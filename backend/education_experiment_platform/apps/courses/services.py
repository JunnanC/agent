"""课程域写用例（doc 02 §一 ``services.py``、§五 服务层、§六 关键事务边界）。

规则（doc 02 §五）：每个写服务统一完成
    权限 → 状态 → 幂等/CAS → 业务写入 → 追加事实 → Audit → Outbox
全部在**同一个事务**内；外部 I/O 只在提交后入队。

视图、serializer、Celery task 都不允许直接 ``model.save(status=...)`` 推进业务状态（doc 02 §一）：
状态跃迁只经过本模块的 ``_assert_transition``，这样非法跃迁会稳定返回
``COURSE_STATE_CONFLICT``，而不是在某个视图里悄悄写坏状态。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db import IntegrityError, transaction
from django.http import HttpRequest
from django.utils import timezone

from apps.core import audit, cas, outbox
from apps.core.errors import (
    COURSE_STATE_CONFLICT,
    ENROLLMENT_BLOCKED,
    ENROLLMENT_CAPACITY_FULL,
    IDEMPOTENCY_KEY_REUSED,  # noqa: F401  (幂等由 apps.core.idempotency 统一处理)
    LAST_OWNER_PROTECTED,
    OWNER_TRANSFER_BLOCKED,
    RESOURCE_NOT_FOUND,
    STAFF_ALREADY_ACTIVE,
    VALIDATION_ERROR,
    ApiError,
)
from apps.core.ids import new_ulid

from . import events, selectors
from .models import (
    Course,
    CourseStaff,
    CourseStaffEvent,
    CourseStaffGrant,
    CourseStaffGrantEvent,
    CourseStatus,
    Enrollment,
    EnrollmentEvent,
    EnrollmentStatus,
    GrantStatus,
    StaffRole,
    StaffStatus,
)
from .ports import Actor, require_teaching_qualification

# doc 01 §四 状态机。``DRAFT -> PUBLISHED`` 之外还包括文档写明的
# ``PUBLISHED -> DRAFT``（撤回编辑，仅当没有已生效发布/任务）。
# 该跃迁首期没有对应端点（doc 08 §六 未列出），因此只登记、不暴露。
# 键值用字面量而不是 ``CourseStatus`` 成员：mypy 在没有 django-stubs 时会把
# ``TextChoices`` 的元组右值推断成 ``tuple[str, str]``，用成员会让类型检查器把
# 合法的状态名判成类型错误。字面量与 doc 07 §三 的列取值一一对应。
COURSE_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"PUBLISHED"},
    "PUBLISHED": {"CLOSED", "DRAFT"},
    "CLOSED": {"ARCHIVED"},
    "ARCHIVED": set(),
}

# 已归档课程的对外可见终态：任何写操作都必须先被它拦下。


@dataclass(frozen=True, slots=True)
class CallContext:
    """一次调用的横切上下文。从 request 提取，便于 service 不依赖 HTTP 细节。"""

    trace_id: str = ""
    client_ip: str = ""
    user_agent: str = ""

    @classmethod
    def from_request(cls, request: HttpRequest) -> CallContext:
        return cls(
            trace_id=str(getattr(request, "trace_id", "") or ""),
            client_ip=request.META.get("REMOTE_ADDR", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )


# ── 内部工具 ─────────────────────────────────────────────────


def _lock_course(actor: Actor, course_public_id: str) -> Course:
    """按 public_id 锁定课程行。

    doc 07 §十 规定统一锁顺序 Course → CourseStaff/Enrollment → ...，
    因此所有写用例都从这里开始加锁，避免交叉死锁。
    """
    course = Course.objects.select_for_update().filter(public_id=course_public_id).first()
    if course is None or selectors.staff_of(course, actor.ref) is None:
        raise ApiError(RESOURCE_NOT_FOUND, detail={"course_id": course_public_id})
    return course


def _assert_transition(current: str, target: str) -> None:
    if target not in COURSE_TRANSITIONS.get(current, set()):
        raise ApiError(
            COURSE_STATE_CONFLICT,
            detail={"from": current, "to": target},
        )


def _touch(course: Course, **fields: Any) -> None:
    """写入字段并推进 row_version。

    在持锁事务内自增而不是用 ``F("row_version") + 1``：后者会让内存中的实例
    与实际值脱节，紧接着用该实例做 CAS 比较就会误判。
    """
    for name, value in fields.items():
        setattr(course, name, value)
    course.row_version += 1
    course.save(update_fields=[*fields.keys(), "row_version", "updated_at"])


def _audit_and_emit(
    actor: Actor,
    context: CallContext,
    *,
    action: str,
    course: Course | None,
    target_type: str,
    target_id: str,
    event_name: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    audit.record_audit(
        actor_ref=actor.ref,
        actor_portal=actor.portal,
        actor_qualification=actor.qualification,
        action=action,
        course_ref=course.public_id if course else "",
        target_type=target_type,
        target_id=target_id,
        before=before,
        after=after,
        trace_id=context.trace_id,
        client_ip=context.client_ip,
        user_agent=context.user_agent,
    )
    outbox.publish_outbox(
        event_name=event_name,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        trace_id=context.trace_id,
    )


# ── 课程生命周期（doc 08 §六）────────────────────────────────


def create_course(actor: Actor, data: dict[str, Any], *, context: CallContext) -> Course:
    """创建课程草稿。

    创建课程要求**有效教师资格**（doc 02 §三），这与「能进教师端」是两层：
    资格是平台级，课程权限是对象级，创建时还没有对象权限可言。
    """
    require_teaching_qualification(actor)
    with transaction.atomic():
        try:
            # 用保存点把唯一键冲突隔离成可翻译的领域错误：外层事务一旦被
            # IntegrityError 污染，后续的 Audit/Outbox 写入都会连带失败。
            with transaction.atomic():
                course = Course.objects.create(
                    public_id=new_ulid(),
                    code=data["code"],
                    title=data["title"],
                    summary=data.get("summary", ""),
                    description=data.get("description", ""),
                    owner_id=actor.ref,
                    status=CourseStatus.DRAFT,
                    visibility=data["visibility"],
                    enrollment_mode=data["enrollment_mode"],
                    capacity=data.get("capacity"),
                    enrollment_start=data.get("enrollment_start"),
                    enrollment_end=data.get("enrollment_end"),
                    teaching_start=data.get("teaching_start"),
                    teaching_end=data.get("teaching_end"),
                )
        except IntegrityError as exc:
            # doc 07 §三 courses_course_code_uniq：课程代码平台内唯一。
            raise ApiError(
                VALIDATION_ERROR,
                detail={"field": "code", "reason": "duplicate"},
            ) from exc
        # 创建者同时成为唯一责任人：课程不允许「有课程但无 OWNER」的中间态。
        staff = CourseStaff.objects.create(
            course=course,
            user_id=actor.ref,
            role=StaffRole.OWNER,
            status=StaffStatus.ACTIVE,
            appointed_by_id=actor.ref,
            appointed_at=timezone.now(),
        )
        CourseStaffEvent.objects.create(
            course_staff=staff,
            course_id=course.public_id,
            user_id=actor.ref,
            action="APPOINT",
            to_status=StaffStatus.ACTIVE,
            actor_id=actor.ref,
            trace_id=context.trace_id,
        )
        _audit_and_emit(
            actor,
            context,
            action="course.create",
            course=course,
            target_type="course",
            target_id=course.public_id,
            event_name=events.COURSE_CREATED,
            aggregate_type=events.AGGREGATE_COURSE,
            aggregate_id=course.public_id,
            payload=events.course_payload(course, trace_id=context.trace_id),
            after={"code": course.code, "title": course.title, "status": course.status},
        )
    return course


def update_course(
    actor: Actor,
    course_public_id: str,
    data: dict[str, Any],
    *,
    expected_row_version: int,
    context: CallContext,
) -> Course:
    """编辑课程。仅 OWNER，且已归档课程不可改。"""
    with transaction.atomic():
        course = _lock_course(actor, course_public_id)
        selectors.require_owner(actor, course)
        cas.assert_row_version(
            actual=course.row_version,
            expected=expected_row_version,
            target_type="course",
            target_id=course.public_id,
        )
        if course.status == CourseStatus.ARCHIVED:
            raise ApiError(COURSE_STATE_CONFLICT, detail={"from": course.status, "to": "EDIT"})

        before = {name: getattr(course, name) for name in data}
        _touch(course, **data)
        _audit_and_emit(
            actor,
            context,
            action="course.update",
            course=course,
            target_type="course",
            target_id=course.public_id,
            event_name=events.COURSE_CREATED.replace("created", "updated"),
            aggregate_type=events.AGGREGATE_COURSE,
            aggregate_id=course.public_id,
            payload=events.course_payload(course, trace_id=context.trace_id),
            before=before,
            after={name: getattr(course, name) for name in data},
        )
    return course


def _assert_publishable(course: Course) -> None:
    """发布前的完整性检查。

    不检查的话会发布出一门「有选课方式但没有报名窗口」的课程，
    学生端看到的是一个永远无法报名的入口。
    """
    problems: list[str] = []
    if course.enrollment_mode == "APPROVAL" and course.capacity is None:
        problems.append("审批选课必须设置容量，否则审批无据可依")
    if (
        course.enrollment_start
        and course.enrollment_end
        and course.enrollment_end <= course.enrollment_start
    ):
        problems.append("报名结束必须晚于开始")
    if problems:
        raise ApiError(COURSE_STATE_CONFLICT, detail={"problems": problems})


def publish_course(
    actor: Actor,
    course_public_id: str,
    *,
    expected_row_version: int,
    context: CallContext,
) -> Course:
    with transaction.atomic():
        course = _lock_course(actor, course_public_id)
        selectors.require_owner(actor, course)
        _assert_transition(course.status, "PUBLISHED")
        cas.assert_row_version(
            actual=course.row_version,
            expected=expected_row_version,
            target_type="course",
            target_id=course.public_id,
        )
        _assert_publishable(course)
        before = {"status": course.status}
        _touch(course, status=CourseStatus.PUBLISHED)
        _audit_and_emit(
            actor,
            context,
            action="course.publish",
            course=course,
            target_type="course",
            target_id=course.public_id,
            event_name=events.COURSE_PUBLISHED,
            aggregate_type=events.AGGREGATE_COURSE,
            aggregate_id=course.public_id,
            payload=events.course_payload(course, trace_id=context.trace_id),
            before=before,
            after={"status": course.status},
        )
    return course


def close_course(actor: Actor, course_public_id: str, *, context: CallContext) -> Course:
    """关闭课程：停止新选课与新实验（doc 08 §六）。历史事实不删除。"""
    with transaction.atomic():
        course = _lock_course(actor, course_public_id)
        selectors.require_owner(actor, course)
        _assert_transition(course.status, "CLOSED")
        before = {"status": course.status}
        _touch(course, status=CourseStatus.CLOSED)
        _audit_and_emit(
            actor,
            context,
            action="course.close",
            course=course,
            target_type="course",
            target_id=course.public_id,
            event_name=events.COURSE_CLOSED,
            aggregate_type=events.AGGREGATE_COURSE,
            aggregate_id=course.public_id,
            payload=events.course_payload(course, trace_id=context.trace_id),
            before=before,
            after={"status": course.status},
        )
    return course


def archive_blockers(course: Course) -> dict[str, Any]:
    """归档阻断项（doc 08 §六 ``archive-check``）。

    **已知缺口**：doc 07 §十三 要求归档前确认「无活动工作区和运行实例」，
    这些事实属于 experiments / provisioning / reviews 域，跨域读必须经 selector 而不是
    直接查表（doc 02 §一）。这几个域尚未落地，因此 ``cross_domain_available`` 返回
    ``False``，调用方与管理端据此知道本次检查不完整——而不是拿到一个假的「无阻断」。
    """
    blockers: list[dict[str, Any]] = []
    pending = Enrollment.objects.filter(course=course, status=EnrollmentStatus.PENDING).count()
    if pending:
        blockers.append({"type": "PENDING_ENROLLMENT", "count": pending})
    return {"blockers": blockers, "cross_domain_available": False}


def archive_course(actor: Actor, course_public_id: str, *, context: CallContext) -> Course:
    with transaction.atomic():
        course = _lock_course(actor, course_public_id)
        selectors.require_owner(actor, course)
        _assert_transition(course.status, "ARCHIVED")
        report = archive_blockers(course)
        if report["blockers"]:
            raise ApiError(
                ENROLLMENT_BLOCKED,
                detail={"blockers": report["blockers"], "course_id": course.public_id},
            )
        before = {"status": course.status}
        _touch(course, status=CourseStatus.ARCHIVED)
        _audit_and_emit(
            actor,
            context,
            action="course.archive",
            course=course,
            target_type="course",
            target_id=course.public_id,
            event_name=events.COURSE_ARCHIVED,
            aggregate_type=events.AGGREGATE_COURSE,
            aggregate_id=course.public_id,
            payload=events.course_payload(
                course, trace_id=context.trace_id, cross_domain_checked=False
            ),
            before=before,
            after={"status": course.status},
        )
    return course


def transfer_owner(
    actor: Actor,
    course_public_id: str,
    *,
    new_owner_ref: str,
    expected_row_version: int,
    context: CallContext,
) -> Course:
    """负责人交接：旧 OWNER 撤销与新 OWNER 生效必须在同一事务内完成。

    中间态（两个 ACTIVE OWNER 或零个）都会被 ``owner_slot`` 唯一约束拒绝，
    所以这里先撤销旧行再插入新行——顺序反了会直接撞约束。
    """
    with transaction.atomic():
        course = _lock_course(actor, course_public_id)
        current = selectors.require_owner(actor, course)
        cas.assert_row_version(
            actual=course.row_version,
            expected=expected_row_version,
            target_type="course",
            target_id=course.public_id,
        )
        if new_owner_ref == actor.ref:
            raise ApiError(OWNER_TRANSFER_BLOCKED, detail={"reason": "不能交接给自己"})

        now = timezone.now()
        CourseStaff.objects.filter(id=current.id).update(
            status=StaffStatus.REVOKED,
            revoked_by_id=actor.ref,
            revoked_at=now,
            row_version=current.row_version + 1,
            updated_at=now,
        )
        CourseStaffEvent.objects.create(
            course_staff=current,
            course_id=course.public_id,
            user_id=current.user_id,
            action="REVOKE",
            from_status=StaffStatus.ACTIVE,
            to_status=StaffStatus.REVOKED,
            actor_id=actor.ref,
            detail={"reason": "OWNER_TRANSFER"},
            trace_id=context.trace_id,
        )

        incoming = selectors.staff_of(course, new_owner_ref)
        if incoming is None:
            incoming = CourseStaff.objects.create(
                course=course,
                user_id=new_owner_ref,
                role=StaffRole.OWNER,
                status=StaffStatus.ACTIVE,
                appointed_by_id=actor.ref,
                appointed_at=now,
            )
        else:
            CourseStaff.objects.filter(id=incoming.id).update(
                role=StaffRole.OWNER,
                status=StaffStatus.ACTIVE,
                appointed_by_id=actor.ref,
                appointed_at=now,
                revoked_by_id="",
                revoked_at=None,
                row_version=incoming.row_version + 1,
                updated_at=now,
            )
        CourseStaffEvent.objects.create(
            course_staff=incoming,
            course_id=course.public_id,
            user_id=new_owner_ref,
            action="APPOINT",
            to_status=StaffStatus.ACTIVE,
            actor_id=actor.ref,
            detail={"role": StaffRole.OWNER},
            trace_id=context.trace_id,
        )

        before = {"owner_id": course.owner_id}
        _touch(course, owner_id=new_owner_ref)
        _audit_and_emit(
            actor,
            context,
            action="course.transfer_owner",
            course=course,
            target_type="course",
            target_id=course.public_id,
            event_name=events.COURSE_STAFF_CHANGED,
            aggregate_type=events.AGGREGATE_COURSE,
            aggregate_id=course.public_id,
            payload=events.course_payload(
                course, trace_id=context.trace_id, new_owner=new_owner_ref
            ),
            before=before,
            after={"owner_id": course.owner_id},
        )
    return course


# ── 教学团队（doc 08 §六 教学团队）────────────────────────────


def appoint_staff(
    actor: Actor,
    course_public_id: str,
    *,
    user_ref: str,
    role: str,
    expected_row_version: int,
    context: CallContext,
) -> CourseStaff:
    """任命助教。

    两条硬规则来自 doc 08 §六：
    * 助教不能被授予 OWNER —— 负责人只能通过 ``transfer_owner`` 变更，
      否则会出现「有两个 OWNER」的中间态。
    * 被任命者必须有有效教师资格 —— 检查的是**被任命者**，不是操作者。
    """
    from .ports import is_teacher_qualified

    with transaction.atomic():
        course = _lock_course(actor, course_public_id)
        selectors.require_owner(actor, course)
        # 这里的 If-Match 针对**课程**row_version：被任命者尚无任职行，
        # 拿不到 staff 级 ETag，而任职集合的聚合根就是课程（doc 07 §十 锁顺序）。
        cas.assert_row_version(
            actual=course.row_version,
            expected=expected_row_version,
            target_type="course",
            target_id=course.public_id,
        )
        if role == StaffRole.OWNER:
            raise ApiError(
                OWNER_TRANSFER_BLOCKED,
                detail={"reason": "助教不能被授予 OWNER，请使用负责人交接接口"},
            )
        if not is_teacher_qualified(user_ref):
            from apps.core.errors import TEACHER_QUALIFICATION_REQUIRED

            raise ApiError(TEACHER_QUALIFICATION_REQUIRED, detail={"user_id": user_ref})

        existing = selectors.staff_of(course, user_ref)
        if existing is not None and existing.status == StaffStatus.ACTIVE:
            raise ApiError(STAFF_ALREADY_ACTIVE, detail={"user_id": user_ref})

        now = timezone.now()
        if existing is None:
            staff = CourseStaff.objects.create(
                course=course,
                user_id=user_ref,
                role=role,
                status=StaffStatus.ACTIVE,
                appointed_by_id=actor.ref,
                appointed_at=now,
            )
        else:
            CourseStaff.objects.filter(id=existing.id).update(
                role=role,
                status=StaffStatus.ACTIVE,
                appointed_by_id=actor.ref,
                appointed_at=now,
                revoked_by_id="",
                revoked_at=None,
                row_version=existing.row_version + 1,
                updated_at=now,
            )
            existing.refresh_from_db()
            staff = existing
        CourseStaffEvent.objects.create(
            course_staff=staff,
            course_id=course.public_id,
            user_id=user_ref,
            action="APPOINT",
            to_status=StaffStatus.ACTIVE,
            actor_id=actor.ref,
            detail={"role": role},
            trace_id=context.trace_id,
        )
        _audit_and_emit(
            actor,
            context,
            action="course.staff.appoint",
            course=course,
            target_type="course_staff",
            target_id=staff.user_id,
            event_name=events.COURSE_STAFF_CHANGED,
            aggregate_type=events.AGGREGATE_COURSE,
            aggregate_id=course.public_id,
            payload=events.course_payload(
                course, trace_id=context.trace_id, staff_user=user_ref, role=role
            ),
            after={"user_id": user_ref, "role": role, "status": StaffStatus.ACTIVE},
        )
    return staff


def update_staff(
    actor: Actor,
    course_public_id: str,
    staff_ref: str,
    *,
    status: str,
    expected_row_version: int,
    context: CallContext,
) -> CourseStaff:
    """更新任职状态（暂停/恢复）。撤销走 ``revoke_staff``，避免绕过唯一负责人保护。"""
    with transaction.atomic():
        course = _lock_course(actor, course_public_id)
        selectors.require_owner(actor, course)
        staff = selectors.get_staff(course, staff_ref)
        cas.assert_row_version(
            actual=staff.row_version,
            expected=expected_row_version,
            target_type="course_staff",
            target_id=staff.user_id,
        )
        if status == StaffStatus.REVOKED:
            raise ApiError(
                COURSE_STATE_CONFLICT,
                detail={"reason": "撤销任职请使用 revoke 接口（需要原因与阻断检查）"},
            )
        if staff.id == selectors.require_owner(actor, course).id and status != StaffStatus.ACTIVE:
            raise ApiError(LAST_OWNER_PROTECTED, detail={"staff_ref": staff.user_id})

        before = {"status": staff.status}
        now = timezone.now()
        CourseStaff.objects.filter(id=staff.id).update(
            status=status, row_version=staff.row_version + 1, updated_at=now
        )
        staff.refresh_from_db()
        CourseStaffEvent.objects.create(
            course_staff=staff,
            course_id=course.public_id,
            user_id=staff.user_id,
            action="UPDATE_STATUS",
            from_status=before["status"],
            to_status=status,
            actor_id=actor.ref,
            trace_id=context.trace_id,
        )
        _audit_and_emit(
            actor,
            context,
            action="course.staff.update",
            course=course,
            target_type="course_staff",
            target_id=staff.user_id,
            event_name=events.COURSE_STAFF_CHANGED,
            aggregate_type=events.AGGREGATE_COURSE,
            aggregate_id=course.public_id,
            payload=events.course_payload(
                course, trace_id=context.trace_id, staff_user=staff.user_id, status=status
            ),
            before=before,
            after={"status": status},
        )
    return staff


def grant_capability(
    actor: Actor,
    course_public_id: str,
    staff_ref: str,
    *,
    capability: str,
    expires_at: datetime | None,
    expected_row_version: int,
    context: CallContext,
) -> CourseStaffGrant:
    """授予助教固定能力（doc 02 §三「需 grant」）。"""
    with transaction.atomic():
        course = _lock_course(actor, course_public_id)
        selectors.require_owner(actor, course)
        staff = selectors.get_staff(course, staff_ref)
        cas.assert_row_version(
            actual=staff.row_version,
            expected=expected_row_version,
            target_type="course_staff",
            target_id=staff.user_id,
        )
        now = timezone.now()
        grant, _created = CourseStaffGrant.objects.get_or_create(
            course_staff=staff,
            capability=capability,
            defaults={
                "status": GrantStatus.ACTIVE,
                "expires_at": expires_at,
                "granted_by_id": actor.ref,
                "granted_at": now,
            },
        )
        if grant.status != GrantStatus.ACTIVE:
            CourseStaffGrant.objects.filter(id=grant.id).update(
                status=GrantStatus.ACTIVE,
                expires_at=expires_at,
                granted_by_id=actor.ref,
                granted_at=now,
                revoked_by_id="",
                revoked_at=None,
                row_version=grant.row_version + 1,
                updated_at=now,
            )
            grant.refresh_from_db()
        CourseStaffGrantEvent.objects.create(
            course_staff_grant=grant,
            course_id=course.public_id,
            capability=capability,
            action="GRANT",
            to_status=GrantStatus.ACTIVE,
            actor_id=actor.ref,
            trace_id=context.trace_id,
        )
        _audit_and_emit(
            actor,
            context,
            action="course.staff.grant",
            course=course,
            target_type="course_staff_grant",
            target_id=f"{staff.user_id}:{capability}",
            event_name=events.COURSE_STAFF_CHANGED,
            aggregate_type=events.AGGREGATE_COURSE,
            aggregate_id=course.public_id,
            payload=events.course_payload(
                course,
                trace_id=context.trace_id,
                staff_user=staff.user_id,
                capability=capability,
            ),
            after={"capability": capability, "status": GrantStatus.ACTIVE},
        )
    return grant


def revoke_staff(
    actor: Actor,
    course_public_id: str,
    staff_ref: str,
    *,
    reason: str,
    expected_row_version: int,
    context: CallContext,
) -> CourseStaff:
    """撤销任职。撤销唯一地址的负责人会被拒绝（doc 02 §三「课程负责人也不能操作」）。"""
    with transaction.atomic():
        course = _lock_course(actor, course_public_id)
        selectors.require_owner(actor, course)
        staff = selectors.get_staff(course, staff_ref)
        cas.assert_row_version(
            actual=staff.row_version,
            expected=expected_row_version,
            target_type="course_staff",
            target_id=staff.user_id,
        )
        if staff.role == StaffRole.OWNER and staff.status == StaffStatus.ACTIVE:
            raise ApiError(LAST_OWNER_PROTECTED, detail={"staff_ref": staff.user_id})

        now = timezone.now()
        before = {"status": staff.status}
        CourseStaff.objects.filter(id=staff.id).update(
            status=StaffStatus.REVOKED,
            revoked_by_id=actor.ref,
            revoked_at=now,
            row_version=staff.row_version + 1,
            updated_at=now,
        )
        # 任职撤销必须连带失效其能力授权，否则「已撤销的助教」仍能通过 grant 检查。
        CourseStaffGrant.objects.filter(course_staff=staff, status=GrantStatus.ACTIVE).update(
            status=GrantStatus.REVOKED,
            revoked_by_id=actor.ref,
            revoked_at=now,
            updated_at=now,
        )
        staff.refresh_from_db()
        CourseStaffEvent.objects.create(
            course_staff=staff,
            course_id=course.public_id,
            user_id=staff.user_id,
            action="REVOKE",
            from_status=before["status"],
            to_status=StaffStatus.REVOKED,
            actor_id=actor.ref,
            detail={"reason": reason},
            trace_id=context.trace_id,
        )
        _audit_and_emit(
            actor,
            context,
            action="course.staff.revoke",
            course=course,
            target_type="course_staff",
            target_id=staff.user_id,
            event_name=events.COURSE_STAFF_CHANGED,
            aggregate_type=events.AGGREGATE_COURSE,
            aggregate_id=course.public_id,
            payload=events.course_payload(
                course, trace_id=context.trace_id, staff_user=staff.user_id
            ),
            before=before,
            after={"status": StaffStatus.REVOKED, "reason": reason},
        )
    return staff


# ── 名册（doc 08 §七）─────────────────────────────────────────


def review_enrollment(
    actor: Actor,
    course_public_id: str,
    enrollment_public_id: str,
    *,
    decision: str,
    note: str,
    expected_row_version: int,
    context: CallContext,
) -> Enrollment:
    """审批选课。

    doc 08 §七：「审批时重新检查容量，不能信任列表加载时的剩余名额」。
    因此这里在**锁内**重新统计 ACTIVE 数量，而不是接受调用方传入的余量。
    """
    with transaction.atomic():
        course = _lock_course(actor, course_public_id)
        selectors.require_capability(actor, course, "MANAGE_ENROLLMENT")
        enrollment = (
            Enrollment.objects.select_for_update()
            .filter(course=course, public_id=enrollment_public_id)
            .first()
        )
        if enrollment is None:
            raise ApiError(RESOURCE_NOT_FOUND, detail={"enrollment_id": enrollment_public_id})
        if enrollment.status != EnrollmentStatus.PENDING:
            raise ApiError(
                COURSE_STATE_CONFLICT,
                detail={"from": enrollment.status, "to": decision},
            )
        cas.assert_row_version(
            actual=enrollment.row_version,
            expected=expected_row_version,
            target_type="enrollment",
            target_id=enrollment.public_id,
        )

        now = timezone.now()
        new_status = EnrollmentStatus.ACTIVE if decision == "APPROVE" else EnrollmentStatus.REJECTED
        if new_status == EnrollmentStatus.ACTIVE and course.capacity is not None:
            active = selectors.active_enrollment_count(course)
            if active >= course.capacity:
                raise ApiError(
                    ENROLLMENT_CAPACITY_FULL,
                    detail={"capacity": course.capacity, "active": active},
                )

        before = {"status": enrollment.status}
        fields: dict[str, Any] = {
            "status": new_status,
            "reviewed_by_id": actor.ref,
            "reviewed_at": now,
            "decision_note": note,
        }
        if new_status == EnrollmentStatus.ACTIVE:
            fields["activated_at"] = now
        Enrollment.objects.filter(id=enrollment.id).update(
            row_version=enrollment.row_version + 1, updated_at=now, **fields
        )
        enrollment.refresh_from_db()
        EnrollmentEvent.objects.create(
            enrollment=enrollment,
            course_id=course.public_id,
            student_id=enrollment.student_id,
            action=decision,
            from_status=before["status"],
            to_status=new_status,
            actor_id=actor.ref,
            reason=note,
            trace_id=context.trace_id,
        )
        _audit_and_emit(
            actor,
            context,
            action="enrollment.review",
            course=course,
            target_type="enrollment",
            target_id=enrollment.public_id,
            event_name=(
                events.ENROLLMENT_ACTIVATED
                if new_status == EnrollmentStatus.ACTIVE
                else events.ENROLLMENT_REJECTED
            ),
            aggregate_type=events.AGGREGATE_ENROLLMENT,
            aggregate_id=enrollment.public_id,
            payload=events.enrollment_payload(
                enrollment, trace_id=context.trace_id, decision=decision
            ),
            before=before,
            after={"status": new_status, "decision_note": note},
        )
    return enrollment


def enrollment_removal_check(enrollment: Enrollment) -> dict[str, Any]:
    """移除阻断检查（doc 08 §七 ``removal-check``）。

    与 ``archive_blockers`` 同样的缺口：未完成实验、活动实例、待审报告属于
    experiments / provisioning / reviews 域，跨域读必须经 selector。
    这些域未落地，因此显式声明检查不完整，而不是返回假的「无阻断」。
    """
    blockers: list[dict[str, Any]] = []
    if enrollment.status not in (EnrollmentStatus.PENDING, EnrollmentStatus.ACTIVE):
        blockers.append({"type": "ENROLLMENT_NOT_LIVE", "status": enrollment.status})
    return {"blockers": blockers, "cross_domain_available": False}


def remove_enrollment(
    actor: Actor,
    course_public_id: str,
    enrollment_public_id: str,
    *,
    reason: str,
    context: CallContext,
) -> Enrollment:
    """移除选课：在事务内重查阻断后结束周期，不删除历史（doc 01 §一 原则 3）。"""
    with transaction.atomic():
        course = _lock_course(actor, course_public_id)
        selectors.require_capability(actor, course, "MANAGE_ENROLLMENT")
        enrollment = (
            Enrollment.objects.select_for_update()
            .filter(course=course, public_id=enrollment_public_id)
            .first()
        )
        if enrollment is None:
            raise ApiError(RESOURCE_NOT_FOUND, detail={"enrollment_id": enrollment_public_id})

        report = enrollment_removal_check(enrollment)
        if report["blockers"]:
            raise ApiError(
                ENROLLMENT_BLOCKED,
                detail={"blockers": report["blockers"], "enrollment_id": enrollment.public_id},
            )

        now = timezone.now()
        before = {"status": enrollment.status}
        Enrollment.objects.filter(id=enrollment.id).update(
            status=EnrollmentStatus.ENDED,
            ended_at=now,
            end_reason=reason,
            row_version=enrollment.row_version + 1,
            updated_at=now,
        )
        enrollment.refresh_from_db()
        EnrollmentEvent.objects.create(
            enrollment=enrollment,
            course_id=course.public_id,
            student_id=enrollment.student_id,
            action="REMOVE",
            from_status=before["status"],
            to_status=EnrollmentStatus.ENDED,
            actor_id=actor.ref,
            reason=reason,
            trace_id=context.trace_id,
        )
        _audit_and_emit(
            actor,
            context,
            action="enrollment.remove",
            course=course,
            target_type="enrollment",
            target_id=enrollment.public_id,
            event_name=events.ENROLLMENT_ENDED,
            aggregate_type=events.AGGREGATE_ENROLLMENT,
            aggregate_id=enrollment.public_id,
            payload=events.enrollment_payload(enrollment, trace_id=context.trace_id, reason=reason),
            before=before,
            after={"status": EnrollmentStatus.ENDED, "end_reason": reason},
        )
    return enrollment
