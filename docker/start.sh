#!/bin/sh
set -eu

APP_USER=appuser
APP_UID="$(id -u "$APP_USER")"
APP_GID="$(id -g "$APP_USER")"
RUN_DIR=/run/bud

# /run is recreated on Cloudron boot, and using it in every environment keeps
# one image/startup path honest.
mkdir -p "$RUN_DIR" \
  /run/nginx/body /run/nginx/proxy /run/nginx/fastcgi /run/nginx/uwsgi /run/nginx/scgi
chown -R "$APP_UID:$APP_GID" "$RUN_DIR" /run/nginx

if [ -n "${CLOUDRON_APP_ORIGIN:-}" ]; then
  : "${CLOUDRON_APP_DOMAIN:?Cloudron did not provide CLOUDRON_APP_DOMAIN}"
  : "${CLOUDRON_POSTGRESQL_URL:?Cloudron did not provide PostgreSQL}"

  mkdir -p /app/data/uploads
  chown "$APP_UID:$APP_GID" /app/data /app/data/uploads

  secrets_file=/app/data/secrets.env
  if [ ! -f "$secrets_file" ]; then
    echo "==> first run: generating persistent Bud secrets"
    umask 077
    {
      printf 'SECRET_KEY=%s\n' "$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
      printf 'RUNNER_API_KEY=%s\n' "$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
      printf 'BUD_INTEGRATION_ENCRYPTION_KEY=%s\n' "$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
    } > "$secrets_file"
    chown "$APP_UID:$APP_GID" "$secrets_file"
  fi
  set -a
  # shellcheck disable=SC1090
  . "$secrets_file"
  set +a

  DATABASE_URL="$(printf '%s' "$CLOUDRON_POSTGRESQL_URL" | sed 's#^postgres://#postgresql://#')"
  export DATABASE_URL

  if [ -n "${CLOUDRON_MAIL_SMTP_SERVER:-}" ]; then
    export SMTP_ENABLED=true
    export SMTP_HOST="$CLOUDRON_MAIL_SMTP_SERVER"
    export SMTP_USERNAME="${CLOUDRON_MAIL_SMTP_USERNAME:-}"
    export SMTP_PASSWORD="${CLOUDRON_MAIL_SMTP_PASSWORD:-}"
    export SMTP_FROM_EMAIL="${CLOUDRON_MAIL_FROM:?Cloudron mail sender missing}"
    export SMTP_SSL=false
    # The port and the TLS mode have to agree. Cloudron's relay offers STARTTLS
    # only on CLOUDRON_MAIL_STARTTLS_PORT (2587); CLOUDRON_MAIL_SMTP_PORT (2525)
    # is plaintext and answers a STARTTLS command with "extension not supported",
    # which surfaced as a 500 on every invite. Prefer the encrypted port and
    # fall back to plaintext only when the platform does not offer one.
    if [ -n "${CLOUDRON_MAIL_STARTTLS_PORT:-}" ]; then
      export SMTP_PORT="$CLOUDRON_MAIL_STARTTLS_PORT"
      export SMTP_STARTTLS=true
    else
      export SMTP_PORT="${CLOUDRON_MAIL_SMTP_PORT:?Cloudron SMTP port missing}"
      export SMTP_STARTTLS=false
    fi
  else
    export SMTP_ENABLED=false
  fi

  export BUD_ENV=production
  export APP_BASE_URL="$CLOUDRON_APP_ORIGIN"
  export FRONTEND_BASE_URL="$CLOUDRON_APP_ORIGIN"
  export BUD_APP_URL="$CLOUDRON_APP_ORIGIN"
  export BUD_UPLOAD_DIR=/app/data/uploads
  export ENABLE_DOCS=false
  export LOG_JSON=true
  export RUN_STARTUP_DATA_REPAIR=false
  export AUTO_SEED_ADMIN=false

  # These satisfy the production guard but are never seeded. The operator
  # creates the only initial administrator through /setup.
  export ADMIN_EMAIL="admin@$CLOUDRON_APP_DOMAIN"
  export ADMIN_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

  echo "==> applying Bud database migrations"
  gosu "$APP_USER" alembic upgrade head
else
  mkdir -p /app/uploads
  chown "$APP_UID:$APP_GID" /app/uploads
fi

cat > "$RUN_DIR/runtime-config.js" <<EOF
window.runtimeConfig = {
  BUD_APP_URL: "${BUD_APP_URL:-}",
  BLOOM_APP_URL: "${BLOOM_APP_URL:-}"
};
EOF
chown "$APP_UID:$APP_GID" "$RUN_DIR/runtime-config.js"

exec /usr/local/bin/supervisord -c /etc/supervisord.conf
