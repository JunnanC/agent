"""按 actor / portal / course 裁剪的读模型（doc 02 §一）。

两个不变式：

* selector 是数据范围的**唯一**查询入口。视图不直接 ``Course.objects``，
  否则新增一处遗漏就是一处越权。
* 不可见对象返回 ``RESOURCE_NOT_FOUND`` 而不是 403：403 会告诉调用方
  「这个 ID 存在但你看不到」，等于免费提供了一个枚举探测器（doc 08 §1.5）。
"""

from __future__ import annotations

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.core.errors import COURSE_GRANT_REQUIRED, RESOURCE_NOT_FOUND, ApiError

from .models import (
    Course,
    CourseStaff,
    CourseStaffGrant,
    Enrollment,
    EnrollmentStatus,
    GrantStatus,
    StaffRole,
    StaffStatus,
)
from .ports import Actor


def teaching_course_queryset(actor: Actor) -> QuerySet[Course]:
    """actor 在教师端可见的课程。

    包含 SUSPENDED 任职：被暂停的教师仍应看到自己的课程历史，
    只是所有写操作会被 capability 检查拦下。
    """
    return (
        Course.objects.filter(staff__user_id=actor.ref)
        .exclude(staff__status=StaffStatus.REVOKED)
        .distinct()
    )


def list_teaching_courses(
    actor: Actor,
    *,
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Course], int]:
    queryset = teaching_course_queryset(actor)
    if status:
        queryset = queryset.filter(status=status)
    if keyword:
        queryset = queryset.filter(Q(title__icontains=keyword) | Q(code__icontains=keyword))
    queryset = queryset.order_by("-updated_at", "-id")
    total = queryset.count()
    offset = (page - 1) * page_size
    return list(queryset[offset : offset + page_size]), total


def get_teaching_course(actor: Actor, course_public_id: str) -> Course:
    course = teaching_course_queryset(actor).filter(public_id=course_public_id).first()
    if course is None:
        raise ApiError(RESOURCE_NOT_FOUND, detail={"course_id": course_public_id})
    return course


def staff_of(course: Course, user_ref: str) -> CourseStaff | None:
    return CourseStaff.objects.filter(course=course, user_id=user_ref).first()


def get_staff(course: Course, staff_ref: str) -> CourseStaff:
    """按**成员账号 public_id** 取任职，不用自增主键（doc 08 §1.1）。

    ``UNIQUE(course_id, user_id)`` 使（课程，成员）天然唯一，因此成员账号就是稳定的对外标识；
    撤销后重新任命也不会换 ID，避免客户端保存一个转瞬失效的数值。
    """
    staff = CourseStaff.objects.filter(course=course, user_id=staff_ref).first()
    if staff is None:
        raise ApiError(RESOURCE_NOT_FOUND, detail={"staff_ref": staff_ref})
    return staff


def active_owner(course: Course) -> CourseStaff | None:
    return CourseStaff.objects.filter(
        course=course, role=StaffRole.OWNER, status=StaffStatus.ACTIVE
    ).first()


def require_owner(actor: Actor, course: Course) -> CourseStaff:
    """负责人专属操作。NOT 用 capability：助教无论如何都不能被授予 OWNER 语义。"""
    staff = staff_of(course, actor.ref)
    if staff is None or staff.role != StaffRole.OWNER or staff.status != StaffStatus.ACTIVE:
        raise ApiError(
            COURSE_GRANT_REQUIRED,
            detail={"course_id": course.public_id, "capability": "COURSE_OWNER"},
        )
    return staff


def active_capabilities(course_staff: CourseStaff) -> set[str]:
    """有效能力集合。过期 grant 视同不生效，判定不能只依赖 status 字段。"""
    now = timezone.now()
    rows = CourseStaffGrant.objects.filter(
        course_staff=course_staff, status=GrantStatus.ACTIVE
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    return set(rows.values_list("capability", flat=True))


def require_capability(actor: Actor, course: Course, capability: str) -> CourseStaff:
    """doc 02 §三「需 grant」：OWNER 天然拥有全部能力，助教必须有有效 grant。"""
    staff = staff_of(course, actor.ref)
    if staff is None or staff.status != StaffStatus.ACTIVE:
        raise ApiError(
            COURSE_GRANT_REQUIRED,
            detail={"course_id": course.public_id, "capability": str(capability)},
        )
    if staff.role == StaffRole.OWNER:
        return staff
    if str(capability) not in active_capabilities(staff):
        raise ApiError(
            COURSE_GRANT_REQUIRED,
            detail={"course_id": course.public_id, "capability": str(capability)},
        )
    return staff


def roster(
    course: Course,
    *,
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Enrollment], int]:
    queryset = Enrollment.objects.filter(course=course)
    if status:
        queryset = queryset.filter(status=status)
    if keyword:
        queryset = queryset.filter(student_id__icontains=keyword)
    # 待审批优先且按申请时间最早优先（doc 01 §五：审批队列语义），其余按最近更新。
    queryset = queryset.order_by("applied_at", "id")
    total = queryset.count()
    offset = (page - 1) * page_size
    return list(queryset[offset : offset + page_size]), total


def get_enrollment(course: Course, enrollment_public_id: str) -> Enrollment:
    enrollment = Enrollment.objects.filter(course=course, public_id=enrollment_public_id).first()
    if enrollment is None:
        raise ApiError(RESOURCE_NOT_FOUND, detail={"enrollment_id": enrollment_public_id})
    return enrollment


def active_enrollment_count(course: Course) -> int:
    return Enrollment.objects.filter(course=course, status=EnrollmentStatus.ACTIVE).count()


def next_cycle_no(course: Course, student_ref: str) -> int:
    """同一学生重新选同一门课产生新的周期号（doc 01 §一 原则 3）。

    调用方必须已锁定 ``(course, student)`` 现有行；并发仍由
    ``UNIQUE(course, student, cycle_no)`` 兜底。
    """
    latest = (
        Enrollment.objects.filter(course=course, student_id=student_ref)
        .order_by("-cycle_no")
        .values_list("cycle_no", flat=True)
        .first()
    )
    return (latest or 0) + 1
