#!/usr/bin/env bash
#
# End-to-end smoke test against a *published* Bud image.
#
# Proves the release-blocking path the unit suite cannot:
#   empty database
#     -> container boots and builds its schema
#     -> `alembic upgrade head` applies cleanly on the real image
#     -> admin can log in
#     -> a database-backed API call works
#     -> a >1 MB artifact upload succeeds THROUGH nginx
#        (i.e. client_max_body_size is configured; nginx's 1 MB default would 413)
#     -> after a container restart the uploaded artifact still exists
#     -> /api/health is liveness-only (never falsely reports database "connected")
#     -> /api/ready reports the database connected
#
# Usage:
#   scripts/e2e_image_smoke.sh <image-ref>
#
# Requires: docker, curl, python3. No repo checkout of the app is needed — the
# published image supplies the application and alembic.
set -euo pipefail

IMAGE="${1:?usage: e2e_image_smoke.sh <image-ref>}"
PLATFORM="${E2E_PLATFORM:-linux/amd64}"
APP_PORT="${E2E_APP_PORT:-}"
BASE=""

SUFFIX="$$"
NET="bud-e2e-net-${SUFFIX}"
PG="bud-e2e-pg-${SUFFIX}"
APP="bud-e2e-app-${SUFFIX}"

DB_USER="e2e_user"
DB_PASSWORD="e2e-strong-db-password-not-a-default"
DB_NAME="e2e_bud"
DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${PG}:5432/${DB_NAME}"

ADMIN_EMAIL="e2e-admin@e2e.example.com"
ADMIN_PASSWORD="E2eAdminPassword-1234567"   # >= 16 chars, non-default

# Production-grade secrets so the fail-closed config accepts them.
ENV_ARGS=(
  -e "BUD_ENV=production"
  -e "DATABASE_URL=${DATABASE_URL}"
  -e "SECRET_KEY=e2e-secret-key-that-is-definitely-long-enough-0123456789"
  -e "RUNNER_API_KEY=e2e-runner-api-key-that-is-at-least-32-chars-0001"
  -e "ADMIN_EMAIL=${ADMIN_EMAIL}"
  -e "ADMIN_PASSWORD=${ADMIN_PASSWORD}"
  -e "ADMIN_FULL_NAME=E2E Admin"
  -e "AUTO_SEED_ADMIN=true"
  -e "RUN_STARTUP_DATA_REPAIR=true"
  -e "ENABLE_DOCS=false"
)

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
fail() { printf '\n\033[1;31mFAIL:\033[0m %s\n' "$*" >&2; exit 1; }

cleanup() {
  local code=$?
  [ "$code" = 0 ] || { log "Dumping app logs (exit ${code})"; docker logs "$APP" 2>&1 | tail -80 || true; }
  docker rm -f "$APP" "$PG" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

json_field() { python3 -c 'import sys,json;print(json.load(sys.stdin)["'"$1"'"])'; }

refresh_base() {
  local port_binding
  port_binding="$(docker port "$APP" 8080/tcp | head -n 1)"
  APP_PORT="${port_binding##*:}"
  [ -n "$APP_PORT" ] || fail "Docker did not allocate an application port"
  BASE="http://127.0.0.1:${APP_PORT}"
}

wait_ready() {
  local what="$1"
  for _ in $(seq 1 60); do
    if curl -fsS "${BASE}/api/ready" >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  fail "app never became ready ${what}"
}

log "Using image: ${IMAGE}"
docker network create "$NET" >/dev/null

log "Starting an empty PostgreSQL"
docker run -d --name "$PG" --network "$NET" \
  -e "POSTGRES_USER=${DB_USER}" \
  -e "POSTGRES_PASSWORD=${DB_PASSWORD}" \
  -e "POSTGRES_DB=${DB_NAME}" \
  postgres:16 >/dev/null
for _ in $(seq 1 30); do
  docker exec "$PG" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1 && break
  sleep 2
done
docker exec "$PG" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1 \
  || fail "postgres never became ready"

log "Booting the application container (builds schema on an empty DB)"
PUBLISH_ADDR="127.0.0.1::8080"
if [ -n "$APP_PORT" ]; then PUBLISH_ADDR="127.0.0.1:${APP_PORT}:8080"; fi
docker run -d --name "$APP" --network "$NET" \
  -p "$PUBLISH_ADDR" \
  --platform "$PLATFORM" \
  "${ENV_ARGS[@]}" \
  "$IMAGE" >/dev/null
refresh_base
wait_ready "on first boot"

log "Applying alembic upgrade head against the published image"
docker run --rm --network "$NET" --platform "$PLATFORM" \
  "${ENV_ARGS[@]}" \
  --entrypoint alembic "$IMAGE" upgrade head

log "/api/health must be liveness-only (never claim database \"connected\")"
health="$(curl -fsS "${BASE}/api/health")"
echo "    health = ${health}"
printf '%s' "$health" | grep -q '"connected"' \
  && fail "/api/health falsely reports the database connected"
printf '%s' "$health" | grep -q '"status":"healthy"' \
  || fail "/api/health did not report healthy"

log "/api/ready must confirm the database"
ready="$(curl -fsS "${BASE}/api/ready")"
echo "    ready = ${ready}"
printf '%s' "$ready" | grep -q '"database":"connected"' \
  || fail "/api/ready did not confirm the database"

log "Admin login"
token="$(curl -fsS -X POST "${BASE}/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}" | json_field access_token)"
[ -n "$token" ] || fail "login returned no access_token"

log "Database-backed API call (list products)"
curl -fsS "${BASE}/api/products" -H "Authorization: Bearer ${token}" >/dev/null \
  || fail "authenticated products listing failed"

log "Uploading a >1 MB artifact through nginx (exercises client_max_body_size)"
upload_file="$(mktemp)"
head -c 2097152 /dev/zero | tr '\0' 'A' > "$upload_file"   # 2 MiB, well over nginx's 1 MB default
artifact_id="$(curl -fsS -X POST "${BASE}/api/uploads" \
  -H "Authorization: Bearer ${token}" \
  -F "file=@${upload_file};type=text/plain;filename=e2e.txt" | json_field id)"
rm -f "$upload_file"
[ -n "$artifact_id" ] || fail "upload did not return an artifact id"
echo "    uploaded artifact id = ${artifact_id}"

log "Restarting the container to prove persistence"
docker restart "$APP" >/dev/null
refresh_base
wait_ready "after restart"

log "Re-login and confirm the artifact survived the restart"
token="$(curl -fsS -X POST "${BASE}/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}" | json_field access_token)"
curl -fsS "${BASE}/api/uploads/info/${artifact_id}" -H "Authorization: Bearer ${token}" >/dev/null \
  || fail "artifact ${artifact_id} did not persist across restart"

log "PASS: Bud published image is end-to-end healthy"
