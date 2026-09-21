from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.views import APIView

from apps.common.context import current_request_id
from apps.common.errors import FORBIDDEN, VALIDATION_ERROR, ApiError
from apps.common.idempotency import idempotent
from apps.common.pagination import paginate_queryset, parse_page_params
from apps.common.responses import success
from apps.identity.services.permissions import require_authenticated

from .blocking import has_blocking_items
from .constants import MEMBERSHIP_STATUS_ACTIVE, MEMBERSHIP_STATUS_PENDING
from .selectors import (
    membership_summary,
    teaching_applications,
    teaching_members,
    user_memberships,
    users_by_membership,
)
from .serializers import (
    MembershipAddSerializer,
    MembershipApplicationSerializer,
    MembershipExitSerializer,
    MembershipRemoveSerializer,
    MembershipReviewSerializer,
    serialize_application_result,
    serialize_exit_result,
    serialize_membership,
    serialize_teaching_member,
    validate_status_filter,
)
from .services import (
    apply_membership,
    direct_add_member,
    exit_membership,
    get_team_settings,
    remove_membership,
    review_application,
)


class BaseAPIView(APIView):
    authentication_classes: tuple[Any, ...] = ()
    permission_classes: tuple[Any, ...] = ()

    @csrf_exempt
    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return super().dispatch(request, *args, **kwargs)


def _json(payload: dict[str, Any], http_status: int = 200) -> JsonResponse:
    return JsonResponse(payload, status=http_status)


def _require_user_endpoint(request: HttpRequest) -> Any:
    user = require_authenticated(request)
    if user.role_code not in {"USER", "ORG_ADMIN", "ORG_SUB_ADMIN"}:
        raise ApiError(FORBIDDEN)
    return user


def _require_teaching_read(request: HttpRequest) -> Any:
    user = require_authenticated(request)
    if user.role_code not in {"ORG_ADMIN", "ORG_SUB_ADMIN"}:
        raise ApiError(FORBIDDEN)
    return user


def _require_org_admin(request: HttpRequest) -> Any:
    user = require_authenticated(request)
    if user.role_code != "ORG_ADMIN":
        raise ApiError(FORBIDDEN)
    return user


class MyMembershipView(BaseAPIView):
    def get(self, request: HttpRequest) -> JsonResponse:
        user = _require_user_endpoint(request)
        team_id = self._team_id(request)
        membership_status = request.query_params.get("status")
        if membership_status and membership_status not in {
            "PENDING",
            "ACTIVE",
            "REJECTED",
            "EXITED",
            "REMOVED",
        }:
            raise ApiError(
                VALIDATION_ERROR,
                details=[{"field": "status", "issue": "无效成员状态"}],
            )
        queryset = user_memberships(user_id=user.id, team_id=team_id, status=membership_status)
        params = parse_page_params(
            request, {"requested_at", "reviewed_at", "updated_at"}, "updated_at"
        )
        result = paginate_queryset(queryset, params, "updated_at")
        settings = get_team_settings()
        items = [
            serialize_membership(membership, settings.team_name) for membership in result.items
        ]
        blockers = has_blocking_items(user.id, operation="exit")
        has_active = any(item["status"] == MEMBERSHIP_STATUS_ACTIVE for item in items)
        has_pending = any(item["status"] == MEMBERSHIP_STATUS_PENDING for item in items)
        block_reason = None
        if has_active:
            block_reason = "ACTIVE"
        elif has_pending:
            block_reason = "PENDING"
        data = {
            "items": items,
            "page": result.page,
            "page_size": result.page_size,
            "total": result.total,
            "blocking_summary": {
                "has_active_membership": has_active,
                "has_pending_application": has_pending,
                "can_apply": not has_active and not has_pending,
                "block_reason": block_reason,
            },
            "blocking_reasons": [item.as_dict() for item in blockers],
        }
        return _json(success(data, current_request_id()))

    def _team_id(self, request: HttpRequest) -> int | None:
        value = request.query_params.get("team_id")
        if value is None:
            return None
        try:
            team_id = int(value)
        except ValueError as exc:
            raise ApiError(
                VALIDATION_ERROR,
                details=[{"field": "team_id", "issue": "必须为整数"}],
            ) from exc
        if team_id != 1:
            raise ApiError(
                VALIDATION_ERROR,
                details=[{"field": "team_id", "issue": "必须为1"}],
            )
        return team_id


@method_decorator(idempotent("membership:application"), name="post")
class MembershipApplicationView(BaseAPIView):
    def post(self, request: HttpRequest) -> JsonResponse:
        user = _require_user_endpoint(request)
        if user.role_code != "USER":
            raise ApiError(FORBIDDEN)
        serializer = MembershipApplicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        membership = apply_membership(user, data.get("message", ""), request=request)
        settings = get_team_settings()
        payload = success(
            serialize_application_result(membership, settings.team_name, data.get("message", "")),
            current_request_id(),
        )
        return _json(payload, status.HTTP_201_CREATED)


@method_decorator(idempotent("membership:exit"), name="post")
class MembershipExitView(BaseAPIView):
    def post(self, request: HttpRequest) -> JsonResponse:
        user = _require_user_endpoint(request)
        if user.role_code != "USER":
            raise ApiError(FORBIDDEN)
        serializer = MembershipExitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        membership = exit_membership(user, data.get("reason", ""), request=request)
        return _json(success(serialize_exit_result(membership), current_request_id()))


class TeachingMembersView(BaseAPIView):
    def get(self, request: HttpRequest) -> JsonResponse:
        user = _require_teaching_read(request)
        statuses = validate_status_filter(request.query_params.get("status"))
        queryset = teaching_members(
            user, statuses=statuses, keyword=request.query_params.get("keyword")
        )
        params = parse_page_params(
            request, {"requested_at", "reviewed_at", "updated_at"}, "updated_at"
        )
        result = paginate_queryset(queryset, params, "updated_at")
        settings = get_team_settings()
        users = users_by_membership(result.items)
        items = [
            serialize_teaching_member(membership, users[membership.user_id], settings.team_name)
            for membership in result.items
            if membership.user_id in users
        ]
        include_summary = request.query_params.get("include_summary", "true").lower() != "false"
        data: dict[str, Any] = {
            "items": items,
            "page": result.page,
            "page_size": result.page_size,
            "total": result.total,
        }
        if include_summary:
            data["summary"] = membership_summary(queryset)
        return _json(success(data, current_request_id()))

    @method_decorator(idempotent("membership:add"))
    def post(self, request: HttpRequest) -> JsonResponse:
        user = _require_org_admin(request)
        serializer = MembershipAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        membership = direct_add_member(user, data["username"], request=request)
        settings = get_team_settings()
        return _json(
            success(serialize_membership(membership, settings.team_name), current_request_id())
        )


class TeachingApplicationsView(BaseAPIView):
    def get(self, request: HttpRequest) -> JsonResponse:
        _require_teaching_read(request)
        membership_status = request.query_params.get("status", "PENDING")
        if membership_status not in {"PENDING", "REJECTED"}:
            raise ApiError(
                VALIDATION_ERROR,
                details=[{"field": "status", "issue": "只允许PENDING或REJECTED"}],
            )
        queryset = teaching_applications(status=membership_status)
        params = parse_page_params(request, {"requested_at", "reviewed_at"}, "requested_at")
        params_asc = type(params)(
            page=params.page, page_size=params.page_size, sort=params.sort, order="asc"
        )
        result = paginate_queryset(queryset, params_asc, "requested_at")
        settings = get_team_settings()
        items = [
            serialize_membership(membership, settings.team_name) for membership in result.items
        ]
        return _json(
            success(
                {
                    "items": items,
                    "page": result.page,
                    "page_size": result.page_size,
                    "total": result.total,
                },
                current_request_id(),
            )
        )


@method_decorator(idempotent("membership:review"), name="post")
class MembershipReviewView(BaseAPIView):
    def post(self, request: HttpRequest, membership_id: int) -> JsonResponse:
        user = _require_org_admin(request)
        serializer = MembershipReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        membership = review_application(
            user,
            membership_id,
            data["action"],
            data.get("review_note", ""),
            request=request,
        )
        settings = get_team_settings()
        return _json(
            success(serialize_membership(membership, settings.team_name), current_request_id())
        )


@method_decorator(idempotent("membership:remove"), name="post")
class MembershipRemoveView(BaseAPIView):
    def post(self, request: HttpRequest, membership_id: int) -> JsonResponse:
        user = _require_org_admin(request)
        serializer = MembershipRemoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        membership = remove_membership(user, membership_id, data.get("reason", ""), request=request)
        settings = get_team_settings()
        return _json(
            success(serialize_membership(membership, settings.team_name), current_request_id())
        )
