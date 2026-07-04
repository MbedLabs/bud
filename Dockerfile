FROM node:20-alpine AS ui-build

WORKDIR /ui

COPY ui/package.json ui/package-lock.json ./
RUN npm ci

COPY ui/ ./
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    libpq-dev \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini ./
RUN pip install --no-cache-dir .

COPY docker/nginx.conf /etc/nginx/sites-enabled/default
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY docker/start.sh /usr/local/bin/start-product
COPY --from=ui-build /ui/dist /var/www/app

RUN chmod +x /usr/local/bin/start-product \
    && useradd -m appuser \
    && mkdir -p /app/uploads /run/nginx /var/lib/nginx /var/log/nginx /var/log/supervisor \
    && chown -R appuser:appuser /app /var/www/app /run/nginx /var/lib/nginx /var/log/nginx

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD curl -f http://localhost:8080/api/health || exit 1

CMD ["/usr/local/bin/start-product"]
