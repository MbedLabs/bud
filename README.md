# Bud

Bud is the combined product repo for the EmbedLabs test management platform. It keeps the FastAPI backend at the repo root, the React frontend under [`frontend/`](frontend), and ships a single product image that serves both the UI and the `/api` surface.

## What is in this repo

- Backend API and Alembic migrations at the root
- Frontend application in [`frontend/`](frontend)
- One combined Docker image build from the root `Dockerfile`
- One product CI workflow in [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml)

## Version

This combined product repo is currently at `1.0.0`.

## Quick start

```bash
cp .env.example .env
docker compose up -d postgres
docker compose run --rm bud alembic upgrade head
docker compose up -d bud
curl -sf http://localhost:8001/api/health
```

Open `http://localhost:8001`.

For the first admin bootstrap, temporarily set `AUTO_SEED_ADMIN=true` in `.env`, start Bud once, sign in, then set it back to `false`.

## Local development

Backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

## Verification

Backend checks:

```bash
black --check --diff app/
isort --profile black --check-only --diff app/
pytest --cov=app --cov-report=term-missing --cov-fail-under=50 -v
```

Frontend checks:

```bash
cd frontend
npm run lint
npx tsc --noEmit
npm run test -- --coverage
```

Combined image:

```bash
docker build -t bud:1.0.0 .
docker run --rm -p 8001:8080 bud:1.0.0
```

## Runner registration

Runner registration still requires the shared `RUNNER_API_KEY` secret. The backend reads it from the environment and the `bud-runner` CLI sends it as `X-API-Key` during `bud-runner register`.

```bash
export RUNNER_API_KEY=<shared-runner-registration-secret>
export BUD_BACKEND_URL=http://localhost:8001
bud-runner register --username local-runner
```

## Production notes

- `BUD_ENV=production` rejects unsafe bootstrap defaults.
- `RUN_STARTUP_DATA_REPAIR` defaults off in production.
- `AUTO_SEED_ADMIN` defaults off in production and should only be enabled for controlled bootstrap or rotation windows.

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. See [LICENSE](LICENSE).
