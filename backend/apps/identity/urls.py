from django.urls import path

from . import views

urlpatterns = [
    path("auth/login", views.LoginView.as_view()),
    path("auth/refresh", views.RefreshView.as_view()),
    path("auth/logout", views.LogoutView.as_view()),
    path("auth/me", views.MeView.as_view()),
    path("admin/users", views.AdminUserListView.as_view()),
    path("admin/users/<int:user_id>", views.AdminUserUpdateView.as_view()),
    path("admin/permissions", views.PermissionMatrixView.as_view()),
    path("admin/user-quotas/<int:user_id>", views.UserQuotaView.as_view()),
]
