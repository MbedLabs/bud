# Operating Bud

A practical guide for running Bud in production: monitoring, logs, backup and
restore, upgrades, and disaster recovery. Runtime configuration lives in
environment variables — see [`.env.example`](../.env.example) for the full list.

## Image tags

Images are published to `ghcr.io/mbedlabs/bud`:

| Tag | Moves? | Use for |
|---|---|---|
| `sha-<commit>` | immutable | exact reproducibility / debugging |
| `1.2.3` (full semver) | immutable | **production — pin this** |
| `1.2`, `1` | moving (stable releases) | tracking a minor/major line |
| `stable` | moving → newest stable release | low-maintenance production |
| `latest` | moving → newest `main` build | **development / staging only** |

Set `BUD_VERSION` in `.env` to a pinned version (e.g. `1.2.3`) or `stable`.
Never run `latest` in production — it is the rolling development build. `stable`
starts existing once you publish your first `vX.Y.Z` release tag.

## Health checks

- `GET /api/health` — **liveness**. Reports only that the API process is up; it
  does not touch PostgreSQL, so it never claims a database connection it has not
  verified. Use it for a cheap "is the process alive?" signal.
- `GET /api/ready` — **readiness**. Runs `SELECT 1` against PostgreSQL and returns
  `200` only when the database is reachable, `503` otherwise. This is what the
  container `HEALTHCHECK` and `docker-compose` healthcheck probe, and it is the
  right target for load-balancer / orchestrator readiness checks.

## Sessions and tokens

Two independent token lifetimes, tunable via environment variables (no code change):

- **User sessions** — `ACCESS_TOKEN_EXPIRE_MINUTES` (default `10080`, i.e. 7 days).
  The bearer token a browser receives at login. Seven days favours convenience;
  if a leaked token's exposure window matters more than staying signed in,
  shorten it (e.g. `1440` for 24h). Users are re-prompted to log in once both the
  access and refresh sessions expire.
- **Runner tokens** — `RUNNER_TOKEN_EXPIRE_HOURS` (default `2160`, i.e. 90 days).
  Issued at runner registration and intentionally long-lived; a runner stays
  usable for heartbeat/results while its `last_heartbeat` is within
  `RUNNER_HEARTBEAT_TIMEOUT`. This is separate from user sessions above.

## Logs

Bud writes logs to stdout so any container log driver or shipper picks them up.

| Variable | Default | Meaning |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Root log level (`DEBUG`, `INFO`, `WARNING`, ...) |
| `LOG_JSON` | auto | `true`/`false`. Unset: JSON in production (`BUD_ENV=production`), text otherwise |

JSON mode emits one object per line:

```json
{"ts": "2026-07-17T02:00:00+0000", "level": "INFO", "logger": "bud.access",
 "message": "GET /api/health 200 1.2ms", "request_id": "6f6e...",
 "method": "GET", "path": "/api/health", "route": "/health",
 "status": 200, "duration_ms": 1.2}
```

Every response carries an `X-Request-ID` header. Incoming `X-Request-ID`
values are propagated, so you can trace a request across a reverse proxy,
Bud, and your log aggregator. Pass the header from your edge (nginx:
`proxy_set_header X-Request-ID $request_id;`) for end-to-end correlation.

## Metrics (Prometheus)

- `GET /api/metrics` — Prometheus text format.
- `http_requests_total{method,path,status}` — request counts by route template.
- `http_request_duration_seconds{method,path}` — latency histogram.
- Plus standard Python process/GC metrics.

Scrape config:

```yaml
scrape_configs:
  - job_name: bud
    metrics_path: /api/metrics
    static_configs:
      - targets: ["bud.example.internal:8080"]
```

The endpoint is unauthenticated (the Prometheus convention). Either keep it
reachable only from your monitoring network, or disable it entirely with
`ENABLE_METRICS=false`.

## Backup and restore

Bud has two stateful locations: **PostgreSQL** and the **uploads directory**
(`UPLOAD_DIR`, default `./uploads` — test artifacts and attachments).

Nightly backup (adjust connection details to your deployment):

```bash
# database
pg_dump --format=custom --file="bud-$(date +%F).dump" "$DATABASE_URL"

# uploaded artifacts
tar czf "bud-uploads-$(date +%F).tgz" -C /path/to/uploads .
```

Restore:

```bash
pg_restore --clean --if-exists --no-owner --dbname "$DATABASE_URL" bud-YYYY-MM-DD.dump
tar xzf bud-uploads-YYYY-MM-DD.tgz -C /path/to/uploads
```

Verify after restore: `GET /api/ready` (confirms the database is reachable),
then log in and confirm recent runs and artifacts are visible.

## Artifact upload controls

`MAX_UPLOAD_SIZE_BYTES` defaults to 25 MiB and cannot exceed 100 MiB.
`MAX_RUN_UPLOAD_BYTES` defaults to 250 MiB. Bud reserves capacity before an
upload, permits one active upload per principal, rate-limits attempts, preserves
`MIN_UPLOAD_FREE_BYTES`, writes through a temporary file, and atomically promotes
only complete uploads. `ARTIFACT_RETENTION_DAYS` controls the daily retention
pass, which also removes orphaned files and expired upload reservations.

These are authorization and resource-exhaustion controls, not a malware scanner.
Add a fail-closed ClamAV or YARA stage if your deployment needs that claim.

## Upgrades

1. Back up first (see above).
2. Pull the target image: `docker pull ghcr.io/mbedlabs/bud:<version>`.
3. Run migrations before serving traffic: `alembic upgrade head`
   (run inside the new image against the production `DATABASE_URL`).
4. Restart the container. Confirm `/api/ready` returns `200` and check the
   version shown in the UI.

When upgrading to `1.0.0`, migration `006_encrypt_bloom_service_token` removes
the legacy Bloom token because it cannot be safely converted into the new scoped
encrypted credential. Create a new `test-results:write` credential in Bloom and
save it again in Bud.

Rollback: restore the pre-upgrade database dump and start the previous image
tag. Never run a newer schema against an older application version.

## Disaster recovery

- **RPO** equals your backup cadence — nightly dumps mean up to 24h of loss;
  schedule to your tolerance and copy backups off the host.
- **RTO** is dominated by Postgres restore time; rehearse the restore path
  against a scratch database at least once before you depend on it.
- Keep `SECRET_KEY`, `RUNNER_API_KEY`, and `BUD_INTEGRATION_ENCRYPTION_KEY` in your
  secret store. A different `SECRET_KEY` invalidates sessions and runner tokens,
  so runners must re-register. A different `BUD_INTEGRATION_ENCRYPTION_KEY` makes the
  stored Bloom result-sync credential unreadable, so it must be rotated.

## Supply chain

Every release build publishes an SPDX SBOM as a CI artifact
(`bud-sbom.spdx.json`) alongside the container image, and CI runs Bandit,
`pip-audit`, and blocking `npm audit` checks on every push.

Backend dependencies are pinned in [`constraints.txt`](../constraints.txt)
(generated with `pip-compile`), and both the image build and CI install with
`-c constraints.txt`, so builds are reproducible. Dependabot watches pip, npm,
Docker and GitHub Actions weekly. Refresh the pins with:

```bash
pip install pip-tools
pip-compile --strip-extras --output-file=constraints.txt pyproject.toml
```

The container runs unprivileged end to end (`USER appuser` — supervisord,
nginx on port 8080, and uvicorn), which also satisfies Kubernetes
`runAsNonRoot` policies.
