import os

from celery import Celery
from celery.signals import before_task_publish, task_postrun, task_prerun

from apps.core.tracing import (
    bind_celery_queue,
    bind_trace_context,
    clear_trace_context,
    new_trace_id,
    trace_headers,
    trace_id_from_traceparent,
)


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "education_experiment_platform.settings.local")

app = Celery("education_experiment_platform")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@before_task_publish.connect
def propagate_trace_headers(sender=None, headers=None, **kwargs):
    if headers is not None:
        headers.update(trace_headers())


@task_prerun.connect
def bind_worker_trace_context(task=None, **kwargs):
    headers = (task.request.headers or {}) if task else {}
    delivery_info = (task.request.delivery_info or {}) if task else {}
    traceparent = headers.get("traceparent", "")
    trace_id = trace_id_from_traceparent(traceparent) or new_trace_id()
    queue = delivery_info.get("routing_key")
    bind_trace_context(trace_id=trace_id, portal=None)
    bind_celery_queue(queue)


@task_postrun.connect
def clear_worker_trace_context(task=None, **kwargs):
    clear_trace_context()
