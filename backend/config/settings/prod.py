from config.env import ConfigurationError, optional_bool, require_str

from .base import *

ALLOWED_HOSTS = [
    host.strip() for host in require_str("DJANGO_ALLOWED_HOSTS").split(",") if host.strip()
]
if not ALLOWED_HOSTS:
    raise ConfigurationError("DJANGO_ALLOWED_HOSTS must contain at least one host")

DEBUG = False
PORTAL_TRUST_PROXY_ENABLED = optional_bool("PORTAL_TRUST_PROXY_ENABLED", True)
if not PORTAL_TRUST_PROXY_ENABLED:
    raise ConfigurationError("Production portal requests require a trusted proxy")
