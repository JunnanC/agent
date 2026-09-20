from django.urls import include, path


urlpatterns = [
    path("api/v2/", include("education_experiment_platform.api_urls")),
]

handler400 = "apps.core.middleware.bad_request"
