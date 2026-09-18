from __future__ import annotations

from django.urls import path

from . import views

urlpatterns = [
    path("me/team-membership", views.MyMembershipView.as_view()),
    path("me/team-membership/applications", views.MembershipApplicationView.as_view()),
    path("me/team-membership/exit", views.MembershipExitView.as_view()),
    path("teaching/team-members", views.TeachingMembersView.as_view()),
    path(
        "teaching/team-membership-applications",
        views.TeachingApplicationsView.as_view(),
    ),
    path(
        "teaching/team-membership-applications/<int:membership_id>/review",
        views.MembershipReviewView.as_view(),
    ),
    path(
        "teaching/team-members/<int:membership_id>/remove",
        views.MembershipRemoveView.as_view(),
    ),
]
