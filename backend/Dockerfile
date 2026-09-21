ARG PYTHON_BASE_IMAGE=python:3.14-slim
FROM ${PYTHON_BASE_IMAGE} AS runtime

ARG DEBIAN_MIRROR=http://deb.debian.org/debian
ARG DEBIAN_SECURITY_MIRROR=http://deb.debian.org/debian-security

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN sed -i \
        -e "s|http://deb.debian.org/debian-security|${DEBIAN_SECURITY_MIRROR}|g" \
        -e "s|http://deb.debian.org/debian|${DEBIAN_MIRROR}|g" \
        /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install --no-install-recommends -y default-libmysqlclient-dev build-essential pkg-config curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements/base.txt /tmp/requirements.txt
RUN python -m pip install -r /tmp/requirements.txt

COPY education_experiment_platform /app
RUN addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["uvicorn", "education_experiment_platform.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
