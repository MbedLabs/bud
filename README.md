# bud-app-backend

Backend application for the Bud project — Test automation API.

> **Note:** This repository was split from the original [MbedLabs/bud-web-app](https://github.com/MbedLabs/bud-web-app) monorepo.
> Git history has been preserved for all files that were under `backend/`.

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
- `POST /api/runners/register` — Register runner
- `POST /api/runners/heartbeat` — Runner heartbeat
- `GET /api/runners/status` — Get runner status

## Related Repos

- Frontend: [MbedLabs/bud-app-frontend](https://github.com/MbedLabs/bud-app-frontend)

## License

MIT License — Copyright (c) 2025 EmbedLabs
