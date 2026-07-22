FROM --platform=$BUILDPLATFORM node:20-alpine AS ui-build

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

LABEL org.opencontainers.image.licenses="AGPL-3.0-only" \
      org.opencontainers.image.source="https://github.com/MbedLabs/bud"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    nginx \
    && rm -rf /var/lib/apt/lists/*

COPY --from=backend-build /usr/local /usr/local
COPY --from=backend-build /build /app

COPY --chmod=0644 docker/nginx.conf /etc/nginx/sites-enabled/default
COPY --chmod=0644 docker/supervisord.conf /etc/supervisord.conf
COPY --chmod=0755 docker/start.sh /usr/local/bin/start-product
COPY --from=ui-build /ui/dist /var/www/app

RUN useradd -m appuser \
    && mkdir -p /app/uploads /run/nginx /var/lib/nginx /var/log/nginx /var/log/supervisor \
    && chown -R appuser:appuser /app /var/www/app /run/nginx /var/lib/nginx /var/log/nginx /var/log/supervisor \
    && chown appuser:appuser /usr/local/bin/start-product \
    && chmod 0755 /usr/local/bin/start-product \
    && chmod 0644 /etc/supervisord.conf /etc/nginx/sites-enabled/default \
    && sed -i 's#^pid .*#pid /run/nginx/nginx.pid;#' /etc/nginx/nginx.conf

# Run the whole stack unprivileged: supervisord, nginx (port 8080) and uvicorn
USER appuser

EXPOSE 8080

# Readiness (not liveness): reports healthy only once the database is reachable.
# Generous start-period covers first-boot schema creation before probing begins.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD curl -f http://localhost:8080/api/ready || exit 1

CMD ["/bin/sh", "/usr/local/bin/start-product"]
