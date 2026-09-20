from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ApiSessionAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "core.authentication.ApiSessionAuthentication"
    name = "sessionAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": "sessionid",
        }
