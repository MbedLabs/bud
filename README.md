# Bud TMP by EmbedLabs

Bud TMP by EmbedLabs is a source-available test management and execution platform for teams running automated tests on CI workers, lab machines, and hardware test stations. It brings runner status, test runs, assertion results, execution events, and uploaded artifacts into one self-hosted workspace.

> **Release status:** 1.0.0 public beta. See the [changelog](CHANGELOG.md) for what this release includes.

## Licence status

Bud is distributed under the [EmbedLabs Source Available License 1.0](LICENSE).

The licence permits personal, educational, evaluation, research, and internal business use, including modification for those permitted uses. A separate professional licence is required for resale, third-party hosting, managed services, commercial redistribution, white-labelling, or embedding Bud in a third-party commercial offering.

The required `Powered by EmbedLabs` attribution must remain visible as described in the licence. Product names and logos are not licensed for modified forks.

The separate [`bud-runner`](https://github.com/MbedLabs/bud-runner) and `budtestlibrary` Python packages remain independent AGPL-3.0-only open-source projects.

For professional licensing, deployment, integration, priority support, or custom development, contact `sales@embedlabs.de`.

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
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD` (at least 16 characters in production)
- `ADMIN_FULL_NAME`
- `APP_BASE_URL`
- `FRONTEND_BASE_URL`
- `BUD_APP_URL`

In production (`BUD_ENV=production`) Bud fails closed at startup: it refuses to boot while `SECRET_KEY`, `RUNNER_API_KEY`, `DB_PASSWORD`, or `ADMIN_PASSWORD` still holds an `.env.example` placeholder, and it requires `ADMIN_PASSWORD` to be at least 16 characters.

Keep `RUN_STARTUP_DATA_REPAIR=false` in production. Set `AUTO_SEED_ADMIN=true` only for the one-time first-administrator bootstrap on a new empty database, then restore it to `false` immediately.

### 3. Pull, migrate, and start

Pin the image by setting `BUD_VERSION` in `.env` (for example `BUD_VERSION=1.0.0`; the default is `stable`). `docker compose` pulls `ghcr.io/mbedlabs/bud:${BUD_VERSION}`.

```bash
docker compose pull
docker compose up -d postgres
docker compose run --rm bud alembic upgrade head
docker compose up -d bud
```

The migration must finish successfully before Bud serves production traffic. The application container never builds or repairs the schema on its own (`RUN_STARTUP_DATA_REPAIR=false`); Alembic is the only schema builder.

### 4. Verify

```bash
docker compose ps
curl -fsS http://localhost:8001/api/ready
```

`/api/health` is process liveness. `/api/ready` verifies PostgreSQL connectivity.

## Email delivery

SMTP is optional when evaluating Bud with only the pre-seeded administrator. It is required for user invitations, password resets, and approved email changes. Configure `SMTP_ENABLED=true` together with `SMTP_HOST`, `SMTP_FROM_EMAIL`, and the authentication/TLS values required by your mail server before using those workflows.

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

## Connect Bud to Bloom

Bud and Bloom remain independently deployable. Saving a Bloom URL and scoped credential in Bud enables result synchronisation; clearing the credential disables it. There is no separate hidden enable flag.

1. In Bloom, set `SERVICE_TOKEN_PEPPER` to an independent random value of at least 32 characters and restart Bloom.
2. In Bloom, sign in as an administrator, open **Settings → Bud Result-Sync Credentials**, and create a credential. Copy it immediately; Bloom displays the raw `blm_sync_…` value only once.
3. In Bud, generate and configure `BUD_INTEGRATION_ENCRYPTION_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

4. Restart Bud, sign in as an administrator, open **Settings → PLM Integration (Bloom)**, and save Bloom's reachable base URL plus the copied credential.
5. Optionally set Bud's deployment-time `BLOOM_APP_URL` to show a Bloom navigation link in the Bud sidebar. This variable does not configure result synchronisation.
6. Optionally set Bloom's `BUD_APP_URL` to show links back to Bud.

Bud accepts HTTP URLs for localhost and deliberately trusted internal networks. Use the HTTPS URL exposed by your reverse proxy whenever traffic crosses a host or network boundary. Changing the saved destination origin requires re-entering or clearing the credential so it cannot be forwarded to a different server.

## Persistence and backups

Bud has two durable stores:

- `bud-postgres-data` for PostgreSQL
- `bud-uploads` mounted at `/app/uploads` for artifacts

Back up both and test restoration on a separate instance. See [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

## Image tags

Set `BUD_VERSION` in `.env` to the tag `docker compose` should pull.

| Container tag | Meaning |
|---|---|
| `1.0.0` | Exact production version — pin this for production |
| `1.0` / `1` | Moving stable channels tracking the newest `1.0.x` / `1.x` |
| `stable` | Newest stable semantic-version release |
| `latest` | Rolling image from `main`; not guaranteed to be a stable release |
| `dev` | Rolling image from the `dev` branch |
| `sha-<commit>` | Immutable image for exact source/image traceability |

Every moving tag (`stable`, `latest`, `1.0`, `1`, a branch name) is promoted to an image only after that exact image passes the published-image end-to-end tests, so a tag never resolves to an untested build. Pin a full semantic version (`BUD_VERSION=1.0.0`) for production.

## Upgrading

1. Read the [changelog](CHANGELOG.md) for the target release, and back up both volumes first (see [Persistence and backups](#persistence-and-backups)).
   When upgrading to `1.0.0`, migration `006_encrypt_bloom_service_token` removes any legacy Bloom administrator/plaintext token. Create a new scoped credential in Bloom and save it again in Bud after the migration.
2. Set the new version in `.env`, for example `BUD_VERSION=1.0.0`.
3. Pull, migrate, then restart. Migrations must complete before the application serves traffic:

```bash
docker compose pull
docker compose run --rm bud alembic upgrade head
docker compose up -d bud
```

4. Confirm the running image and database:

```bash
curl -fsS http://localhost:8001/api/version
curl -fsS http://localhost:8001/api/ready
```

To roll back, restore the pre-upgrade volume backups and set `BUD_VERSION` to the previous release. Downgrades that require reversing a migration are not supported — restore from backup instead.

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
