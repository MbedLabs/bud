FROM --platform=$BUILDPLATFORM node:24-alpine AS ui-build

WORKDIR /ui

COPY ui/package.json ui/package-lock.json ./
RUN npm ci --ignore-scripts

COPY ui/ ./
RUN npm run build

FROM python:3.11-slim AS backend-build

COPY --from=ghcr.io/astral-sh/uv:0.11.14@sha256:1025398289b62de8269e70c45b91ffa37c373f38118d7da036fb8bb8efc85d97 /uv /bin/uv

WORKDIR /build

COPY pyproject.toml README.md LICENSE uv.lock ./
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini ./
RUN uv export --frozen --no-dev --no-emit-project --group image \
      --format requirements-txt --output-file /tmp/requirements.txt \
    && uv pip install --system --no-build --require-hashes --compile-bytecode --no-cache \
      -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt \
    && pip uninstall --yes pip setuptools wheel

FROM debian:trixie-slim

LABEL org.opencontainers.image.licenses="LicenseRef-EmbedLabs-Source-Available-1.0" \
      org.opencontainers.image.source="https://github.com/MbedLabs/bud"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gosu \
    nginx \
    && rm -rf /var/lib/apt/lists/*

COPY --from=backend-build /usr/local /usr/local
COPY --from=backend-build /build /app

COPY --chmod=0644 docker/nginx.conf /etc/nginx/sites-enabled/default
COPY --chmod=0644 docker/security-headers.conf /etc/nginx/security-headers.conf
COPY --chmod=0644 docker/runtime-paths.conf /etc/nginx/conf.d/runtime-paths.conf
COPY --chmod=0644 docker/supervisord.conf /etc/supervisord.conf
COPY --chmod=0755 docker/start.sh /usr/local/bin/start-product
COPY --from=ui-build /ui/dist /var/www/app

RUN useradd -m appuser \
    && mkdir -p /app/uploads /run/nginx /var/lib/nginx /var/log/nginx /var/log/supervisor \
    && chown -R appuser:appuser /app /var/www/app /run/nginx /var/lib/nginx /var/log/nginx /var/log/supervisor \
    && chmod 0755 /usr/local/bin/start-product \
    && chmod 0644 /etc/supervisord.conf /etc/nginx/sites-enabled/default /etc/nginx/security-headers.conf /etc/nginx/conf.d/runtime-paths.conf \
    && sed -i \
      -e 's#^pid .*#pid /run/nginx/nginx.pid;#' \
      -e 's#^[[:space:]]*error_log[[:space:]].*#error_log /dev/stderr warn;#' \
      -e 's#^[[:space:]]*access_log[[:space:]].*#access_log /dev/stdout;#' \
      -e '/^[[:space:]]*user[[:space:]]/d' \
      /etc/nginx/nginx.conf \
    && rm -f /var/www/app/runtime-config.js \
    && ln -s /run/bud/runtime-config.js /var/www/app/runtime-config.js

USER root

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD curl -f http://localhost:8080/api/ready || exit 1

CMD ["/bin/sh", "/usr/local/bin/start-product"]
