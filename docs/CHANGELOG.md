# Changelog

## 1.2.0 - unreleased

### Added

- Admin company logo on test-run PDF reports: an administrator uploads a company logo in Settings; it renders on the report letterhead (top-left) alongside the EmbedLabs tamper-evidence footer, which is always present. The Settings preview loads through the authenticated client so the admin sees exactly what was stored.
- Robot Framework runs (bud-runner `run-robot`): HTML artifacts (`text/html`, Robot's log.html and report.html) are accepted. Every artifact download is an attachment sent with `Content-Security-Policy: sandbox` and `X-Content-Type-Options: nosniff`, so user-supplied HTML or SVG never runs in the Bud origin. The Bloom sync event says how many results had no Bloom tc_id and how many skipped results were not sent; a skipped result is no longer reported to Bloom as passed.
- User groups (Users page, admin): a group has a role, members and product grants (one product or all products). An admin group makes its members administrators. A viewer group shows its members only the products it is granted, across runs, results, reports, artifacts, statistics and products; a run outside them answers 404. A user in no group keeps their own role and sees every product, as before. `/api/auth/me` reports the role groups give.
- Run notifications: when a run finishes, Bud posts it to every enabled channel under Settings, Notifications: Microsoft Teams (Adaptive Card), Slack (Block Kit), Discord (embed) or plain JSON for any endpoint. The message carries the run, product, station and software under test, the counts and duration, up to five failed tests, the Bud link and the Bloom link or sync failure. A channel sends all runs, failures only, or the first failure after a green run; its URL is stored encrypted and shown as a prefix; an optional secret signs the JSON body (`X-Bud-Signature`). Each delivery is retried three times and recorded, shown as a notify stage on the run timeline; Send test message checks a channel. Routing per product and per station is not in this release.

## 1.1.0 - 2026-09-16

### Added

- Cloudron package: `cloudron/CloudronManifest.json` and `cloudron/CloudronVersions.json`; the product image runs under Cloudron's read-only root filesystem with data and generated secrets in `/app/data`; PostgreSQL and local storage addons, mail addon optional; `minBoxVersion` 9.1.0; CI smoke-tests the image against the Cloudron contract.
- First-run setup: `GET /api/setup/status` and `POST /api/setup` create the first administrator; the endpoint answers 409 once any user exists; a confirmation email is sent, best effort.
- Custom runs: `GET /api/test-catalog`, `POST /api/test-runs/custom`, `POST /api/runners/claim-run` and the Custom Run screen; a selection spanning two stations becomes one queued run per station; `test_runs.selected_tests` holds the selected `module.Class` paths.
- Per-station enrolment keys, minted on the Test Stations page; a key pins to the first station that registers with it, is shown once, stored as a SHA-256 digest and listed by prefix.
- Station names are chosen when the key is minted and can be renamed afterwards; runner tokens carry the station id.
- A run links back to the Bloom test suite holding its synced test cases (`bloom_artefact_id`, `bloom_artefact_name`, `bloom_artefact_url`), shown on the run detail, the run list and the dashboard; only `http`/`https` addresses render as links.
- Dashboard statistics filter by time range, Test Station and suite; `GET /api/test-runs/stats` and `GET /api/test-runs/filter-options`; `GET /api/test-runs` accepts `suite`, `q` and `location`.
- `GET /api/test-runs/{run_id}/artifacts` lists a run's files; the run detail page downloads them.
- PDF reports: `GET /api/reports/test-runs.pdf` for the dashboard selection and `GET /api/reports/test-runs/{run_id}.pdf` for one run, with download buttons on both screens.
- Upload allowlist adds CSV, SVG, PDF, `application/vnd.tcpdump.pcap`, `application/x-pcapng`, `application/cap`, gzip, tar, GIF and WebP; HTML stays refused.
- Index on `artifacts (test_run_id, created_at)`.
- Release pipeline: tested images are promoted by digest to `v1.1.0`, `1.1.0`, `1.1`, `1` and `stable`; a published version is never overwritten; an SBOM is attached to each release.
- CLA acceptance check on pull requests; Dependabot targets `dev`.

### Changed

- Removing a station or revoking a key opens a confirmation; server errors are shown inside the dialog.
- Station row actions sit in a `…` menu; keys are added with `+`; the enrolment panel lists only keys not yet bound to a station; the catalogue is labelled "Available test cases".
- The Users and Test Stations pages no longer repeat the header title.
- `RUNNER_API_KEY` is removed from `.env.example` and the README; the `teststations` table and its endpoints are removed; ALM is renamed PLM.
- Transactional mail uses Bud's colours with inlined styles.
- The frontend is split by route; screens behind authentication load on demand.
- Dispatching a custom run reloads the created runs in one query.
- Coverage measures threads and greenlets; the CI gate is 85%.
- React 19, React Router 8 (`react-router`), Node 24 for builds, `lucide-react` upgraded; the dependency audit carries no exception.
- The migration history is one locked baseline; the container runs `alembic upgrade head` before serving.
- Backend tests are split into `tests/api`, `tests/logic`, `tests/sec` and `tests/pg`; CI runs `tests/pg` twice on the same database.
- Dependencies: alembic 1.19.2, click 8.5.0, cryptography 50.0.1, idna 3.19, pydantic 2.13.5, pydantic-core 2.46.5, uvicorn 0.52.4, wrapt 2.4.0, `@tanstack/react-query` 5.102.8, `axios` 1.20.0, `react-router` 8.3.1.

### Fixed

- Constraint violations answer 409 or 422 with the request id; unhandled errors return the request id in the body and the message.
- Tests no longer load the operator's `.env`; opt in with `BUD_TESTS_USE_DOTENV=1`.
- Cloudron mail uses the STARTTLS port; delivery failures return 503 naming host, port and TLS mode; `packageUrl` is removed from the manifest.
- The result listing no longer loads per-method tracebacks; `TestResult.artifacts` is removed from the frontend types.
- Run list search and the location filter apply on the server; `latest_per_suite` uses a window function.
- Summary tiles count test cases and assertions separately; dashboard counters aggregate the whole filtered set and exclude runs in progress.
- The smoke test reads the expected version from `pyproject.toml`.
- The build fails on a Tailwind gradient class the config does not define.

### Security

- Revoking an invitation revokes its link.
- Result uploads authenticate with the station's own key; `get_uploader_entity` no longer reads the request body.

### Removed

- `ui/dist/index.html`; the duplicate CI workflow and pull request template under `ui/.github/`.

### bud_runner

- `upload_artifact` exists in the runner's API client and no command calls it.
- A station polls `POST /api/runners/claim-run` and executes `selected_tests`; a 204 means nothing is waiting.

### Upgrade notes

- Stations enrolled before 1.1.0 re-register once against a key minted by an administrator; `RUNNER_API_KEY` is no longer read.

## 1.0.0 - 2026-07-24

Initial public beta release of Bud TMP by EmbedLabs, a test
management and execution platform. Published as a multi-architecture container
image with PostgreSQL-backed deployment, Alembic migrations, liveness/readiness
health checks, and persistent artifact storage.

### Added

- User-first deployment and operations guidance for the published Bud TMP by EmbedLabs container image.
- Configurable 25 MiB per-file upload limit, with an operator opt-in up to 100 MiB for trace-heavy runners.
- A 250 MiB aggregate quota per run, upload rate and concurrency limits, free-space protection, retention, and orphan-file cleanup.

### Changed

- Bloom integration now uses a revocable, time-limited `test-results:write` credential instead of an administrator token.
- Bud sends test-case execution outcomes by Bloom `tc_id`; it does not create or synchronize campaigns.
- Saving the Bloom URL and scoped credential now enables result synchronisation directly; clearing the credential disables it.
- Email changes are administrator-controlled: users may request a change, administrators approve or reject it, and the new mailbox must confirm before the login changes. Administrators can initiate the same confirmed workflow.

### Fixed

- Login failures now show the useful API error detail instead of a generic HTTP status message.
- Runner, user, and Test Station authorization boundaries are consistently enforced.

### Security

- Artifact uploads are validated and written while streaming; runner uploads are scoped to their own run.
- Bloom integration credentials are encrypted at rest and are never returned through settings APIs.
- Passwords must be at least 12 characters; changing or resetting a password signs out all existing sessions.
- One-time links (invitation, email verification, password reset, email change) carry their token only in the URL fragment and are single-use, keeping tokens out of request targets, server logs, and the Referer header.
- Direct email replacement through the generic administrator user-update API is no longer allowed.
- Python and npm dependency vulnerability scans block CI on actionable findings.
- Upgraded React Router to 7.18.2 and the lint/test toolchain to patched releases. The remaining npm advisory affects only RSC Actions, which Bud does not use, and is narrowly documented in the audit gate.

### Upgrade notes

- Migration `006_encrypt_bloom_service_token` deletes legacy plaintext or administrator Bloom tokens. Create a new scoped `test-results:write` credential in Bloom and save it in Bud after upgrading.
- SMTP remains optional for a single-administrator evaluation, but invitations, password resets, and approved email changes require it.
