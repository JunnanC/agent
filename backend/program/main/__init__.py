"""Django project package. Celery is initialized by ``celery.py``."""

import pymysql

pymysql.install_as_MySQLdb()
