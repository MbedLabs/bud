# Operating Bud

A practical guide for running Bud in production: monitoring, logs, backup and
restore, upgrades, and disaster recovery. Runtime configuration lives in
environment variables; see [`.env.example`](../.env.example) for the full list.

## Image tags

Images are published to `ghcr.io/mbedlabs/bud`:

| Tag | Moves? | Use for |
|---|---|---|
| `sha-<commit>` | immutable | exact reproducibility / debugging |
| `1.2.3` (full semver) | immutable | **production: pin this** |
| `1.2`, `1` | moving (stable releases) | tracking a minor/major line |
| `stable` | moving → newest stable release | low-maintenance production |
| `latest` | moving → newest `main` build | **development / staging only** |

Set `BUD_VERSION` in `.env` to a pinned version (e.g. `1.2.3`) or `stable`.
Never run `latest` in production: it is the rolling development build. `stable`
starts existing once you publish your first `vX.Y.Z` release tag.

## Health checks

- `GET /api/health`: **liveness**. Reports only that the API process is up; it
  does not touch PostgreSQL, so it never claims a database connection it has not
  verified. Use it for a cheap "is the process alive?" signal.
- `GET /api/ready`: **readiness**. Runs `SELECT 1` against PostgreSQL and returns
  `200` only when the database is reachable, `503` otherwise. This is what the
  container `HEALTHCHECK` and `docker-compose` healthcheck probe, and it is the
  right target for load-balancer / orchestrator readiness checks.

## Sessions and tokens

Two independent token lifetimes, tunable via environment variables (no code change):

- **User sessions**: `ACCESS_TOKEN_EXPIRE_MINUTES` (default `10080`, i.e. 7 days).
  The bearer token a browser receives at login. Seven days favours convenience;
  if a leaked token's exposure window matters more than staying signed in,
  shorten it (e.g. `1440` for 24h). Users are re-prompted to log in once both the
  access and refresh sessions expire.
- **Runner tokens**: `RUNNER_TOKEN_EXPIRE_HOURS` (default `2160`, i.e. 90 days).
  Issued at runner registration and intentionally long-lived; a runner stays
  usable for heartbeat/results while its `last_heartbeat` is within
  `RUNNER_HEARTBEAT_TIMEOUT`. This is separate from user sessions above.

## Roles, policies and groups

Every user has a base role, chosen when they are invited:

- **Viewer** reads everything and changes nothing. The Viewer role is meant for internal
  viewers.
- **Developer** is Viewer plus queuing custom runs on the Test Stations and publishing a
  run's report to Bloom.
- **Admin** holds every permission. Admin is chosen when a user is created or invited; an
  existing user is never promoted to it, and an Admin's role is never changed. Managing
  users and their accounts, deleting runs and artifacts, and confirming an Admin's own email
  change stay with the Admin base role and are never given through a group.

A **policy** is the set of rights for one area of Bud: Results, Custom runs, Publish to
Bloom, Stations, Products, Settings and integrations, Audit log and Access management. A
**group** is a named bundle of policies. A user can have several groups; their access is
the base role's allowance plus every policy of every group. A group only adds.

Bud ships five groups: Results Viewers, Test Operators (Results, Custom runs, Publish to
Bloom), Station Managers (Results, Stations), Access Managers (Station Managers plus Access
management) and Application Administrators (every policy). Shipped groups and policies cannot be
changed; duplicate one to make an editable copy. A group that manages stations is given
only to users with the Admin or Developer base role. Only an Admin gives Application Administrators and
edits policies. Someone with Access management gives, creates and edits only groups whose
policies they hold themselves.

Access is not scoped by products or stations: every user sees every product.

**Access** in the sidebar has Assignments for group rosters, Groups for policy bundles,
Policies for Read/Write controls and Requests for access requests. Users is a separate
account-management page. A user without Publish to Bloom finds
Request access in its place on a run; Admins and Access managers are emailed and grant it
by giving a group that holds Publish to Bloom.

Test Stations create execution records, report their status and counters, and submit raw
results using their station credentials. These submissions are limited to the station's
own runs. Human sessions, including Administrator, cannot submit those execution records.
Users request queued work through **Custom Run**.

A custom-run request contains the selected test classes and assigned Test Station.
It appears in the station's request queue and links to an execution record after
that station claims it. Queued requests are excluded from run reports and dashboard
execution totals. The station executes the selection in its local test workspace,
uploads results and artifacts, and acknowledges completion with its process exit
code. Dashboard totals and completion notifications wait for that acknowledgement; an
unavailable selected class or another execution error counts as a failed run even
when no test results were produced. Completion retries retain the original terminal
answer and do not record it twice.

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

- `GET /api/metrics`: Prometheus text format.
- `http_requests_total{method,path,status}`: request counts by route template.
- `http_request_duration_seconds{method,path}`: latency histogram.
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
(`BUD_UPLOAD_DIR`, with `UPLOAD_DIR` as an unprefixed alias). The supplied
Compose deployment uses `/app/uploads` and persists it in the `bud-uploads`
named volume. A non-Compose deployment must mount durable storage at its
configured path.

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
`MAX_RUN_UPLOAD_BYTES` defaults to 250 MiB. A runner creates a `TestRun` for a
suite execution and may attach multiple artifacts to it: the first setting caps
each file, and the second caps the combined committed and reserved bytes for
that run. The aggregate boundary is the run, not the suite name, so separate
executions of the same named suite receive separate run budgets.

Bud reserves run capacity before an upload. `UPLOADS_PER_15_MINUTES` and
`MAX_CONCURRENT_UPLOADS_PER_PRINCIPAL` apply per authenticated runner or user
principal; different runners therefore have independent request allowances.
These request controls do not shrink the per-run byte budget. Bud also preserves
`MIN_UPLOAD_FREE_BYTES`, writes through a temporary file, and atomically
promotes only complete uploads. `ARTIFACT_RETENTION_DAYS` controls the daily
retention pass, which also removes orphaned files and expired reservations.

These are authorization and resource-exhaustion controls, not a malware scanner.
Add a fail-closed ClamAV or YARA stage if your deployment needs that claim.

## Object storage (S3)

Run artifacts are kept in `BUD_UPLOAD_DIR` by default. To keep them in an
S3-compatible bucket (AWS S3, MinIO, Hetzner, Ceph) instead:

- `BUD_STORAGE_BACKEND=s3` and `BUD_S3_BUCKET`. The bucket must exist.
- `BUD_S3_ENDPOINT_URL` for anything that is not AWS (for MinIO, for example
  `http://minio:9000`); `BUD_S3_REGION` where the store needs one.
- `BUD_S3_PREFIX` (default `bud`) keeps several instances apart in one bucket.
- `BUD_S3_ACCESS_KEY_ID` and `BUD_S3_SECRET_ACCESS_KEY`, or neither, in which
  case the ambient AWS credentials (an instance role) are used.
- `BUD_STORAGE_LOCAL_MIRROR` (default `true`) also keeps every file in
  `BUD_UPLOAD_DIR`. Reads come from the bucket and fall back to the mirror when the
  bucket does not answer; the log then names the key as a warning. The free-space
  reserve applies to this directory; quotas in the bucket are the operator's.

Existing files are copied with `python -m app.storage migrate --to s3`. Each file
keeps its storage name under the prefix, sizes are checked after the copy, and files
already in the bucket are skipped, so the command can be run again. The local files
stay where they are.

`GET /api/ready` reports `storage`: `local`, `s3`, or `s3-unreachable` when the bucket
did not answer. It stays `200` in that case, because the database decides readiness
and reads can still come from the mirror. Orphan cleanup lists the bucket; a file is
counted missing when the bucket lacks it. On Cloudron the variables are set with
`cloudron env set`; keep the mirror, as it lives under `/app/data` and is part of
Cloudron's backup.

## Audit log

Every HTTP request, health probes, metrics scrapes and Test Station heartbeats included, leaves one `api.request` event in the `audit_events` table. It is written on its own database session once the response is finished; a failed write is logged and never changes the response. Its actor is the signed-in user, with `details.client` set to `cli` for a token issued through CLI sign-in and `web` otherwise; `runner` for a Test Station token or an enrolment key bound to a station, with the station's id in `details.runner_id`; or `anonymous`. Its details hold the method, the route template (`route`), the `path`, the HTTP `status`, `duration_ms`, the names of the query parameters (`query_params`, never their values), the kind of credential presented (`auth`: `bearer`, `api-key` or `none`) and, for a `201` answer whose JSON body has an `id`, that id (`created_id`), or, when the body has no `id` and has a `test_run_id` (a results upload), that run id (`created_test_run_id`). A CORS preflight (`OPTIONS` with `Access-Control-Request-Method`) that the CORS settings allow is answered by the CORS layer in front of the audit and leaves no event; the request it precedes is recorded. A preflight the CORS settings refuse, from a foreign origin or asking for a method or header outside the allowed ones, is answered `403` and recorded as a `denied` event, which counts toward repeated refusals. No request or response body and no header value is stored. A `product_id` path parameter fills `product_id`, and the last path parameter ending in `_id` fills the target. The outcome is `success` below 400, `denied` for 401, 403 and 429 and for a 404 answered to an anonymous caller, and `failure` otherwise, a 404 to a signed-in user or a Test Station included. A deactivated user or station refused with 403 is named as the actor.

When one client address has `AUDIT_REFUSAL_THRESHOLD` (default 20) denied requests within `AUDIT_REFUSAL_WINDOW_MINUTES` (default 10), one `security.repeated_refusals` event is written for that address, at most once per window, with the number of denied requests, the threshold and the window in its details.

Security-relevant events are also written to the `audit_events` table in the same transaction as the action: sign-in, sign-out, session refresh, password change and reset, email verification and email change; user creation, invitation, role change, activation, deletion; groups, station registration, enrolment keys and station removal; configuration changes; deletions, exports, imports and attachments. A failed sign-in or password reset is recorded even though the request itself fails. Each event carries the acting user or `anonymous`/`service`/`runner`, the action, the target, the request id (the `x-request-id` response header), the client address and user agent, the outcome and details without secrets.

Users with the `audit.view` permission read the log under Audit log in the sidebar, or with `GET /api/audit`. Every Admin has it; any other user has it through a group with a policy that grants it, such as the shipped Audit log policy, which the shipped Application Administrators group includes. Filters: `actor_user_id`, `actor_type`, `action` or an action prefix ending in `.`, `target_type`, `target_id`, `product_id`, `outcome`, `ip`, `request_id`, `status` (the HTTP status of `api.request` events), `since`, `until`; paging: `limit` (1 to 500, default 50) and `offset`. Each event also carries the names of its target, of the object a `201` answer created and of the acting Test Station (`target_label`, `created_label`, `station_name`) for runs, products, Test Stations, users, groups, policies, enrolment keys, notification channels, artifacts and results, and `target_deleted`, `created_deleted` or `station_deleted` when that object no longer exists; the stored event keeps the id. No endpoint changes or deletes an event.

The client address is the one the image's own nginx received: nginx appends it to `X-Forwarded-For`, and uvicorn, started with `--forwarded-allow-ips 127.0.0.1,::1` whatever `FORWARDED_ALLOW_IPS` holds, takes from that header the right-most address other than `127.0.0.1` and `::1`. A request that reaches nginx from `127.0.0.1`, the container's own loopback (another process in the container or pod, a port forward) is treated as part of the image, so the `X-Forwarded-For` it carries is read as well. Behind another reverse proxy (Cloudron, a Kubernetes ingress, a load balancer) that is the proxy's address, the same for every caller, unless the proxy is trusted with `TRUSTED_PROXY_NETWORKS`.

`TRUSTED_PROXY_NETWORKS` (also read as `BUD_TRUSTED_PROXY_NETWORKS`) is a JSON array of the networks, in CIDR notation, that your reverse proxies connect from. When a request reaches the image's nginx from an address in one of them, the client address is the right-most `X-Forwarded-For` address outside those networks; addresses inside them are skipped as further proxies. A request from any other address outside the container keeps that address, whatever `X-Forwarded-For` it carries, so a forged header from such a sender never changes the recorded address. The default is empty: no forwarding header from outside the container is trusted and the client address is the one nginx received. Example, a reverse proxy on a private network:

```
TRUSTED_PROXY_NETWORKS=["10.10.0.0/16"]
```

An entry that is not a network address, such as `10.10.0.1/16` instead of `10.10.0.0/16`, stops Bud at start. List only the networks your proxies use: any host inside them can name another client address. The resolved address is the one the audit log stores as `ip`, the one `security.repeated_refusals` counts by and the one the per-address request rate limits (sign-in, for example) count by. On Cloudron the setting is set with `cloudron env set`.

Access requests are emailed through the transactional mail settings to every active Admin and every active user with `access.manage` other than the requester, with a link to Access, where they are listed under Requests with the name of the run each was made from. Only Publish to Bloom can be requested; someone who already holds it, every Admin and Developer included, is refused with 409 and nothing is emailed. When the email cannot be sent (SMTP is disabled or not fully configured, or the send fails), the request is still recorded and listed there, and the user is told the email could not be sent.

Retention is the operator's choice. Every request adds a row, so the table grows with traffic: one Test Station's heartbeat alone adds 1440 rows a day, the image's own health check, every 30 seconds, adds 2880, and every metrics scrape and CORS preflight adds one more. The application never deletes events; to remove old ones, run on a schedule:

```
python -m app.audit prune --older-than-days 365
```

## Upgrades

1. Back up first (see above).
2. Pull the target image: `docker pull ghcr.io/mbedlabs/bud:<version>`.
3. Run migrations before serving traffic: `alembic upgrade head`
   (run inside the new image against the production `DATABASE_URL`).
4. Restart the container. Confirm `/api/ready` returns `200` and check the
   version shown in the UI.

When upgrading to `1.0.0`, any legacy Bloom token is removed because it cannot be
safely converted into the new scoped encrypted credential. Create a new
`test-results:write` credential in Bloom and save it again in Bud.

The migration history was collapsed into a single locked baseline at `1.0.0`.
Databases already at `1.0.0` are recognised as up to date and are not
re-migrated. Upgrading a database created before `1.0.0` is not supported:
restore it into a `1.0.0` deployment from a dump instead.

Rollback: restore the pre-upgrade database dump and start the previous image
tag. Never run a newer schema against an older application version.

## Disaster recovery

- **RPO** equals your backup cadence: nightly dumps mean up to 24h of loss;
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

Backend dependencies, the CI tools and supervisor are pinned with their
hashes in [`uv.lock`](../uv.lock). CI and the image build install from it with
hash checks and without building any source distribution
(`uv sync --frozen --no-build`, and `uv pip install --require-hashes --no-build`
from `uv export` in the image), so builds are reproducible. CI checks that the
lock matches `pyproject.toml` with `uv lock --check --no-build`. Dependabot
watches uv, npm, Docker and GitHub Actions weekly. Refresh the pins with:

```bash
uv lock --upgrade --no-build
```

The container starts as root only to prepare its runtime directories, the
ownership of its data and of its standard output and error streams and, on
Cloudron, the persistent secrets and the database migrations. It then runs
everything as `appuser`: supervisord, nginx on port 8080 (master and
workers), and uvicorn. Because the start needs root, Kubernetes
`runAsNonRoot` policies are not supported.
