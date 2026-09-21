from .base import *  # noqa: F403

SECRET_KEY = "test-only-secret-key"
DEBUG = False
ALLOWED_HOSTS = [
    "testserver",
    "localhost",
    "127.0.0.1",
    "user.localhost",
    "teacher.localhost",
    "admin.localhost",
]
TRUSTED_PROXY_CIDRS = ["127.0.0.0/8"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
