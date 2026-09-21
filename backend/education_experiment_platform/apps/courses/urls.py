"""教师端课程路由（doc 08 §六、§七 的路径表）。

前缀 ``/api/v2/teaching/`` 由 ``education_experiment_platform/api_urls.py`` 挂载，
app 内部只声明相对段，避免前缀在两处硬编码后漂移。

路径参数都不是自增主键（doc 08 §1.1）：

* ``{course_id}`` —— 课程 ``public_id``
* ``{staff_id}``  —— 成员**账号** public_id。``courses_course_staff`` 没有 public_id，
  而 ``UNIQUE(course_id, user_id)`` 已保证「课程 + 成员」唯一，因此账号就是稳定标识。
* ``{enrollment_id}`` —— 选课周期 ``public_id``
"""

from django.urls import path

from . import views

app_name = "teaching"

urlpatterns = [
    path("courses", views.TeachingCourseListCreateView.as_view(), name="course-list"),
    path(
        "courses/<str:course_id>",
        views.TeachingCourseDetailView.as_view(),
        name="course-detail",
    ),
    path(
        "courses/<str:course_id>/publish",
        views.TeachingCoursePublishView.as_view(),
        name="course-publish",
    ),
    path(
        "courses/<str:course_id>/close",
        views.TeachingCourseCloseView.as_view(),
        name="course-close",
    ),
    path(
        "courses/<str:course_id>/archive-check",
        views.TeachingCourseArchiveCheckView.as_view(),
        name="course-archive-check",
    ),
    path(
        "courses/<str:course_id>/archive",
        views.TeachingCourseArchiveView.as_view(),
        name="course-archive",
    ),
    path(
        "courses/<str:course_id>/transfer-owner",
        views.TeachingCourseTransferOwnerView.as_view(),
        name="course-transfer-owner",
    ),
    path(
        "courses/<str:course_id>/staff",
        views.TeachingStaffListCreateView.as_view(),
        name="staff-list",
    ),
    path(
        "courses/<str:course_id>/staff/<str:staff_id>",
        views.TeachingStaffDetailView.as_view(),
        name="staff-detail",
    ),
    path(
        "courses/<str:course_id>/staff/<str:staff_id>/grants",
        views.TeachingStaffGrantListCreateView.as_view(),
        name="staff-grant-list",
    ),
    path(
        "courses/<str:course_id>/staff/<str:staff_id>/revoke",
        views.TeachingStaffRevokeView.as_view(),
        name="staff-revoke",
    ),
    path(
        "courses/<str:course_id>/enrollments",
        views.TeachingEnrollmentListView.as_view(),
        name="enrollment-list",
    ),
    path(
        "courses/<str:course_id>/enrollments/<str:enrollment_id>",
        views.TeachingEnrollmentDetailView.as_view(),
        name="enrollment-detail",
    ),
    path(
        "courses/<str:course_id>/enrollments/<str:enrollment_id>/review",
        views.TeachingEnrollmentReviewView.as_view(),
        name="enrollment-review",
    ),
    path(
        "courses/<str:course_id>/enrollments/<str:enrollment_id>/removal-check",
        views.TeachingEnrollmentRemovalCheckView.as_view(),
        name="enrollment-removal-check",
    ),
    path(
        "courses/<str:course_id>/enrollments/<str:enrollment_id>/remove",
        views.TeachingEnrollmentRemoveView.as_view(),
        name="enrollment-remove",
    ),
]
