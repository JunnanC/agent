# Backend

The canonical Django project root is `backend/`. Install dependencies from `requirements.txt`, then run checks with:

```powershell
$env:SECRET_KEY="local-check-secret"
$env:DJANGO_SETTINGS_MODULE="education_experiment_platform.settings.local"
python manage.py check
```

Local serving must use ASGI because later SSE endpoints require streaming:

```powershell
uvicorn education_experiment_platform.asgi:application --host 127.0.0.1 --port 8000
```

Do not validate SSE behavior with a WSGI synchronous container.
