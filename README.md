# Bud

Bud is an open source test management and execution platform for teams that need runs, results, artifacts, and runner orchestration in one place.

## What you can do with Bud

- Manage test runs, execution history, and uploaded artifacts from one workspace
- Register and monitor runners and test stations across hardware and software setups
- Collect structured execution results from automated and operator-driven workflows
- Coordinate execution infrastructure while keeping product-facing run history in one system
- Connect execution outcomes with Bloom when the two products are deployed together

## Self-host Bud

Bud ships as a combined product repo with a FastAPI backend at the repository top level, a React UI in [`ui/`](ui), and one product image that serves both the UI and the `/api` surface.

Bud requires PostgreSQL plus runtime configuration for database access, application secrets, public URLs, admin access, and runner registration. Runner registration is protected by the shared `RUNNER_API_KEY` secret. Run `alembic upgrade head` before serving traffic.

## Get Started

- Review [`docker-compose.yml`](docker-compose.yml) for a reference self-host layout
- Use [`Dockerfile`](Dockerfile) if you want to build the combined product image directly
- Verify the deployed instance through the `/api/health` endpoint on your Bud URL

## Runner Registration

New runner registration requires the same shared `RUNNER_API_KEY` value on both the Bud backend and the registering runner.

## Local Development

Backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

UI:

```bash
cd ui
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

UI checks:

```bash
cd ui
npm run lint
npx tsc --noEmit
npm run test -- --coverage
```

Combined image:

```bash
docker build -t bud:1.0.0 .
```

## Resources

- [`CHANGELOG.md`](CHANGELOG.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. See [LICENSE](LICENSE).
