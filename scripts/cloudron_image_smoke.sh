#!/usr/bin/env bash
# Prove that the normal product image satisfies Cloudron's runtime contract.
set -euo pipefail

IMAGE="${1:?usage: cloudron_image_smoke.sh <image-ref> <bloom|bud>}"
APP_KIND="${2:?usage: cloudron_image_smoke.sh <image-ref> <bloom|bud>}"
PLATFORM="${CLOUDRON_TEST_PLATFORM:-linux/amd64}"

case "$APP_KIND" in
  bloom)
    DATA_DIR=/app/data/attachments
    PEER_ENV=BUD_APP_URL
    PEER_URL=https://bud.cloudron.test
    ;;
  bud)
    DATA_DIR=/app/data/uploads
    PEER_ENV=BLOOM_APP_URL
    PEER_URL=https://bloom.cloudron.test
    ;;
  *)
    echo "unsupported app kind: $APP_KIND" >&2
    exit 2
    ;;
esac

SUFFIX="$$"
NET="${APP_KIND}-cloudron-smoke-net-${SUFFIX}"
PG="${APP_KIND}-cloudron-smoke-pg-${SUFFIX}"
APP="${APP_KIND}-cloudron-smoke-app-${SUFFIX}"
PGVOL="${APP_KIND}-cloudron-smoke-pgdata-${SUFFIX}"
DATAVOL="${APP_KIND}-cloudron-smoke-data-${SUFFIX}"

DB_USER=cloudron_test
DB_PASSWORD=cloudron-test-password
DB_NAME="cloudron_${APP_KIND}"
ADMIN_EMAIL="owner-${APP_KIND}@example.com"
ADMIN_PASSWORD=CloudronOwnerPassword-123456
BASE=""
APP_PORT=""

log() { printf '\n==> %s\n' "$*"; }
fail() { printf '\nFAIL: %s\n' "$*" >&2; exit 1; }

cleanup() {
  local code=$?
  if [ "$code" -ne 0 ]; then
    docker logs "$APP" 2>&1 | tail -120 || true
  fi
  docker rm -f "$APP" "$PG" >/dev/null 2>&1 || true
  docker volume rm "$PGVOL" "$DATAVOL" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

json_field() {
  python3 -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"
}

wait_for_postgres() {
  for _ in $(seq 1 30); do
    docker exec "$PG" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1 && return 0
    sleep 2
  done
  fail "PostgreSQL never became ready"
}

refresh_base() {
  local binding
  binding="$(docker port "$APP" 8080/tcp | head -n 1)"
  APP_PORT="${binding##*:}"
  [ -n "$APP_PORT" ] || fail "Docker did not allocate an app port"
  BASE="http://127.0.0.1:${APP_PORT}"
}

wait_for_app() {
  for _ in $(seq 1 60); do
    curl -fsS "${BASE}/api/ready" >/dev/null 2>&1 && return 0
    [ "$(docker inspect -f '{{.State.Running}}' "$APP" 2>/dev/null || true)" = true ] \
      || fail "normal image exited under Cloudron constraints"
    sleep 2
  done
  fail "normal image never became ready under Cloudron constraints"
}

start_app() {
  local publish=127.0.0.1::8080
  if [ -n "$APP_PORT" ]; then publish="127.0.0.1:${APP_PORT}:8080"; fi
  docker run -d --name "$APP" --network "$NET" --platform "$PLATFORM" \
    --read-only \
    --tmpfs /run:rw,exec,nosuid,size=64m \
    --tmpfs /tmp:rw,exec,nosuid,size=64m \
    -v "${DATAVOL}:/app/data" \
    -p "$publish" \
    -e "CLOUDRON_APP_ORIGIN=https://${APP_KIND}.cloudron.test" \
    -e "CLOUDRON_APP_DOMAIN=${APP_KIND}.cloudron.test" \
    -e "CLOUDRON_POSTGRESQL_URL=postgres://${DB_USER}:${DB_PASSWORD}@${PG}:5432/${DB_NAME}" \
    -e "${PEER_ENV}=${PEER_URL}" \
    "$IMAGE" >/dev/null
  refresh_base
}

login() {
  curl -fsS -X POST "${BASE}/api/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}" \
    | json_field access_token
}

log "Starting PostgreSQL"
docker network create "$NET" >/dev/null
docker run -d --name "$PG" --network "$NET" \
  -v "${PGVOL}:/var/lib/postgresql/data" \
  -e "POSTGRES_USER=${DB_USER}" \
  -e "POSTGRES_PASSWORD=${DB_PASSWORD}" \
  -e "POSTGRES_DB=${DB_NAME}" \
  postgres:16 >/dev/null
wait_for_postgres

log "Booting the normal image with Cloudron's read-only filesystem"
start_app
wait_for_app

log "Checking first-run setup and runtime peer link"
[ "$(curl -fsS "${BASE}/api/setup/status" | json_field setup_required)" = True ] \
  || fail "fresh Cloudron instance did not require setup"
curl -fsS "${BASE}/runtime-config.js" | grep -F "$PEER_URL" >/dev/null \
  || fail "runtime-config.js did not contain ${PEER_ENV}"

curl -fsS -X POST "${BASE}/api/setup" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\",\"full_name\":\"Cloudron Owner\"}" \
  >/dev/null
[ -n "$(login)" ] || fail "first administrator could not sign in"

log "Checking persistent layout and secrets"
docker exec "$APP" test -d "$DATA_DIR" || fail "$DATA_DIR was not created"
docker exec "$APP" test -f /app/data/secrets.env || fail "persistent secrets file was not created"
secret_digest="$(docker exec "$APP" sha256sum /app/data/secrets.env | awk '{print $1}')"

log "Recreating the app with the same PostgreSQL and /app/data volumes"
docker rm -f "$APP" >/dev/null
start_app
wait_for_app
[ "$(curl -fsS "${BASE}/api/setup/status" | json_field setup_required)" = False ] \
  || fail "setup reopened after container recreation"
[ -n "$(login)" ] || fail "administrator login did not survive recreation"
[ "$(docker exec "$APP" sha256sum /app/data/secrets.env | awk '{print $1}')" = "$secret_digest" ] \
  || fail "persistent secrets changed across recreation"

log "PASS: the normal ${APP_KIND} image is Cloudron compatible"
