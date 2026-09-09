FROM --platform=$BUILDPLATFORM node:24-alpine AS ui-build

WORKDIR /ui

COPY ui/package.json ui/package-lock.json ./
RUN npm ci

COPY ui/ ./
RUN npm run build

FROM python:3.11-slim AS backend-build

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE constraints.txt ./
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini ./
RUN pip install --no-cache-dir -c constraints.txt . "supervisor==4.3.0" \
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
# Included from the server block and from every location that sets a header of
# its own: nginx drops inherited add_header directives at those levels.
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
      -e 's#^[[:space:]]*user[[:space:]].*#user appuser;#' \
      /etc/nginx/nginx.conf \
    && rm -f /var/www/app/runtime-config.js \
    && ln -s /run/bud/runtime-config.js /var/www/app/runtime-config.js

# PID 1 prepares Cloudron's writable mounts, then supervisord/nginx drop their
# application-facing processes to appuser. The same image is used everywhere.
USER root

EXPOSE 8080

# Readiness (not liveness): reports healthy only once the database is reachable.
# Generous start-period covers first-boot schema creation before probing begins.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD curl -f http://localhost:8080/api/ready || exit 1

CMD ["/bin/sh", "/usr/local/bin/start-product"]
