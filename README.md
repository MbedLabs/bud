# bud-app-backend

Backend application for the Bud platform — a comprehensive test automation and runner orchestration API.

## Stack

- **FastAPI** (Python)
- **PostgreSQL**

## Development

```bash
python -m venv venv
source venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

API available at http://localhost:8000

## Docker

```bash
docker build -t bud-app-backend .
docker run -p 8000:8000 bud-app-backend
```

## API Endpoints

### Health
- `GET /api/health` — Health check
- `GET /api/version` — API version

### Test Runs
- `POST /api/test-runs` — Create test run
- `GET /api/test-runs` — List test runs
- `GET /api/test-runs/{id}` — Get test run
- `PATCH /api/test-runs/{id}` — Update test run

### Results
- `POST /api/results` — Upload results
- `GET /api/results/{run_id}` — Get results for a run

### Uploads
- `POST /api/uploads` — Upload artifact
- `GET /api/uploads/{id}` — Download artifact

### Runners
- `POST /api/runners/register` — Register a new Bud runner. **Requires `X-API-Key`**
  (see "Runner registration" below).
- `POST /api/runners/heartbeat` — Runner heartbeat
- `GET /api/runners/status` — Get runner status

## Authentication

The backend uses two distinct credentials:

| Credential | Where it's used | How it's passed |
| --- | --- | --- |
| **User JWT (`BUD_TOKEN`)** | Most API calls (create test runs, upload results, etc.) | `Authorization: Bearer <token>` |
| **`RUNNER_API_KEY`** | `POST /api/runners/register` only | `X-API-Key: <key>` header |

### Runner registration

`POST /api/runners/register` is protected by a shared secret so that only
operators with access to it can register new Bud runners against this
backend. The server reads it from the `RUNNER_API_KEY` environment variable
(see [`app/core/deps.py`](app/core/deps.py) / `require_runner_api_key`). If
it's not set, the endpoint returns **500** and registration is effectively
disabled.

Set it alongside `SECRET_KEY` in the backend's `.env`:

```env
SECRET_KEY=<your-jwt-signing-secret>
RUNNER_API_KEY=<shared-runner-registration-secret>
```

Operators who register runners need the same value on the client side.
The [`bud_runner`](https://github.com/MbedLabs/bud_runner) CLI reads it
from the `RUNNER_API_KEY` environment variable (or `--api-key`) and sends
it as `X-API-Key`:

```bash
export RUNNER_API_KEY=...   # same value as the backend
export BUD_BACKEND_URL=https://<your-bud-instance-url>
bud_runner register --username my-runner
```

> **Terminology:** a *Bud runner* is the registered execution agent
> (account) on a host; a *Test Station* is the host/environment itself as
> shown in the frontend. One station can run many test suites; a pure
> software station can host multiple Bud runners.

## Related Repos

- Frontend: [MbedLabs/bud-app-frontend](https://github.com/MbedLabs/bud-app-frontend)

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. See the [LICENSE](LICENSE) file for the full text.

Copyright (C) 2026 EmbedLabs.

For commercial licensing options that do not require AGPL compliance, contact dev@embedlabs.net. Contributions are accepted under the [CLA](CLA.md) — see [CONTRIBUTING.md](CONTRIBUTING.md).
