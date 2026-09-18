from __future__ import annotations

import uuid
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.views import APIView

from apps.common.context import current_request_id, current_trace_id
from apps.common.errors import UNAUTHENTICATED, ApiError
from apps.common.idempotency import idempotent
from apps.common.responses import accepted, paginated, success

from .serializers import (
    AdminUserSerializer,
    CreateUserSerializer,
    LoginSerializer,
    QuotaSerializer,
    RefreshSerializer,
    UpdateUserSerializer,
    UserSummarySerializer,
)
from .services.admin_users import create_user, update_user
from .services.audit import audit_identity
from .services.auth import login, logout, refresh
from .services.permissions import require_authenticated, require_system_admin
from .services.quotas import get_quota, update_quota
from .tasks import import_users


class BaseAPIView(APIView):
    authentication_classes: tuple[Any, ...] = ()
    permission_classes: tuple[Any, ...] = ()

    @csrf_exempt
    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return super().dispatch(request, *args, **kwargs)


def _json(payload: dict[str, Any], http_status: int = 200) -> JsonResponse:
    return JsonResponse(payload, status=http_status)


class LoginView(BaseAPIView):
    def post(self, request: HttpRequest) -> JsonResponse:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = login(**serializer.validated_data)
        from .services.membership import get_membership

        membership = get_membership(result["user"].id)
        return _json(
            success(
                {
                    "access_token": result["access_token"],
                    "refresh_token": result["refresh_token"],
                    "expires_in": result["expires_in"],
                    "token_type": result["token_type"],
                    "user": UserSummarySerializer(
                        result["user"], context={"membership": membership}
                    ).data,
                },
                current_request_id(),
            )
        )


class RefreshView(BaseAPIView):
    def post(self, request: HttpRequest) -> JsonResponse:
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return _json(
            success(refresh(serializer.validated_data["refresh_token"]), current_request_id())
        )


@method_decorator(idempotent("identity:logout"), name="post")
class LogoutView(BaseAPIView):
    def post(self, request: HttpRequest) -> JsonResponse:
        try:
            logout(request)
        except ApiError as exc:
            if exc.error != UNAUTHENTICATED:
                raise
        return _json(success(None, current_request_id()))


class MeView(BaseAPIView):
    def get(self, request: HttpRequest) -> JsonResponse:
        user = require_authenticated(request)
        from .services.membership import get_membership

        membership = get_membership(user.id)
        data = UserSummarySerializer(user, context={"membership": membership}).data
        return _json(success(data, current_request_id()))


class AdminUserListView(BaseAPIView):
    def get(self, request: HttpRequest) -> JsonResponse:
        require_system_admin(request)
        from apps.common.pagination import paginate_queryset, parse_page_params

        from .selectors import admin_users

        params = parse_page_params(request, {"created_at", "updated_at", "username"}, "created_at")
        result = paginate_queryset(
            admin_users(
                keyword=request.query_params.get("keyword"),
                role=request.query_params.get("role"),
                status=request.query_params.get("status"),
            ),
            params,
            "created_at",
        )
        items = [AdminUserSerializer(user).data for user in result.items]
        return _json(
            paginated(items, result.page, result.page_size, result.total, current_request_id())
        )

    @method_decorator(idempotent("identity:admin-users"))
    def post(self, request: HttpRequest) -> JsonResponse:
        actor = require_system_admin(request)
        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["mode"] == "single":
            user = create_user(actor.id, data)
            audit_identity(
                request,
                action="admin.user.created",
                target_type="USER",
                target_id=str(user.id),
                result="SUCCESS",
                after={"role_id": user.role_id},
            )
            return _json(
                success(AdminUserSerializer(user).data, current_request_id()),
                status.HTTP_201_CREATED,
            )
        operation_id = str(uuid.uuid4())
        import_users.delay(actor.id, data["import_file_key"])
        return _json(
            accepted(operation_id, current_trace_id(), current_request_id(), "PROCESSING"),
            status.HTTP_202_ACCEPTED,
        )


@method_decorator(idempotent("identity:admin-user-update"), name="patch")
class AdminUserUpdateView(BaseAPIView):
    def patch(self, request: HttpRequest, user_id: int) -> JsonResponse:
        actor = require_system_admin(request)
        serializer = UpdateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = update_user(actor, user_id, serializer.validated_data)
        audit_identity(
            request,
            action="admin.user.updated",
            target_type="USER",
            target_id=str(user.id),
            result="SUCCESS",
            before={"status": user.status},
            after={"status": user.status, "role_id": user.role_id},
        )
        return _json(success(AdminUserSerializer(user).data, current_request_id()))


class PermissionMatrixView(BaseAPIView):
    def get(self, request: HttpRequest) -> JsonResponse:
        require_system_admin(request)
        from .selectors import permission_matrix

        matrix = permission_matrix(
            role_code=request.query_params.get("role_code"),
            resource=request.query_params.get("resource"),
        )
        total_permissions = sum(len(row["permissions"]) for row in matrix)
        return _json(
            success(
                {
                    "matrix": matrix,
                    "total_roles": len(matrix),
                    "total_permissions": total_permissions,
                },
                current_request_id(),
            )
        )


class UserQuotaView(BaseAPIView):
    def get(self, request: HttpRequest, user_id: int) -> JsonResponse:
        require_system_admin(request)
        return _json(success(QuotaSerializer(get_quota(user_id)).data, current_request_id()))

    @method_decorator(idempotent("identity:admin-user-quota"))
    def patch(self, request: HttpRequest, user_id: int) -> JsonResponse:
        require_system_admin(request)
        max_values = {
            key: int(value) for key, value in request.data.items() if key.startswith("max_")
        }
        quota = update_quota(user_id, {key[4:]: value for key, value in max_values.items()})
        audit_identity(
            request,
            action="admin.user_quota.updated",
            target_type="USER_QUOTA",
            target_id=str(user_id),
            result="SUCCESS",
        )
        return _json(success(QuotaSerializer(quota).data, current_request_id()))
