"""课程聚合根、教学团队与选课周期（doc 01 §四/§五，doc 07 §五/§六）。

表名、列名、唯一键与索引严格对齐 doc 07。doc 07 未定义列集合的三张只追加事件表
（``courses_course_staff_event`` / ``courses_course_staff_grant_event`` /
``courses_enrollment_event``）采用「引用 + 动作 + 前后状态 + trace」的最小集合。

两处与 doc 07 的差异，都是依赖顺序造成的，且已留好升级路径：

1. 用户引用。doc 07 要求 ``owner_id``/``user_id``/``student_id`` 为指向
   ``accounts_user`` 的外键，但 V01（accounts）尚未落地。本阶段用**同名列**存放
   ``accounts_user.public_id``（ULID 字符串）。列名与语义不变，V01 落地后改为
   ``ForeignKey(..., to_field="public_id")`` 即可。
2. ``public_id`` 的 ASCII binary collation 只在 MySQL 注入。SQLite 没有等价集合，
   声明未知 collation 会让唯一索引直接报错，因此测试库不注入。
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Case, F, Q, Value, When


def ascii_bin_kwargs() -> dict[str, str]:
    """doc 07：``public_id`` 与摘要列使用 ASCII binary collation。

    只在 MySQL 后端注入。SQLite 会为未知 collation 报
    ``no such collation sequence``，而唯一索引必然用到它。
    """
    if "mysql" in settings.DATABASES["default"]["ENGINE"]:
        return {"db_collation": "ascii_bin"}
    return {}


class CourseStatus(models.TextChoices):
    """doc 01 §四 的课程状态机取值。"""

    DRAFT = "DRAFT", "草稿"
    PUBLISHED = "PUBLISHED", "已发布"
    CLOSED = "CLOSED", "已关闭"
    ARCHIVED = "ARCHIVED", "已归档"


class CourseVisibility(models.TextChoices):
    PUBLIC = "PUBLIC", "公开"
    UNLISTED = "UNLISTED", "不公开列出"


class EnrollmentMode(models.TextChoices):
    OPEN = "OPEN", "开放选课"
    APPROVAL = "APPROVAL", "审批选课"


class StaffRole(models.TextChoices):
    OWNER = "OWNER", "负责人"
    ASSISTANT = "ASSISTANT", "助教"


class StaffStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "有效"
    SUSPENDED = "SUSPENDED", "暂停"
    REVOKED = "REVOKED", "已撤销"


class StaffCapability(models.TextChoices):
    """doc 02 §三 权限矩阵里「需 grant」的固定能力集合。

    用固定枚举而非自由字符串：权限矩阵是文档冻结的，
    自由字符串会让「隐藏接口不可调用」无法被穷举验证。
    """

    MANAGE_ENROLLMENT = "MANAGE_ENROLLMENT", "管理名册与选课审批"
    MANAGE_TEMPLATE = "MANAGE_TEMPLATE", "管理模板与版本"
    PUBLISH_EXPERIMENT = "PUBLISH_EXPERIMENT", "发布课程实验"
    REVIEW_SUBMISSION = "REVIEW_SUBMISSION", "作出审核结论"
    EXPORT_RESULT = "EXPORT_RESULT", "导出课程成果"


class GrantStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "有效"
    REVOKED = "REVOKED", "已撤销"


class EnrollmentStatus(models.TextChoices):
    """doc 01 §五 的选课周期状态。"""

    PENDING = "PENDING", "待审批"
    ACTIVE = "ACTIVE", "有效"
    REJECTED = "REJECTED", "已拒绝"
    ENDED = "ENDED", "已结束"


class Course(models.Model):
    """课程聚合根（doc 01 §四）。"""

    class Meta:
        db_table = "courses_course"
        constraints = (
            models.UniqueConstraint(fields=("code",), name="courses_course_code_uniq"),
            models.CheckConstraint(
                condition=Q(capacity__isnull=True) | Q(capacity__gt=0),
                name="courses_course_capacity_positive",
            ),
            models.CheckConstraint(
                condition=Q(enrollment_start__isnull=True)
                | Q(enrollment_end__isnull=True)
                | Q(enrollment_end__gt=F("enrollment_start")),
                name="courses_course_enrollment_window",
            ),
            models.CheckConstraint(
                condition=Q(teaching_start__isnull=True)
                | Q(teaching_end__isnull=True)
                | Q(teaching_end__gt=F("teaching_start")),
                name="courses_course_teaching_window",
            ),
        )
        indexes = (
            models.Index(
                fields=("status", "enrollment_start", "enrollment_end"),
                name="courses_course_window_idx",
            ),
            models.Index(
                fields=("owner_id", "status", "updated_at"), name="courses_course_owner_idx"
            ),
        )

    id = models.BigAutoField(primary_key=True)
    public_id = models.CharField(max_length=26, unique=True, **ascii_bin_kwargs())
    code = models.CharField(max_length=64)
    title = models.CharField(max_length=128)
    summary = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    owner_id = models.CharField(max_length=26, db_index=True)
    status = models.CharField(
        max_length=16, choices=CourseStatus.choices, default=CourseStatus.DRAFT
    )
    visibility = models.CharField(
        max_length=16, choices=CourseVisibility.choices, default=CourseVisibility.PUBLIC
    )
    enrollment_mode = models.CharField(
        max_length=16, choices=EnrollmentMode.choices, default=EnrollmentMode.OPEN
    )
    capacity = models.PositiveIntegerField(null=True, blank=True)
    enrollment_start = models.DateTimeField(null=True, blank=True)
    enrollment_end = models.DateTimeField(null=True, blank=True)
    teaching_start = models.DateTimeField(null=True, blank=True)
    teaching_end = models.DateTimeField(null=True, blank=True)
    row_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.code}({self.public_id})"


class CourseStaff(models.Model):
    """课程任职投影（doc 07 §五）。

    「课程恰有一个 ACTIVE OWNER」由 ``owner_slot`` 生成列 + 唯一约束保证；
    MySQL 不支持条件唯一索引，生成列是等价的表达方式。
    """

    class Meta:
        db_table = "courses_course_staff"
        constraints = (
            models.UniqueConstraint(
                fields=("course", "user_id"), name="courses_course_staff_course_user_uniq"
            ),
            models.UniqueConstraint(
                fields=("course", "owner_slot"), name="courses_course_staff_owner_slot_uniq"
            ),
        )
        indexes = (
            models.Index(fields=("user_id", "status", "course"), name="courses_staff_user_idx"),
            models.Index(fields=("course", "role", "status"), name="courses_staff_role_idx"),
        )

    id = models.BigAutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.RESTRICT, related_name="staff")
    user_id = models.CharField(max_length=26)
    role = models.CharField(max_length=16, choices=StaffRole.choices)
    status = models.CharField(
        max_length=16, choices=StaffStatus.choices, default=StaffStatus.ACTIVE
    )
    appointed_by_id = models.CharField(max_length=26, blank=True, default="")
    appointed_at = models.DateTimeField(null=True, blank=True)
    revoked_by_id = models.CharField(max_length=26, blank=True, default="")
    revoked_at = models.DateTimeField(null=True, blank=True)
    row_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # role='OWNER' AND status='ACTIVE' 时为 1，否则 NULL。
    # NULL 在 MySQL/SQLite 的唯一索引里互不冲突，因此助教（NULL）不受限，
    # 而 ACTIVE OWNER 每门课只能有一行。
    owner_slot = models.GeneratedField(
        expression=Case(
            When(role="OWNER", status="ACTIVE", then=Value(1)),
            default=Value(None),
            output_field=models.IntegerField(null=True),
        ),
        output_field=models.IntegerField(null=True),
        db_persist=True,
    )

    def __str__(self) -> str:
        return f"{self.course_id}:{self.user_id}:{self.role}"


class CourseStaffEvent(models.Model):
    """课程任职只追加历史（doc 07 §三）。"""

    class Meta:
        db_table = "courses_course_staff_event"
        indexes = (
            models.Index(fields=("course_staff", "id"), name="courses_staff_evt_staff_idx"),
            models.Index(fields=("course_id", "created_at"), name="courses_staff_evt_course_idx"),
        )

    id = models.BigAutoField(primary_key=True)
    course_staff = models.ForeignKey(CourseStaff, on_delete=models.RESTRICT, related_name="events")
    course_id = models.CharField(max_length=26)
    user_id = models.CharField(max_length=26)
    action = models.CharField(max_length=32)
    from_status = models.CharField(max_length=16, blank=True, default="")
    to_status = models.CharField(max_length=16, blank=True, default="")
    actor_id = models.CharField(max_length=26, blank=True, default="")
    detail = models.JSONField(default=dict)
    trace_id = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)


class CourseStaffGrant(models.Model):
    """助教固定能力授权（doc 07 §五）。"""

    class Meta:
        db_table = "courses_course_staff_grant"
        constraints = (
            models.UniqueConstraint(
                fields=("course_staff", "capability"), name="courses_staff_grant_uniq"
            ),
        )
        indexes = (models.Index(fields=("status", "expires_at"), name="courses_grant_status_idx"),)

    id = models.BigAutoField(primary_key=True)
    course_staff = models.ForeignKey(CourseStaff, on_delete=models.RESTRICT, related_name="grants")
    capability = models.CharField(max_length=32, choices=StaffCapability.choices)
    status = models.CharField(
        max_length=16, choices=GrantStatus.choices, default=GrantStatus.ACTIVE
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    granted_by_id = models.CharField(max_length=26, blank=True, default="")
    granted_at = models.DateTimeField(null=True, blank=True)
    revoked_by_id = models.CharField(max_length=26, blank=True, default="")
    revoked_at = models.DateTimeField(null=True, blank=True)
    row_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CourseStaffGrantEvent(models.Model):
    """能力授权只追加历史（doc 07 §三）。"""

    class Meta:
        db_table = "courses_course_staff_grant_event"
        indexes = (
            models.Index(fields=("course_staff_grant", "id"), name="courses_grant_evt_grant_idx"),
            models.Index(fields=("course_id", "created_at"), name="courses_grant_evt_course_idx"),
        )

    id = models.BigAutoField(primary_key=True)
    course_staff_grant = models.ForeignKey(
        CourseStaffGrant, on_delete=models.RESTRICT, related_name="events"
    )
    course_id = models.CharField(max_length=26)
    capability = models.CharField(max_length=32)
    action = models.CharField(max_length=32)
    from_status = models.CharField(max_length=16, blank=True, default="")
    to_status = models.CharField(max_length=16, blank=True, default="")
    actor_id = models.CharField(max_length=26, blank=True, default="")
    detail = models.JSONField(default=dict)
    trace_id = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)


class Enrollment(models.Model):
    """选课周期（doc 01 §五、doc 07 §六）。

    重新选同一门课产生**新的 cycle_no**，不覆盖历史（doc 01 §一 原则 3）。
    """

    class Meta:
        db_table = "courses_enrollment"
        constraints = (
            models.UniqueConstraint(
                fields=("course", "student_id", "cycle_no"), name="courses_enrollment_cycle_uniq"
            ),
            models.UniqueConstraint(
                fields=("course", "student_id", "live_slot"),
                name="courses_enrollment_live_slot_uniq",
            ),
            models.CheckConstraint(
                condition=Q(cycle_no__gt=0), name="courses_enrollment_cycle_positive"
            ),
        )
        indexes = (
            models.Index(
                fields=("course", "status", "applied_at"), name="courses_enroll_course_idx"
            ),
            models.Index(
                fields=("student_id", "status", "updated_at"), name="courses_enroll_student_idx"
            ),
        )

    id = models.BigAutoField(primary_key=True)
    public_id = models.CharField(max_length=26, unique=True, **ascii_bin_kwargs())
    course = models.ForeignKey(Course, on_delete=models.RESTRICT, related_name="enrollments")
    student_id = models.CharField(max_length=26)
    cycle_no = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=16, choices=EnrollmentStatus.choices)
    application_message = models.TextField(blank=True, default="")
    applied_at = models.DateTimeField()
    reviewed_by_id = models.CharField(max_length=26, blank=True, default="")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True, default="")
    end_reason = models.CharField(max_length=255, blank=True, default="")
    row_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # status IN ('PENDING','ACTIVE') 时为 1，否则 NULL。
    # 与 owner_slot 同理：把「条件唯一」表达成生成列 + 唯一约束。
    live_slot = models.GeneratedField(
        expression=Case(
            When(status__in=("PENDING", "ACTIVE"), then=Value(1)),
            default=Value(None),
            output_field=models.IntegerField(null=True),
        ),
        output_field=models.IntegerField(null=True),
        db_persist=True,
    )

    def __str__(self) -> str:
        return f"{self.course_id}:{self.student_id}#{self.cycle_no}"


class EnrollmentEvent(models.Model):
    """选课只追加历史（doc 07 §六）。"""

    class Meta:
        db_table = "courses_enrollment_event"
        indexes = (
            models.Index(fields=("enrollment", "id"), name="courses_enroll_evt_enroll_idx"),
            models.Index(fields=("course_id", "created_at"), name="courses_enroll_evt_course_idx"),
        )

    id = models.BigAutoField(primary_key=True)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.RESTRICT, related_name="events")
    course_id = models.CharField(max_length=26)
    student_id = models.CharField(max_length=26)
    action = models.CharField(max_length=32)
    from_status = models.CharField(max_length=16, blank=True, default="")
    to_status = models.CharField(max_length=16, blank=True, default="")
    actor_id = models.CharField(max_length=26, blank=True, default="")
    reason = models.CharField(max_length=255, blank=True, default="")
    trace_id = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
