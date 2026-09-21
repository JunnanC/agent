FROM python:3.12-slim

ARG DEBIAN_MIRROR_URL=https://mirrors.tuna.tsinghua.edu.cn/debian

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY . /app
RUN sed -i "s|http://deb.debian.org/debian|${DEBIAN_MIRROR_URL}|g" /etc/apt/sources.list.d/debian.sources \
    && sed -i "s|http://deb.debian.org/debian-security|${DEBIAN_MIRROR_URL}-security|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        pkg-config \
        default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir .

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
