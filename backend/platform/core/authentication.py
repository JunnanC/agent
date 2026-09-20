from rest_framework.authentication import SessionAuthentication


class ApiSessionAuthentication(SessionAuthentication):
    """Session authentication that reports missing credentials as HTTP 401."""

    def authenticate_header(self, request) -> str:
        return "Session"
