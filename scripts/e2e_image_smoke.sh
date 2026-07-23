#!/usr/bin/env bash
#
# End-to-end smoke test against a *published* Bud image.
#
# Proves the release-blocking path the unit suite cannot, using real named
# volumes and a full container teardown/recreate (not just a restart):
#   empty named-volume PostgreSQL
#     -> `alembic upgrade head` builds the schema on the real image (before the
#        app boots; RUN_STARTUP_DATA_REPAIR=false, so no create_all rescue)
#     -> `alembic current` is at head (migrations are complete on their own)
#     -> app boots against the migrated schema
#     -> admin can log in; a database-backed API call works
#     -> a >1 MB artifact upload succeeds THROUGH nginx (client_max_body_size)
#     -> BOTH containers are removed and recreated with the SAME named volumes
#     -> the database records still exist and the artifact's bytes + SHA-256
#        survive (the uploads volume persisted)
#     -> /api/health is liveness-only; /api/ready confirms the database
#
# Usage:
#   scripts/e2e_image_smoke.sh <image-ref>
#
# Requires: docker, curl, python3, sha256sum. No repo checkout of the app is
# needed — the published image supplies the application and alembic.
set -euo pipefail

IMAGE="${1:?usage: e2e_image_smoke.sh <image-ref>}"
PLATFORM="${E2E_PLATFORM:-linux/amd64}"
APP_PORT="${E2E_APP_PORT:-}"
BASE=""

SUFFIX="$$"
NET="bud-e2e-net-${SUFFIX}"
PG="bud-e2e-pg-${SUFFIX}"
APP="bud-e2e-app-${SUFFIX}"
PGVOL="bud-e2e-pgdata-${SUFFIX}"
UPVOL="bud-e2e-uploads-${SUFFIX}"

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
  # Production-path migration test: the app must NOT build or repair the schema.
  # alembic (run explicitly below, before the app boots) is the only schema
  # builder, so a missing/incomplete migration fails instead of being rescued by
  # create_all().
  -e "RUN_STARTUP_DATA_REPAIR=false"
  -e "ENABLE_DOCS=false"
)

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
fail() { printf '\n\033[1;31mFAIL:\033[0m %s\n' "$*" >&2; exit 1; }

cleanup() {
  local code=$?
  [ "$code" = 0 ] || { log "Dumping app logs (exit ${code})"; docker logs "$APP" 2>&1 | tail -80 || true; }
  docker rm -f "$APP" "$PG" >/dev/null 2>&1 || true
  docker volume rm "$PGVOL" "$UPVOL" >/dev/null 2>&1 || true
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

start_pg() {
  # Reuses the named PGVOL so data survives a container recreate.
  docker run -d --name "$PG" --network "$NET" \
    -v "${PGVOL}:/var/lib/postgresql/data" \
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
}

start_app() {
  # Reuses the named UPVOL so uploaded artifacts survive a container recreate.
  local publish="127.0.0.1::8080"
  if [ -n "$APP_PORT" ]; then publish="127.0.0.1:${APP_PORT}:8080"; fi
  docker run -d --name "$APP" --network "$NET" \
    -p "$publish" \
    -v "${UPVOL}:/app/uploads" \
    --platform "$PLATFORM" \
    "${ENV_ARGS[@]}" \
    "$IMAGE" >/dev/null
  refresh_base
}

login_token() {
  curl -fsS -X POST "${BASE}/api/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}" | json_field access_token
}

log "Using image: ${IMAGE}"
docker network create "$NET" >/dev/null

log "Starting an empty named-volume PostgreSQL"
start_pg

log "Applying alembic upgrade head against the published image (before the app boots)"
docker run --rm --network "$NET" --platform "$PLATFORM" \
  "${ENV_ARGS[@]}" \
  --entrypoint alembic "$IMAGE" upgrade head

log "Verifying the database is at alembic head (migrations are complete on their own)"
current="$(docker run --rm --network "$NET" --platform "$PLATFORM" \
  "${ENV_ARGS[@]}" \
  --entrypoint alembic "$IMAGE" current 2>&1)"
echo "    ${current}"
printf '%s' "$current" | grep -q '(head)' \
  || fail "database is not at alembic head after upgrade (migration incomplete)"

log "Booting the application container (schema already built by alembic; no create_all)"
start_app
wait_ready "on first boot"

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
token="$(login_token)"
[ -n "$token" ] || fail "login returned no access_token"

log "Database-backed API call (list products)"
curl -fsS "${BASE}/api/products" -H "Authorization: Bearer ${token}" >/dev/null \
  || fail "authenticated products listing failed"

log "Uploading a >1 MB artifact through nginx (exercises client_max_body_size)"
upload_file="$(mktemp)"
head -c 2097152 /dev/zero | tr '\0' 'A' > "$upload_file"   # 2 MiB, well over nginx's 1 MB default
upload_sha="$(sha256sum "$upload_file" | awk '{print $1}')"
artifact_id="$(curl -fsS -X POST "${BASE}/api/uploads" \
  -H "Authorization: Bearer ${token}" \
  -F "file=@${upload_file};type=text/plain;filename=e2e.txt" | json_field id)"
rm -f "$upload_file"
[ -n "$artifact_id" ] || fail "upload did not return an artifact id"
echo "    uploaded artifact id = ${artifact_id}, sha256 = ${upload_sha}"

log "Removing BOTH containers and recreating them with the SAME named volumes"
docker rm -f "$APP" "$PG" >/dev/null
start_pg
# No alembic re-run: the schema and data live in the persistent PGVOL.
start_app
wait_ready "after container recreation"

log "Database records must still exist (re-login uses the persisted admin row)"
token="$(login_token)"
[ -n "$token" ] || fail "admin login failed after recreation (database did not persist)"
curl -fsS "${BASE}/api/uploads/info/${artifact_id}" -H "Authorization: Bearer ${token}" >/dev/null \
  || fail "artifact ${artifact_id} row did not persist across recreation"

log "Downloading the artifact and verifying its bytes + SHA-256"
downloaded="$(mktemp)"
curl -fsS "${BASE}/api/uploads/${artifact_id}" -H "Authorization: Bearer ${token}" -o "$downloaded" \
  || fail "artifact ${artifact_id} bytes did not persist across recreation"
download_sha="$(sha256sum "$downloaded" | awk '{print $1}')"
rm -f "$downloaded"
[ "$download_sha" = "$upload_sha" ] \
  || fail "artifact SHA-256 mismatch after recreation: uploaded ${upload_sha}, got ${download_sha}"
echo "    verified sha256 = ${download_sha}"

log "PASS: Bud published image survives full container recreation with named volumes"
