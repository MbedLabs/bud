# Bud

Bud is an open source test management and execution platform for teams that run automated tests on CI workers, lab machines, and hardware test stations. It brings runner status, test runs, assertion results, execution events, and uploaded artifacts into one self-hosted workspace.

## Container image and GitHub Packages

- **Image:** `ghcr.io/mbedlabs/bud`
- **Package:** [Bud on GitHub Packages](https://github.com/orgs/MbedLabs/packages/container/package/bud)
- **Platforms:** `linux/amd64` and `linux/arm64`

The published image contains the Bud web application and API. You do not need to compile the frontend or install Python dependencies to host Bud.

For evaluation, use `latest`. For production, pin a semantic version such as `1.0.0` so an explicit upgrade controls every change.

## What Bud provides

- A dashboard for recent test activity and connected Test Stations
- Searchable Test Runs with status, station, and location filters
- Per-run assertion summaries, detailed results, and a System Report of execution and integration events
- Registration and heartbeat monitoring for `bud_runner` execution agents
- Artifact upload and download APIs backed by persistent storage
- Admin-managed users, invitations, and viewer access
- Optional test-case execution synchronization to [Bloom](https://github.com/MbedLabs/bloom)

## Self-host in a few minutes

The checked-in [`docker-compose.yml`](docker-compose.yml) runs the published Bud image with PostgreSQL. It exposes Bud at `http://localhost:8001`, stores the database and uploads in named volumes, and does not build application source.

### Prerequisites

- Docker Engine with Docker Compose v2 (`docker compose`)
- Git, to obtain the Compose and environment files
- `openssl`, to generate secrets
- Available host port `8001` for Bud

### 1. Get the deployment files

```bash
git clone https://github.com/MbedLabs/bud.git
cd bud
cp .env.example .env
```

### 2. Configure secrets and public URLs

Generate independent values for the database password, application signing key, runner registration key, and initial admin password:

```bash
openssl rand -hex 24
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 24
```

Open `.env` and replace every active `replace-with-...` placeholder. At minimum:

- Set `DB_PASSWORD` to the generated database password.
- Set `SECRET_KEY` to the 64-character signing key. Keep it stable across upgrades and restores.
- Set `RUNNER_API_KEY` to a separate 64-character registration secret.
- Set `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `ADMIN_FULL_NAME` for the first administrator. Production admin passwords must contain at least 16 characters.
- Set `APP_BASE_URL`, `FRONTEND_BASE_URL`, and `BUD_APP_URL` to the externally reachable Bud URL.
- Leave `AUTO_SEED_ADMIN=true` for the first startup only.

The example keeps `SMTP_ENABLED=false`. Before enabling email, replace the SMTP host, username, password, sender, and reply-to placeholders with real values.

`BUD_VERSION=latest` selects the evaluation channel. Set it to a published version such as `1.0.0` for a production deployment, or to a prerelease such as `1.0.0-rc.1` when evaluating a release candidate.

### 3. Pull, migrate, and start

```bash
docker compose pull
docker compose up -d postgres
docker compose run --rm bud alembic upgrade head
docker compose up -d bud
```

The migration command must finish successfully before Bud serves production traffic.

### 4. Verify and sign in

```bash
docker compose ps
curl -fsS http://localhost:8001/api/health
```

The health response reports `"status":"healthy"`. Open [http://localhost:8001](http://localhost:8001) and sign in with `ADMIN_EMAIL` and `ADMIN_PASSWORD` from `.env`.

After the first successful login, set this in `.env`:

```dotenv
AUTO_SEED_ADMIN=false
```

Then recreate the Bud service so future starts cannot bootstrap an administrator:

```bash
docker compose up -d --force-recreate bud
```

Keep `RUN_STARTUP_DATA_REPAIR=false` in production. Schema changes are handled explicitly with Alembic.

## Set up the instance

Once signed in:

1. Configure SMTP, then open **Users** as an administrator to invite teammates and assign the Admin or Viewer role.
2. Open **Settings** to choose appearance and display timezone preferences.
3. If you use Bloom, configure **Settings → PLM Integration (Bloom)** as described in [Connect Bud to Bloom](#connect-bud-to-bloom).
4. Register at least one execution agent. It will appear under **Test Stations** after registration and heartbeats begin.

## Register a Test Station

A Test Station is a host where tests execute. The `bud_runner` process is the execution agent on that host. Install and run it only on machines where the test code is trusted.

```bash
python -m pip install bud-runner budtestlibrary

export BUD_BACKEND_URL="https://bud.example.com"
export RUNNER_API_KEY="the-same-value-as-the-bud-server"

python -m bud_runner register \
  --username "lab-station-01" \
  --socket-port 53035 \
  --no-start

python -m bud_runner daemon \
  --username "lab-station-01" \
  --location "Hardware Lab"
```

`BUD_BACKEND_URL` is the Bud base URL, without `/api`. `RUNNER_API_KEY` must exactly match the server value and is needed only for registration. The runner stores its machine token in `~/.bud/config.json`; do not commit that file or registration secrets to a repository.

Verify the connection with:

```bash
python -m bud_runner status
```

The station should appear as **Online** under **Test Stations**. See the [Bud Runner documentation](https://github.com/MbedLabs/bud-runner) for executing suites, uploading results, CI integration, and service installation.

## Work with runs, results, and artifacts

- **Dashboard** shows recent Test Runs and Test Station availability.
- **Test Runs** searches run and suite names and filters by status, Test Station, or station location. Select a row to open its detail page.
- **Test Run detail** shows run timing, station assignment, assertion totals, pass rate, filterable Test Results, and the **System Report** event timeline.
- Compatible runners and API clients upload logs, traces, reports, and other allowed artifacts through `/api/uploads`. Files are stored under `/app/uploads`, which the reference Compose deployment persists in the `bud-uploads` volume.

API documentation is disabled by default. For a trusted development environment only, set `ENABLE_DOCS=true` and open `/api/docs` to inspect the result and artifact endpoints.

## Connect Bud to Bloom

Bud can send test-case execution outcomes to Bloom after it accepts a run's results.

1. Set `BLOOM_APP_URL` in `.env` to control the **Bloom PLM** link in Bud's sidebar.
2. Sign in to Bud as an administrator and open **Settings → PLM Integration (Bloom)**.
3. Enter the Bloom base URL and a valid Bloom access token for an Admin or Maintainer account, then select **Save Integration**.
4. Ensure uploaded result metadata includes Bloom's `tc_id` value, such as `PRJ-TC-001`.

Bud sends one aggregated execution outcome per `tc_id` to Bloom. It does not create or synchronize Bloom campaigns, suites, or documents. The Test Run **System Report** records whether the Bloom synchronization completed, was skipped, or failed. Set `BLOOM_SYNC_ENABLED=false` to disable this behavior.

## Production hosting essentials

### HTTPS and network exposure

Terminate TLS at a reverse proxy or load balancer and proxy to Bud's port `8001`. Set `APP_BASE_URL`, `FRONTEND_BASE_URL`, and `BUD_APP_URL` to the final `https://` URL so links and redirects use the public origin.

The reference Compose file keeps PostgreSQL private to the Compose network; only the Bud service connects to it. Do not add a public database port. Keep `/api/metrics` limited to your monitoring network.

### Email

Set `SMTP_ENABLED=true` only after configuring `SMTP_HOST`, `SMTP_PORT`, credentials, sender addresses, and the appropriate `SMTP_STARTTLS` or `SMTP_SSL` mode. Verify invitation, email-verification, and password-reset delivery before onboarding users.

### Persistent data and backups

Bud has two durable data stores:

- `bud-postgres-data` for PostgreSQL
- `bud-uploads` mounted at `/app/uploads` for uploaded artifacts and attachments

Back up both on the same schedule and test restores on a separate instance. The full procedures are in [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

### Health, metrics, and logs

- `GET /api/health` — container and load-balancer health probe
- `GET /api/metrics` — Prometheus metrics when `ENABLE_METRICS=true`
- `docker compose logs -f bud` — application, nginx, and access logs
- `docker compose logs -f postgres` — database logs

Production logging is JSON by default. Use `LOG_LEVEL` and `LOG_JSON` to integrate with your log collector. Every HTTP response includes `X-Request-ID` for request correlation.

## Image tags and releases

Release images are built from Git tags. Available tag types are:

| Git tag | Container tags | Intended use |
|---|---|---|
| `v1.0.0-rc.1` | `v1.0.0-rc.1`, `1.0.0-rc.1`, `sha-...` | Release-candidate evaluation; does not update `latest`, `1`, or `1.0` |
| `v1.0.0` | `v1.0.0`, `1.0.0`, `1.0`, `1`, `latest`, `sha-...` | Stable release |

Pin the full semantic version in `BUD_VERSION` for production. Major, minor, and `latest` tags move when later stable releases are published.

## Upgrade and rollback

Before upgrading, back up PostgreSQL and uploads. Then set `BUD_VERSION` in `.env` to the target version and run:

```bash
docker compose pull bud
docker compose run --rm bud alembic upgrade head
docker compose up -d bud
curl -fsS http://localhost:8001/api/health
```

Confirm login, a recent Test Run, its results, and an uploaded artifact after the upgrade.

For rollback, restore the pre-upgrade database and uploads backup, set `BUD_VERSION` to the previous image, and start Bud again. Do not run an older application against a database already migrated to an incompatible newer schema. See [`docs/OPERATIONS.md`](docs/OPERATIONS.md) for the complete backup, restore, upgrade, and disaster-recovery procedures.

## Troubleshooting

### Bud does not become healthy

```bash
docker compose ps
docker compose logs --tail=200 bud postgres
```

Confirm PostgreSQL is healthy, `DB_USER`, `DB_PASSWORD`, and `DB_NAME` are set, and `alembic upgrade head` completed. A missing or short `SECRET_KEY`, an unchanged production admin default, or a production admin password shorter than 16 characters prevents startup.

### Runner registration returns `401` or `403`

Confirm the runner's `RUNNER_API_KEY` exactly matches `.env`, its `BUD_BACKEND_URL` uses the Bud base URL, and the URL is reachable from the station. Recreate the Bud container after changing server environment values.

### A Test Station is offline

Run `python -m bud_runner status` on the station, check that its daemon is running, and verify it can reach `/api/health`. Bud marks a station offline when heartbeats stop beyond `RUNNER_HEARTBEAT_TIMEOUT`.

### Invitations or password resets are not delivered

Bud requires SMTP for invitations, email verification, and password resets. Check `SMTP_ENABLED` and every SMTP setting, then inspect `docker compose logs bud`.

### Bloom results do not synchronize

Open the Test Run's **System Report**. Confirm the Bloom URL and token under **PLM Integration (Bloom)**, the token's Bloom role, and that result metadata contains a matching `tc_id`.

## Local development and contributing

The hosting path above uses the published image. Source setup is for contributors.

Backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]" -c constraints.txt
python -m pip install black==25.1.0 isort==5.13.2
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd ui
npm ci
npm run dev
```

Before opening a pull request, run the same formatting and test commands used by CI:

```bash
black --check --diff app/
isort --profile black --check-only --diff app/
pytest --cov=app --cov-report=xml --cov-report=term-missing --cov-fail-under=60 -v

npm --prefix ui run lint
npx --prefix ui tsc --project ui/tsconfig.json --noEmit
npm --prefix ui run test -- --coverage
```

The complete workflow also provisions PostgreSQL, applies the model-driven base schema and Alembic migrations, installs the pinned formatter and security-scan tools, and runs Bandit plus `pip-audit`. See [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) for that environment and [`CONTRIBUTING.md`](CONTRIBUTING.md) for the contribution process. Contributions require acceptance of [`CLA.md`](CLA.md).

## Security and support

Report vulnerabilities according to [`SECURITY.md`](SECURITY.md). For release history, see [`CHANGELOG.md`](CHANGELOG.md).

## License

Bud is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. See [`LICENSE`](LICENSE).
