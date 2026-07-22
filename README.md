# Bud TMP by EmbedLabs

Bud TMP by EmbedLabs is a source-available test management and execution platform for teams running automated tests on CI workers, lab machines, and hardware test stations. It brings runner status, test runs, assertion results, execution events, and uploaded artifacts into one self-hosted workspace.

## Licence status

Bud is distributed under the [EmbedLabs Source Available License 1.0](LICENSE). It is **source-available**, not Open Source under the Open Source Definition.

The licence permits personal, educational, evaluation, research, and internal business use, including modification for those permitted uses. A separate professional licence is required for resale, third-party hosting, managed services, commercial redistribution, white-labelling, or embedding Bud in a third-party commercial offering.

The required `Powered by EmbedLabs` attribution must remain visible as described in the licence. Product names and logos are not licensed for modified forks.

The separate [`bud-runner`](https://github.com/MbedLabs/bud-runner) and `budtestlibrary` Python packages remain independent AGPL-3.0-only open-source projects.

For professional licensing, deployment, integration, priority support, or custom development, contact `professional@embedlabs.de` or `dev@embedlabs.net`.

## Container image

- **Image:** `ghcr.io/mbedlabs/bud`
- **Package:** [Bud on GitHub Packages](https://github.com/orgs/MbedLabs/packages/container/package/bud)
- **Platforms:** `linux/amd64` and `linux/arm64`
- **Container port:** `8080`
- **Reference host port:** `8001`

The published image contains the Bud web application and API. You do not need to build the frontend or install Python dependencies to host it.

## What Bud provides

- Dashboard for recent test activity and connected Test Stations
- Searchable Test Runs with status, station, and location filters
- Per-run assertion summaries, detailed results, and execution events
- Registration and heartbeat monitoring for `bud-runner` agents
- Artifact upload and download backed by persistent storage
- Administrator-managed users, invitations, and viewer access
- Optional test-case execution result synchronisation to Bloom

Bud, `bud-runner`, and `budtestlibrary` work without Bloom. Bloom integration is optional.

## Quick start

### Prerequisites

- Docker Engine with Docker Compose v2
- Git
- `openssl`
- Available host port `8001`

### 1. Get the deployment files

```bash
git clone https://github.com/MbedLabs/bud.git
cd bud
cp .env.example .env
```

### 2. Configure secrets

Generate separate values for the database password, application signing key, runner registration key, and initial administrator password:

```bash
openssl rand -hex 24
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 24
```

Replace every active `replace-with-...` placeholder in `.env`. At minimum configure:

- `DB_PASSWORD`
- `SECRET_KEY`
- `RUNNER_API_KEY`
- `INTEGRATION_ENCRYPTION_KEY`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `ADMIN_FULL_NAME`
- `APP_BASE_URL`
- `FRONTEND_BASE_URL`
- `BUD_APP_URL`

Keep `RUN_STARTUP_DATA_REPAIR=false` in production. Set `AUTO_SEED_ADMIN=true` only for the one-time first-administrator bootstrap on a new empty database, then restore it to `false` immediately.

### 3. Pull, migrate, and start

```bash
docker compose pull
docker compose up -d postgres
docker compose run --rm bud alembic upgrade head
docker compose up -d bud
```

The migration must finish successfully before Bud serves production traffic.

### 4. Verify

```bash
docker compose ps
curl -fsS http://localhost:8001/api/ready
```

`/api/health` is process liveness. `/api/ready` verifies PostgreSQL connectivity.

## Register a Test Station

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

The runner stores its machine token in `~/.bud/config.json`. Do not commit that file or registration secrets.

## Persistence and backups

Bud has two durable stores:

- `bud-postgres-data` for PostgreSQL
- `bud-uploads` mounted at `/app/uploads` for artifacts

Back up both and test restoration on a separate instance. See [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

## Image tags

| Container tag | Meaning |
|---|---|
| `dev` | Rolling image from the `dev` branch |
| `latest` | Rolling image from `main`; not guaranteed to be a stable release |
| `stable` | Newest stable semantic-version release |
| `1.2.3` | Exact production version |
| `1.2` / `1` | Moving stable channels |
| `sha-...` | Exact source/image traceability |

Pin a full semantic version for production.

## Security and documentation

- [Operating Bud](docs/OPERATIONS.md)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [Contributing guide](CONTRIBUTING.md)
- [Contributor License Agreement](CLA.md)
- [EmbedLabs Source Available License](LICENSE)

API documentation is disabled by default. Enable it only in a trusted development environment.

## Contributing

Contributions require explicit acceptance of [`CLA.md`](CLA.md) through the pull-request declaration. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Professional services

Professional licensing, deployment assistance, integrations, priority support, and custom engineering are available through [EmbedLabs Professional Services](https://embedlabs.de).
