"""输入校验与响应结构（doc 02 §一 ``serializers.py``）。

三条约定：

* serializer 只校验**形状与取值范围**。跨字段的领域不变量（例如「审批选课必须有容量」）
  留在 model/service，避免同一条规则出现两份实现而日后只改一处。
* 输出只含 ``public_id`` 与业务 code，绝不返回自增主键（doc 08 §1.1）。
  因此 ``courses_course_staff`` 没有 public_id，对外用**成员账号 public_id** 标识任职。
* 时间统一由 DRF ``DateTimeField`` 输出 ISO 8601 带时区；数据库存 UTC（doc 08 §1.1）。
"""

from __future__ import annotations

from typing import Any

# 重用 P00 已有的 trace 元数据组件，避免同名不同身份的重复组件。
from education_experiment_platform.serializers import TraceMetaSerializer
from rest_framework import serializers

from .models import (
    Course,
    CourseStaff,
    CourseStaffGrant,
    CourseVisibility,
    Enrollment,
    EnrollmentMode,
    StaffCapability,
    StaffRole,
    StaffStatus,
)

# 允许 PATCH 的字段白名单。``code`` 不在其中：课程代码是外部系统（教务/导入）的
# 关联键，创建后可变会让已下发的选课链接和导出附件对不上号（doc 08 §六 只列出
# 「编辑」而未把 code 列为可改字段）。
COURSE_EDITABLE_FIELDS: tuple[str, ...] = (
    "title",
    "summary",
    "description",
    "visibility",
    "enrollment_mode",
    "capacity",
    "enrollment_start",
    "enrollment_end",
    "teaching_start",
    "teaching_end",
)

# 时间窗口字段，成对校验先后顺序（doc 07 §五 的 CHECK 约束在这里提前成 400）。
_WINDOW_PAIRS: tuple[tuple[str, str], ...] = (
    ("enrollment_start", "enrollment_end"),
    ("teaching_start", "teaching_end"),
)


class CourseWindowMixin:
    """报名/教学窗口的先后校验。

    与 doc 07 §五 的 CHECK 约束同一规则：serializer 给出可读的 400，
    数据库约束作为最后一道兜底（直接写库的脚本同样被拒绝）。
    """

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        # PATCH 时只传了部分字段，未提交的一边要从现有实例取值，
        # 否则「只改结束时间」这种合法请求会因为另一边看不见而漏检。
        instance = getattr(self, "instance", None)
        for start_name, end_name in _WINDOW_PAIRS:
            start = attrs.get(start_name, getattr(instance, start_name, None))
            end = attrs.get(end_name, getattr(instance, end_name, None))
            if start is not None and end is not None and end <= start:
                raise serializers.ValidationError(
                    {end_name: "必须晚于对应的开始时间"},
                    code="VALIDATION_ERROR",
                )
        return attrs


class CourseCreateSerializer(CourseWindowMixin, serializers.Serializer):
    """``POST /teaching/courses`` 请求体（doc 08 §六 创建课程请求示例）。"""

    code = serializers.CharField(max_length=64, trim_whitespace=True)
    title = serializers.CharField(max_length=128, trim_whitespace=True)
    summary = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    description = serializers.CharField(required=False, allow_blank=True, default="")
    visibility = serializers.ChoiceField(
        choices=CourseVisibility.values, default=CourseVisibility.PUBLIC
    )
    enrollment_mode = serializers.ChoiceField(
        choices=EnrollmentMode.values, default=EnrollmentMode.OPEN
    )
    # 容量上限取一个远高于实际课程的数值：目的只是挡住把容量写成天文数字后
    # 让名册统计溢出，不是业务策略。
    capacity = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=1_000_000
    )
    enrollment_start = serializers.DateTimeField(required=False, allow_null=True, default=None)
    enrollment_end = serializers.DateTimeField(required=False, allow_null=True, default=None)
    teaching_start = serializers.DateTimeField(required=False, allow_null=True, default=None)
    teaching_end = serializers.DateTimeField(required=False, allow_null=True, default=None)

    def validate_code(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("课程代码不能为空", code="VALIDATION_ERROR")
        return value.strip()


class CourseUpdateSerializer(CourseWindowMixin, serializers.Serializer):
    """``PATCH /teaching/courses/{id}`` 请求体。

    ``partial=True`` 由视图传入；字段缺省表示「不改」。显式传 ``null`` 表示清空
    （仅对 nullable 字段有意义），因此 nullable 字段都开了 ``allow_null``。
    """

    title = serializers.CharField(max_length=128, required=False, trim_whitespace=True)
    summary = serializers.CharField(max_length=255, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    visibility = serializers.ChoiceField(choices=CourseVisibility.values, required=False)
    enrollment_mode = serializers.ChoiceField(choices=EnrollmentMode.values, required=False)
    capacity = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=1_000_000
    )
    enrollment_start = serializers.DateTimeField(required=False, allow_null=True)
    enrollment_end = serializers.DateTimeField(required=False, allow_null=True)
    teaching_start = serializers.DateTimeField(required=False, allow_null=True)
    teaching_end = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs = super().validate(attrs)
        if not attrs:
            raise serializers.ValidationError("至少要提供一个可修改字段", code="VALIDATION_ERROR")
        return attrs


class CourseSerializer(serializers.Serializer):
    """课程详情输出（doc 08 §1.3 详情信封的 ``data``）。"""

    public_id = serializers.CharField(read_only=True)
    code = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    summary = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    visibility = serializers.CharField(read_only=True)
    enrollment_mode = serializers.CharField(read_only=True)
    capacity = serializers.IntegerField(read_only=True, allow_null=True)
    enrollment_start = serializers.DateTimeField(read_only=True)
    enrollment_end = serializers.DateTimeField(read_only=True)
    teaching_start = serializers.DateTimeField(read_only=True)
    teaching_end = serializers.DateTimeField(read_only=True)
    owner_id = serializers.CharField(read_only=True)
    row_version = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class StaffCreateSerializer(serializers.Serializer):
    """``POST /teaching/courses/{id}/staff`` 请求体。

    ``role`` 允许传 ``OWNER`` 以便拿到 doc 08 §六 约定的 ``OWNER_TRANSFER_BLOCKED``
    提示，而不是一个只有字段名、不知道去哪里的 400。
    """

    user_id = serializers.CharField(max_length=26, trim_whitespace=True)
    role = serializers.ChoiceField(choices=StaffRole.values, default=StaffRole.ASSISTANT)


class StaffUpdateSerializer(serializers.Serializer):
    """``PATCH /teaching/courses/{id}/staff/{staff_id}`` 请求体。

    允许传 ``REVOKED`` 以便 service 返回「请使用 revoke 接口」的 409 指引；
    真正的撤销必须走 ``revoke``，因为那条路径要检查阻断并连带失效 grant。
    """

    status = serializers.ChoiceField(choices=StaffStatus.values)


class StaffSerializer(serializers.Serializer):
    """任职输出。

    注意 ``user_id`` 同时就是路由里的 ``{staff_id}``：``courses_course_staff``
    没有 public_id，而 ``UNIQUE(course_id, user_id)`` 已使（课程，成员）唯一。
    """

    user_id = serializers.CharField(read_only=True)
    role = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    appointed_by_id = serializers.CharField(read_only=True)
    appointed_at = serializers.DateTimeField(read_only=True)
    revoked_by_id = serializers.CharField(read_only=True)
    revoked_at = serializers.DateTimeField(read_only=True)
    row_version = serializers.IntegerField(read_only=True)


class GrantCreateSerializer(serializers.Serializer):
    """``POST .../staff/{staff_id}/grants`` 请求体（doc 02 §三「需 grant」）。"""

    capability = serializers.ChoiceField(choices=StaffCapability.values)
    expires_at = serializers.DateTimeField(required=False, allow_null=True, default=None)


class GrantSerializer(serializers.Serializer):
    capability = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)
    granted_by_id = serializers.CharField(read_only=True)
    granted_at = serializers.DateTimeField(read_only=True)
    revoked_at = serializers.DateTimeField(read_only=True)
    row_version = serializers.IntegerField(read_only=True)


class TransferOwnerSerializer(serializers.Serializer):
    """``POST /teaching/courses/{id}/transfer-owner`` 请求体（doc 08 §六）。"""

    user_id = serializers.CharField(max_length=26, trim_whitespace=True)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class EnrollmentReviewSerializer(serializers.Serializer):
    """``POST .../enrollments/{eid}/review`` 请求体（doc 08 §七 审核请求）。"""

    decision = serializers.ChoiceField(choices=("APPROVE", "REJECT"))
    note = serializers.CharField(required=False, allow_blank=True, default="")


class ReasonSerializer(serializers.Serializer):
    """归档/移除等不可逆动作必须带原因，供审计追溯。"""

    reason = serializers.CharField(max_length=255, trim_whitespace=True)

    def validate_reason(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("必须给出原因", code="VALIDATION_ERROR")
        return value


class EnrollmentSerializer(serializers.Serializer):
    """名册条目输出（doc 08 §七）。"""

    public_id = serializers.CharField(read_only=True)
    student_id = serializers.CharField(read_only=True)
    cycle_no = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    application_message = serializers.CharField(read_only=True)
    applied_at = serializers.DateTimeField(read_only=True)
    reviewed_by_id = serializers.CharField(read_only=True)
    reviewed_at = serializers.DateTimeField(read_only=True)
    activated_at = serializers.DateTimeField(read_only=True)
    ended_at = serializers.DateTimeField(read_only=True)
    decision_note = serializers.CharField(read_only=True)
    end_reason = serializers.CharField(read_only=True)
    row_version = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


def course_data(data: dict[str, Any]) -> dict[str, Any]:
    """把已校验的输入裁成 service 认识的键。

    service 用 ``data`` 直接 ``,**kwargs`` 写入模型，所以这里必须裁一次：
    否则客户端多传一个字段就可能在 ``_touch`` 里写坏模型属性。
    """
    return {
        key: value for key, value in data.items() if key in COURSE_EDITABLE_FIELDS or key == "code"
    }


def course_payload(course: Course) -> dict[str, Any]:
    return CourseSerializer(course).data


def staff_payload(staff: CourseStaff) -> dict[str, Any]:
    return StaffSerializer(staff).data


def grant_payload(grant: CourseStaffGrant) -> dict[str, Any]:
    return GrantSerializer(grant).data


def enrollment_payload(enrollment: Enrollment) -> dict[str, Any]:
    return EnrollmentSerializer(enrollment).data


class BlockerReportSerializer(serializers.Serializer):
    """阻断报告（doc 08 §六 ``archive-check``、§七 ``removal-check``）。

    ``cross_domain_available=False`` 是真实介面：本阶段只能查到 courses 域内的阻断，
    experiments/provisioning/reviews 还未落地，不能假装已查完。
    """

    blockers = serializers.ListField(child=serializers.DictField(), read_only=True)
    cross_domain_available = serializers.BooleanField(read_only=True)


class EnrollmentDetailSerializer(EnrollmentSerializer):
    """详情比列表多出只追加的历史事件（doc 08 §七「详情和历史」）。"""

    events = serializers.ListField(child=serializers.DictField(), read_only=True)


# 响应信封（doc 08 §1.3）。命名与 P00 的 ``HealthResponseSerializer`` 保持一致：
# ``data`` + ``meta``，列表在 ``meta`` 里多出 page/page_size/total。
# 定义成真实类而不用 ``inline_serializer``：后者每调用一次就造一个同名不同身份的类，
# drf-spectacular 会为此报「重名组件」并丢失该操作的响应结构。


class PageMetaSerializer(TraceMetaSerializer):
    """列表信封的 ``meta``（doc 08 §1.3）。"""

    page = serializers.IntegerField(read_only=True)
    page_size = serializers.IntegerField(read_only=True)
    total = serializers.IntegerField(read_only=True)


class CourseResponseSerializer(serializers.Serializer):
    data = CourseSerializer(read_only=True)
    meta = TraceMetaSerializer(read_only=True)


class CourseListResponseSerializer(serializers.Serializer):
    data = CourseSerializer(many=True, read_only=True)
    meta = PageMetaSerializer(read_only=True)


class StaffResponseSerializer(serializers.Serializer):
    data = StaffSerializer(read_only=True)
    meta = TraceMetaSerializer(read_only=True)


class StaffListResponseSerializer(serializers.Serializer):
    data = StaffSerializer(many=True, read_only=True)
    meta = PageMetaSerializer(read_only=True)


class GrantResponseSerializer(serializers.Serializer):
    data = GrantSerializer(read_only=True)
    meta = TraceMetaSerializer(read_only=True)


class GrantListResponseSerializer(serializers.Serializer):
    data = GrantSerializer(many=True, read_only=True)
    meta = PageMetaSerializer(read_only=True)


class EnrollmentResponseSerializer(serializers.Serializer):
    data = EnrollmentDetailSerializer(read_only=True)
    meta = TraceMetaSerializer(read_only=True)


class EnrollmentListResponseSerializer(serializers.Serializer):
    data = EnrollmentSerializer(many=True, read_only=True)
    meta = PageMetaSerializer(read_only=True)


class BlockerReportResponseSerializer(serializers.Serializer):
    data = BlockerReportSerializer(read_only=True)
    meta = TraceMetaSerializer(read_only=True)
