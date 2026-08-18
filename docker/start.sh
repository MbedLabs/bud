#!/bin/sh
set -eu

cat > /var/www/app/runtime-config.js <<EOF
window.runtimeConfig = {
  BUD_APP_URL: "${BUD_APP_URL:-}",
  BLOOM_APP_URL: "${BLOOM_APP_URL:-}"
};
EOF

exec /usr/local/bin/supervisord -c /etc/supervisord.conf
