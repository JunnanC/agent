from django.http import HttpRequest, HttpResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


def metrics(_request: HttpRequest) -> HttpResponse:
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
