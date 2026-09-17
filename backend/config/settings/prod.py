from config.env import ConfigurationError, require_str

from .base import *

ALLOWED_HOSTS = [
    host.strip() for host in require_str("DJANGO_ALLOWED_HOSTS").split(",") if host.strip()
]
if not ALLOWED_HOSTS:
    raise ConfigurationError("DJANGO_ALLOWED_HOSTS must contain at least one host")

DEBUG = False
