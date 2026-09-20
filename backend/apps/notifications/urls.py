from django.urls import path

from apps.notifications.views import EventStreamView

app_name = "notifications"

urlpatterns = [
    path("events/stream", EventStreamView.as_view(), name="event-stream"),
]
