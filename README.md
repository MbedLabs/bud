# Bud TMP by EmbedLabs

Bud TMP is a self-hosted test management and execution platform for automated software, hardware, and system testing. It gives teams one place to monitor Test Stations, inspect runs and assertions, retain artifacts, and connect execution evidence to Bloom PLM.

> **Release:** 1.0.0 public beta

## What Bud provides

- Live Test Station registration, heartbeat, and availability
- Searchable test runs with status, station, and location filters
- Assertion results, execution events, logs, and uploaded artifacts
- User, invitation, administrator, and viewer management
- Runner-token and API-key authentication for automated uploads
- Optional result synchronization to Bloom PLM test cases
- Readiness, health, metrics, structured logging, and backup workflows

## Bud testing ecosystem

| Component | Role |
|---|---|
| **Bud TMP** | Stores, presents, and manages execution results |
| [`bud-runner`](https://github.com/MbedLabs/bud-runner) | Runs trusted Python test suites and uploads their results to Bud |
| [`budtestlibrary`](https://github.com/MbedLabs/bud-test-library) | Provides the Python test lifecycle, assertions, result model, and optional Bloom metadata |
| [`Bloom PLM`](https://github.com/MbedLabs/bloom) | Optionally receives linked test-case execution outcomes from Bud |

`bud-runner` and `budtestlibrary` are independent AGPL-3.0 open-source Python packages. They work with Bud without requiring Bloom.

## Quick start

### Requirements

- Docker Engine with Docker Compose v2
- `curl`
- `openssl`
- Available host port `8001`

### 1. Download the deployment files

```bash
mkdir bud-deployment
cd bud-deployment

curl -fsSLo compose.yaml \
  https://raw.githubusercontent.com/MbedLabs/bud/main/docker-compose.yml
curl -fsSLo .env \
  https://raw.githubusercontent.com/MbedLabs/bud/main/.env.example
```

This downloads only the deployment configuration. The application itself runs from `ghcr.io/mbedlabs/bud`.

### 2. Configure Bud

Generate independent secrets:

```bash
openssl rand -hex 24
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 24
```

Open `.env` and replace every active `replace-with-...` value. At minimum, set:

- `DB_PASSWORD`
- `SECRET_KEY`
- `RUNNER_API_KEY`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `ADMIN_FULL_NAME`
- `APP_BASE_URL`
- `FRONTEND_BASE_URL`
- `BUD_APP_URL`

For a new database, set `AUTO_SEED_ADMIN=true` for the first startup. In production, Bud rejects placeholder secrets and requires an administrator password of at least 16 characters.

Keep `RUN_STARTUP_DATA_REPAIR=false`. Database schema changes are applied only through Alembic.

### 3. Pull, migrate, and start

```bash
docker compose -f compose.yaml pull
docker compose -f compose.yaml up -d postgres
docker compose -f compose.yaml run --rm bud alembic upgrade head
docker compose -f compose.yaml up -d bud
```

After the first administrator has been created, set `AUTO_SEED_ADMIN=false` in `.env` and apply the configuration:

```bash
docker compose -f compose.yaml up -d bud
```

### 4. Verify

```bash
docker compose -f compose.yaml ps
curl -fsS http://localhost:8001/api/ready
```

Open `http://localhost:8001`.

- `/api/health` checks process liveness.
- `/api/ready` checks application readiness and PostgreSQL connectivity.
- `/api/version` reports the running version.

## Connect a Test Station

Install both execution packages on a trusted lab host or self-hosted CI worker:

```bash
python -m pip install bud-runner budtestlibrary
```

Register and start the runner:

```bash
export BUD_BACKEND_URL="https://bud.example.com"
export RUNNER_API_KEY="the-registration-secret-from-bud"

python -m bud_runner register \
  --username "lab-station-01" \
  --socket-port 53035 \
  --no-start

python -m bud_runner daemon \
  --username "lab-station-01" \
  --location "Hardware Lab"
```

The runner stores its machine identity and tokens under `~/.bud/`. Keep that directory private and never commit it.

See the [`bud-runner` documentation](https://github.com/MbedLabs/bud-runner) for execution and upload commands, and the [`budtestlibrary` documentation](https://github.com/MbedLabs/bud-test-library) for test authoring and assertions.

## Connect Bud to Bloom

Bud and Bloom remain independently deployable. To synchronize linked test-case outcomes:

1. Set a random Bloom `SERVICE_TOKEN_PEPPER` of at least 32 characters and restart Bloom.
2. In Bloom Settings, open **PLM Integration Token Management** and select **Create Credential**.
3. Copy the `blm_sync_…` credential when it is shown. Bloom displays it only once.
4. Generate a Bud encryption key:

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

5. Set the result as `BUD_INTEGRATION_ENCRYPTION_KEY` and restart Bud.
6. In Bud, open **Settings → PLM Integration (Bloom)** and save Bloom's reachable URL and the scoped credential.

`BLOOM_APP_URL` adds a Bloom navigation link to Bud. It does not configure result synchronization. Clearing the saved scoped credential disables synchronization.

## Email

SMTP is optional for an installation that uses only the initial administrator. It is required for invitations, password resets, email verification, and approved email changes.

Set `SMTP_ENABLED=true` and configure the SMTP host, sender, authentication, and TLS values in `.env` before using those workflows.

## Data and backups

Bud has two durable stores:

- `bud-postgres-data` for PostgreSQL
- `bud-uploads` for uploaded artifacts

Back up both volumes and the deployment secrets together. Test restoration on a separate installation. Detailed procedures are in [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

## Images and versions

- **Image:** `ghcr.io/mbedlabs/bud`
- **Package:** [Bud on GitHub Packages](https://github.com/orgs/MbedLabs/packages/container/package/bud)
- **Platforms:** `linux/amd64`, `linux/arm64`
- **Container port:** `8080`
- **Default host port:** `8001`

Set `BUD_VERSION` in `.env`:

| Tag | Use |
|---|---|
| `1.0.0` | Immutable production release |
| `1.0` / `1` | Moving release channels |
| `stable` | Newest stable release |
| `latest` | Rolling image from `main` |
| `dev` | Rolling image from `dev` |
| `sha-<commit>` | Exact source and image revision |

Pin a complete version such as `1.0.0` for production.

## Upgrade

1. Read [`CHANGELOG.md`](CHANGELOG.md).
2. Back up `bud-postgres-data`, `bud-uploads`, and `.env`.
3. Set the target `BUD_VERSION`.
4. Pull the image, run migrations, and restart:

   ```bash
   docker compose -f compose.yaml pull
   docker compose -f compose.yaml run --rm bud alembic upgrade head
   docker compose -f compose.yaml up -d bud
   ```

5. Verify `/api/version` and `/api/ready`.

Restore the pre-upgrade backups to roll back a release that changed the database schema. Database downgrades are not supported.

## Documentation

- [Operations](docs/OPERATIONS.md)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Contributor License Agreement](CLA.md)

API documentation is disabled by default. Enable it only in a trusted development environment.

## Licensing

Bud TMP is distributed under the [EmbedLabs Source Available License 1.0](LICENSE).

The license permits personal, educational, evaluation, research, and internal business use, including modification for those uses. A separate professional license is required for resale, third-party hosting, managed services, commercial redistribution, white-labelling, or embedding Bud in a third-party commercial product.

The required `Powered by EmbedLabs` attribution must remain visible. Product names and logos are not licensed for modified forks.

For professional licensing, deployment, integration, priority support, or custom development, contact `sales@embedlabs.de` or visit [EmbedLabs](https://www.embedlabs.net).
