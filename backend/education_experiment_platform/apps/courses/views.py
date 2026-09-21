"""HTTP 到 service/selector 的薄适配层（doc 02 §一 ``views.py``）。

视图只做四件事：解析输入 → 取 actor/context → 调用 selector/service → 套信封。
这里**不允许**出现状态判断、``model.save(status=...)``、跨域查表或手拼 JSON。

写入顺序严格按 doc 00 §3.2 固定：

```text
准入 → 数据范围 → 幂等占位/精确重放 → If-Match/CAS → service（内部再加锁）
```

所以本模块里 ``cas.read_if_match`` 一律出现在 ``self.idempotent(...)`` 的 ``produce``
回调**内部**：先占位（失败会随外层事务回滚并释放键），再校验前置条件。
把顺序反过来的话，缺 ``Idempotency-Key`` 的请求会先拿到 428，
而且同一幂等键的合法重试会因为「前后两次校验的先后不同」拿到不同错误。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import cas, idempotency, responses

from . import selectors, serializers, services
from .models import Course
from .permissions import TeachingPortalRequired, TeachingQualificationRequired
from .ports import Actor, get_actor
from .services import CallContext

OPENAPI_TAG = "teaching"


@extend_schema(tags=[OPENAPI_TAG])
class TeachingView(APIView):
    """教师端视图基类：门户准入 + 全局教师资格，两层都在进入业务逻辑之前。"""

    # doc 02 §4.1：接口级只做粗粒度检查（portal + 全局资格）。
    # 对象级权限必须落在 selector/service，因为这里还拿不到 course 实例。
    permission_classes = [TeachingPortalRequired, TeachingQualificationRequired]

    def actor(self, request: Request) -> Actor:
        return get_actor(request)

    def context(self, request: Request) -> CallContext:
        return CallContext.from_request(request)

    def validated(self, serializer_class: type, request: Request, **kwargs: Any) -> dict[str, Any]:
        serializer = serializer_class(data=request.data, **kwargs)
        serializer.is_valid(raise_exception=True)
        return dict(serializer.validated_data)

    def if_match_raw(self, request: Request) -> str:
        """幂等摘要要包含前置条件，但**不在这里校验**。

        ``If-Match`` 属于请求体语义的一部分（同一个 ``Idempotency-Key`` 配不同 ETag
        是完全不同的请求，必须判成键复用），所以进摘要；而它是否合法、是否过期，
        要等占位完成之后由 ``cas.read_if_match`` + service 判断。
        """
        return (request.headers.get(cas.IF_MATCH_HEADER) or "").strip()

    def idempotent(
        self,
        request: Request,
        *,
        scope: str,
        actor: Actor,
        payload: Any,
        produce: Callable[[], Response],
    ) -> Response:
        """幂等写包装（doc 02 §七、doc 08 §十六）。

        占位记录与业务写入放在**同一个外层事务**里，业务回滚时占位一起消失。
        如果占位单独提交，一次失败的请求会把该键锁死到 TTL 结束，
        之后所有同键重试都只能拿到 ``IDEMPOTENCY_IN_PROGRESS``。
        """
        key = idempotency.parse_idempotency_key(request)
        with transaction.atomic():
            record, replay = idempotency.reserve_idempotency(
                scope=scope, actor_ref=actor.ref, key=key, payload=payload
            )
            if replay is not None:
                # 同一意图的重试：直接回放首次响应，不重复副作用。
                return Response(replay.body, status=replay.status)
            if record is None:  # pragma: no cover - 由 reserve_idempotency 的契约保证
                raise RuntimeError("幂等占位失败但仍需继续执行")
            response = produce()
            idempotency.store_idempotency_response(
                record, status=response.status_code, body=response.data
            )
            return response


# ── 课程（doc 08 §六）───────────────────────────────────────


class TeachingCourseListCreateView(TeachingView):
    """``GET /teaching/courses`` 我的课程 / ``POST`` 创建草稿。"""

    @extend_schema(
        operation_id="teaching_courses_list",
        responses={200: serializers.CourseListResponseSerializer},
    )
    def get(self, request: Request) -> Response:
        actor = self.actor(request)
        page, page_size = responses.parse_page_params(request)
        courses, total = selectors.list_teaching_courses(
            actor,
            status=request.query_params.get("status") or None,
            keyword=request.query_params.get("q") or None,
            page=page,
            page_size=page_size,
        )
        return responses.paginated(
            [serializers.course_payload(course) for course in courses],
            request,
            page=page,
            page_size=page_size,
            total=total,
        )

    @extend_schema(
        request=serializers.CourseCreateSerializer,
        responses={201: serializers.CourseResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        actor = self.actor(request)
        data = serializers.course_data(self.validated(serializers.CourseCreateSerializer, request))
        return self.idempotent(
            request,
            scope="teaching.course.create",
            actor=actor,
            payload=data,
            produce=lambda: responses.success(
                serializers.course_payload(
                    services.create_course(actor, data, context=self.context(request))
                ),
                request,
                status=201,
            ),
        )


class TeachingCourseDetailView(TeachingView):
    """``GET /teaching/courses/{id}`` 详情 / ``PATCH`` 编辑（OWNER，If-Match）。"""

    @extend_schema(
        operation_id="teaching_courses_retrieve",
        responses={200: serializers.CourseResponseSerializer},
    )
    def get(self, request: Request, course_id: str) -> Response:
        actor = self.actor(request)
        course = selectors.get_teaching_course(actor, course_id)
        return responses.success(
            serializers.course_payload(course),
            request,
            etag=cas.etag_for(course.row_version),
        )

    @extend_schema(
        request=serializers.CourseUpdateSerializer,
        responses={200: serializers.CourseResponseSerializer},
    )
    def patch(self, request: Request, course_id: str) -> Response:
        actor = self.actor(request)
        # 无幂等键的写路径：先按 selector 定数据范围（不可见即 404），再校验 If-Match。
        course = selectors.get_teaching_course(actor, course_id)
        expected = cas.read_if_match(request)
        # 传入 instance 才能让跨字段窗口校验在 PATCH 上按「改后的整体」判断。
        data = serializers.course_data(
            self.validated(
                serializers.CourseUpdateSerializer, request, partial=True, instance=course
            )
        )
        updated = services.update_course(
            actor,
            course_id,
            data,
            expected_row_version=expected,
            context=self.context(request),
        )
        return responses.success(
            serializers.course_payload(updated),
            request,
            etag=cas.etag_for(updated.row_version),
        )


class TeachingCoursePublishView(TeachingView):
    """``POST /teaching/courses/{id}/publish`` 发布（OWNER，幂等 + If-Match）。"""

    @extend_schema(request=None, responses={200: serializers.CourseResponseSerializer})
    def post(self, request: Request, course_id: str) -> Response:
        actor = self.actor(request)
        return self.idempotent(
            request,
            scope="teaching.course.publish",
            actor=actor,
            payload={"course_id": course_id, "if_match": self.if_match_raw(request)},
            produce=lambda: self._publish(request, actor, course_id),
        )

    def _publish(self, request: Request, actor: Actor, course_id: str) -> Response:
        expected = cas.read_if_match(request)
        return responses.success(
            serializers.course_payload(
                services.publish_course(
                    actor,
                    course_id,
                    expected_row_version=expected,
                    context=self.context(request),
                )
            ),
            request,
            etag=cas.etag_for(selectors.get_teaching_course(actor, course_id).row_version),
        )


class TeachingCourseCloseView(TeachingView):
    """``POST /teaching/courses/{id}/close`` 关闭新选课与新实验（OWNER，幂等）。

    doc 08 §六 与 §十六 只为「课程设置」和 ``publish``/``transfer-owner`` 要求
    ``If-Match``，因此本接口不做 CAS；已归档课程仍由 service 的状态机拦下。
    """

    @extend_schema(request=None, responses={200: serializers.CourseResponseSerializer})
    def post(self, request: Request, course_id: str) -> Response:
        actor = self.actor(request)
        return self.idempotent(
            request,
            scope="teaching.course.close",
            actor=actor,
            payload={"course_id": course_id},
            produce=lambda: responses.success(
                serializers.course_payload(
                    services.close_course(actor, course_id, context=self.context(request))
                ),
                request,
            ),
        )


class TeachingCourseArchiveCheckView(TeachingView):
    """``GET /teaching/courses/{id}/archive-check`` 归档阻断（OWNER，只读）。"""

    @extend_schema(responses={200: serializers.BlockerReportResponseSerializer})
    def get(self, request: Request, course_id: str) -> Response:
        actor = self.actor(request)
        course = selectors.get_teaching_course(actor, course_id)
        selectors.require_owner(actor, course)
        return responses.success(services.archive_blockers(course), request)


class TeachingCourseArchiveView(TeachingView):
    """``POST /teaching/courses/{id}/archive`` 归档并只读化（OWNER，幂等）。

    doc 01 §四 的状态机要求先 ``CLOSED`` 再 ``ARCHIVED``；``PUBLISHED`` 直接归档
    会拿到 ``COURSE_STATE_CONFLICT``，这是有意的硬顺序。
    """

    @extend_schema(request=None, responses={200: serializers.CourseResponseSerializer})
    def post(self, request: Request, course_id: str) -> Response:
        actor = self.actor(request)
        return self.idempotent(
            request,
            scope="teaching.course.archive",
            actor=actor,
            payload={"course_id": course_id},
            produce=lambda: responses.success(
                serializers.course_payload(
                    services.archive_course(actor, course_id, context=self.context(request))
                ),
                request,
            ),
        )


class TeachingCourseTransferOwnerView(TeachingView):
    """``POST /teaching/courses/{id}/transfer-owner`` 负责人交接（幂等 + If-Match）。"""

    @extend_schema(
        request=serializers.TransferOwnerSerializer,
        responses={200: serializers.CourseResponseSerializer},
    )
    def post(self, request: Request, course_id: str) -> Response:
        actor = self.actor(request)
        data = self.validated(serializers.TransferOwnerSerializer, request)
        return self.idempotent(
            request,
            scope="teaching.course.transfer-owner",
            actor=actor,
            payload={
                "course_id": course_id,
                "if_match": self.if_match_raw(request),
                **data,
            },
            produce=lambda: self._transfer(request, actor, course_id, data),
        )

    def _transfer(
        self, request: Request, actor: Actor, course_id: str, data: dict[str, Any]
    ) -> Response:
        expected = cas.read_if_match(request)
        return responses.success(
            serializers.course_payload(
                services.transfer_owner(
                    actor,
                    course_id,
                    new_owner_ref=data["user_id"],
                    expected_row_version=expected,
                    context=self.context(request),
                )
            ),
            request,
        )


# ── 教学团队（doc 08 §六「教学团队」）────────────────────────


class TeachingStaffListCreateView(TeachingView):
    """``GET`` 查询教学团队 / ``POST`` 任命助教（OWNER）。"""

    @extend_schema(responses={200: serializers.StaffListResponseSerializer})
    def get(self, request: Request, course_id: str) -> Response:
        actor = self.actor(request)
        course = selectors.get_teaching_course(actor, course_id)
        selectors.require_owner(actor, course)
        staff = list(course.staff.all().order_by("role", "user_id"))
        return responses.success([serializers.staff_payload(row) for row in staff], request)

    @extend_schema(
        request=serializers.StaffCreateSerializer,
        responses={201: serializers.StaffResponseSerializer},
    )
    def post(self, request: Request, course_id: str) -> Response:
        actor = self.actor(request)
        data = self.validated(serializers.StaffCreateSerializer, request)
        return self.idempotent(
            request,
            scope="teaching.staff.appoint",
            actor=actor,
            payload={
                "course_id": course_id,
                "if_match": self.if_match_raw(request),
                **data,
            },
            produce=lambda: self._appoint(request, actor, course_id, data),
        )

    def _appoint(
        self, request: Request, actor: Actor, course_id: str, data: dict[str, Any]
    ) -> Response:
        # 被任命者此时还没有任职行，拿不到 staff 级 ETag，所以用课程 ETag（doc 07 §十 锁顺序）。
        expected = cas.read_if_match(request)
        return responses.success(
            serializers.staff_payload(
                services.appoint_staff(
                    actor,
                    course_id,
                    user_ref=data["user_id"],
                    role=data["role"],
                    expected_row_version=expected,
                    context=self.context(request),
                )
            ),
            request,
            status=201,
        )


class TeachingStaffDetailView(TeachingView):
    """``PATCH /teaching/courses/{id}/staff/{staff_id}`` 暂停/恢复任职（If-Match）。"""

    @extend_schema(
        request=serializers.StaffUpdateSerializer,
        responses={200: serializers.StaffResponseSerializer},
    )
    def patch(self, request: Request, course_id: str, staff_id: str) -> Response:
        actor = self.actor(request)
        data = self.validated(serializers.StaffUpdateSerializer, request)
        expected = cas.read_if_match(request)
        updated = services.update_staff(
            actor,
            course_id,
            staff_id,
            status=data["status"],
            expected_row_version=expected,
            context=self.context(request),
        )
        return responses.success(
            serializers.staff_payload(updated),
            request,
            etag=cas.etag_for(updated.row_version),
        )


class TeachingStaffGrantListCreateView(TeachingView):
    """``GET`` 该成员的能力授权 / ``POST`` 授予固定能力（If-Match）。"""

    @extend_schema(responses={200: serializers.GrantListResponseSerializer})
    def get(self, request: Request, course_id: str, staff_id: str) -> Response:
        actor = self.actor(request)
        course = selectors.get_teaching_course(actor, course_id)
        selectors.require_owner(actor, course)
        staff = selectors.get_staff(course, staff_id)
        grants = list(staff.grants.all().order_by("capability"))
        return responses.success([serializers.grant_payload(row) for row in grants], request)

    @extend_schema(
        request=serializers.GrantCreateSerializer,
        responses={201: serializers.GrantResponseSerializer},
    )
    def post(self, request: Request, course_id: str, staff_id: str) -> Response:
        actor = self.actor(request)
        data = self.validated(serializers.GrantCreateSerializer, request)
        return self.idempotent(
            request,
            scope="teaching.staff.grant",
            actor=actor,
            payload={
                "course_id": course_id,
                "staff_id": staff_id,
                "if_match": self.if_match_raw(request),
                **data,
            },
            produce=lambda: self._grant(request, actor, course_id, staff_id, data),
        )

    def _grant(
        self,
        request: Request,
        actor: Actor,
        course_id: str,
        staff_id: str,
        data: dict[str, Any],
    ) -> Response:
        expected = cas.read_if_match(request)
        return responses.success(
            serializers.grant_payload(
                services.grant_capability(
                    actor,
                    course_id,
                    staff_id,
                    capability=data["capability"],
                    expires_at=data["expires_at"],
                    expected_row_version=expected,
                    context=self.context(request),
                )
            ),
            request,
            status=201,
        )


class TeachingStaffRevokeView(TeachingView):
    """``POST /teaching/courses/{id}/staff/{staff_id}/revoke`` 撤销任职（If-Match）。"""

    @extend_schema(
        request=serializers.ReasonSerializer,
        responses={200: serializers.StaffResponseSerializer},
    )
    def post(self, request: Request, course_id: str, staff_id: str) -> Response:
        actor = self.actor(request)
        data = self.validated(serializers.ReasonSerializer, request)
        return self.idempotent(
            request,
            scope="teaching.staff.revoke",
            actor=actor,
            payload={
                "course_id": course_id,
                "staff_id": staff_id,
                "if_match": self.if_match_raw(request),
                **data,
            },
            produce=lambda: self._revoke(request, actor, course_id, staff_id, data),
        )

    def _revoke(
        self,
        request: Request,
        actor: Actor,
        course_id: str,
        staff_id: str,
        data: dict[str, Any],
    ) -> Response:
        expected = cas.read_if_match(request)
        return responses.success(
            serializers.staff_payload(
                services.revoke_staff(
                    actor,
                    course_id,
                    staff_id,
                    reason=data["reason"],
                    expected_row_version=expected,
                    context=self.context(request),
                )
            ),
            request,
        )


# ── 名册（doc 08 §七）──────────────────────────────────────


class TeachingEnrollmentView(TeachingView):
    """名册读接口的公共前置：课程可见 + 具备 ``MANAGE_ENROLLMENT``。"""

    def roster_course(self, request: Request, course_id: str) -> tuple[Actor, Course]:
        actor = self.actor(request)
        course = selectors.get_teaching_course(actor, course_id)
        selectors.require_capability(actor, course, "MANAGE_ENROLLMENT")
        return actor, course


class TeachingEnrollmentListView(TeachingEnrollmentView):
    """``GET /teaching/courses/{id}/enrollments`` 名册/申请列表。"""

    @extend_schema(
        operation_id="teaching_enrollments_list",
        responses={200: serializers.EnrollmentListResponseSerializer},
    )
    def get(self, request: Request, course_id: str) -> Response:
        _actor, course = self.roster_course(request, course_id)
        page, page_size = responses.parse_page_params(request)
        rows, total = selectors.roster(
            course,
            status=request.query_params.get("status") or None,
            keyword=request.query_params.get("q") or None,
            page=page,
            page_size=page_size,
        )
        return responses.paginated(
            [serializers.enrollment_payload(row) for row in rows],
            request,
            page=page,
            page_size=page_size,
            total=total,
        )


class TeachingEnrollmentDetailView(TeachingEnrollmentView):
    """``GET /teaching/courses/{id}/enrollments/{eid}`` 详情与历史。"""

    @extend_schema(
        operation_id="teaching_enrollments_retrieve",
        responses={200: serializers.EnrollmentResponseSerializer},
    )
    def get(self, request: Request, course_id: str, enrollment_id: str) -> Response:
        _actor, course = self.roster_course(request, course_id)
        enrollment = selectors.get_enrollment(course, enrollment_id)
        data = serializers.enrollment_payload(enrollment)
        data["events"] = [
            {
                "action": event.action,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "actor_id": event.actor_id,
                "reason": event.reason,
                "created_at": event.created_at.isoformat(),
            }
            for event in enrollment.events.all().order_by("id")
        ]
        return responses.success(data, request, etag=cas.etag_for(enrollment.row_version))


class TeachingEnrollmentReviewView(TeachingEnrollmentView):
    """``POST .../enrollments/{eid}/review`` 审批（幂等 + If-Match）。"""

    @extend_schema(
        request=serializers.EnrollmentReviewSerializer,
        responses={200: serializers.EnrollmentResponseSerializer},
    )
    def post(self, request: Request, course_id: str, enrollment_id: str) -> Response:
        actor = self.actor(request)
        data = self.validated(serializers.EnrollmentReviewSerializer, request)
        return self.idempotent(
            request,
            scope="teaching.enrollment.review",
            actor=actor,
            payload={
                "course_id": course_id,
                "enrollment_id": enrollment_id,
                "if_match": self.if_match_raw(request),
                **data,
            },
            produce=lambda: self._review(request, actor, course_id, enrollment_id, data),
        )

    def _review(
        self,
        request: Request,
        actor: Actor,
        course_id: str,
        enrollment_id: str,
        data: dict[str, Any],
    ) -> Response:
        expected = cas.read_if_match(request)
        return responses.success(
            serializers.enrollment_payload(
                services.review_enrollment(
                    actor,
                    course_id,
                    enrollment_id,
                    decision=data["decision"],
                    note=data["note"],
                    expected_row_version=expected,
                    context=self.context(request),
                )
            ),
            request,
        )


class TeachingEnrollmentRemovalCheckView(TeachingEnrollmentView):
    """``GET .../enrollments/{eid}/removal-check`` 移除阻断（只读）。"""

    @extend_schema(responses={200: serializers.BlockerReportResponseSerializer})
    def get(self, request: Request, course_id: str, enrollment_id: str) -> Response:
        _actor, course = self.roster_course(request, course_id)
        enrollment = selectors.get_enrollment(course, enrollment_id)
        return responses.success(services.enrollment_removal_check(enrollment), request)


class TeachingEnrollmentRemoveView(TeachingEnrollmentView):
    """``POST .../enrollments/{eid}/remove`` 事务内重查阻断并移除（幂等）。"""

    @extend_schema(
        request=serializers.ReasonSerializer,
        responses={200: serializers.EnrollmentResponseSerializer},
    )
    def post(self, request: Request, course_id: str, enrollment_id: str) -> Response:
        actor = self.actor(request)
        data = self.validated(serializers.ReasonSerializer, request)
        return self.idempotent(
            request,
            scope="teaching.enrollment.remove",
            actor=actor,
            payload={"course_id": course_id, "enrollment_id": enrollment_id, **data},
            produce=lambda: responses.success(
                serializers.enrollment_payload(
                    services.remove_enrollment(
                        actor,
                        course_id,
                        enrollment_id,
                        reason=data["reason"],
                        context=self.context(request),
                    )
                ),
                request,
            ),
        )
