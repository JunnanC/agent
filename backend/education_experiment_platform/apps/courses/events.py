"""课程领域事件（doc 01 §十）。

载荷只含 opaque ID、状态、必要摘要和 trace_id；禁止证件原值、Session、
工作区票据、签名 URL、完整报告内容。事件名与载荷在这里构造一次，
service 只引用常量，避免同一事件在多个调用点出现不同拼写。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # 避免运行期导入循环：events 只在类型标注中引用模型
    from .models import Course, Enrollment

COURSE_CREATED = "course.created"
COURSE_PUBLISHED = "course.published"
COURSE_CLOSED = "course.closed"
COURSE_ARCHIVED = "course.archived"
COURSE_STAFF_CHANGED = "course.staff.changed"

ENROLLMENT_APPLIED = "enrollment.applied"
ENROLLMENT_ACTIVATED = "enrollment.activated"
ENROLLMENT_REJECTED = "enrollment.rejected"
ENROLLMENT_ENDED = "enrollment.ended"

AGGREGATE_COURSE = "course"
AGGREGATE_ENROLLMENT = "enrollment"


def course_payload(course: Course, *, trace_id: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "course_id": course.public_id,
        "status": course.status,
        "trace_id": trace_id,
    }
    payload.update(extra)
    return payload


def enrollment_payload(enrollment: Enrollment, *, trace_id: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "enrollment_id": enrollment.public_id,
        "course_id": enrollment.course.public_id,
        "student_id": enrollment.student_id,
        "status": enrollment.status,
        "trace_id": trace_id,
    }
    payload.update(extra)
    return payload
