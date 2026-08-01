# Changelog

## Unreleased

### Added

- Dashboard statistics can be filtered by time range, Test Station, and test suite.
- `GET /api/test-runs/stats` and `GET /api/test-runs/filter-options` expose those aggregates.
- `GET /api/test-runs` accepts a `suite` filter.
- PDF reports. `GET /api/reports/test-runs.pdf` renders the current dashboard selection - time range, Test Station and suite - as a document with a passed/failed/skipped pie chart and breakdown tables per suite, per Test Station and per day. `GET /api/reports/test-runs/{run_id}.pdf` reports a single run, carrying its run id, station, product, timings and every recorded result. Both carry the Bud logo, a "Powered by EmbedLabs" footer on every page, and real PDF link annotations: the run's repositories, the run's page in Bud, and the EmbedLabs site are all clickable. The Dashboard and the run detail page each have a download button.

### Security

- Revoking an invitation now revokes its link. It previously only deactivated the account, leaving the emailed token valid until its TTL: whoever held the link could still accept the invitation and set a password, which then worked the moment an administrator reactivated the account.

### Fixed

- Test run summary tiles reported assertion counts under a "Total Tests" label. Test cases and assertions are now counted separately and shown together on the Total, Passed, and Failed tiles.
- Dashboard counters were derived from only the first page of test runs, so the pass rate depended on the page size. They are now aggregated in the database across the whole filtered set, and runs still in progress no longer count against the pass rate.

### Changed

- Upgraded to React 19 and React Router 8, which resolves GHSA-qwww-vcr4-c8h2 (React Router RSC-mode CSRF). The frontend now imports from `react-router` instead of the retired `react-router-dom` package. Frontend builds and CI run on Node 24; Node 22.22 is the supported minimum.
- Upgraded `lucide-react`, whose pinned release declared support only up to React 18.
- The dependency audit no longer carries any reviewed-advisory exception; every advisory now fails the build.
- The migration history is collapsed into a single locked baseline of explicit DDL. The base revision previously called `Base.metadata.create_all()`, which meant it always produced whatever the models currently described, so every later revision had to be written with inspect-then-add guards and the real `ALTER` path was never exercised by the fresh-install CI check. The baseline keeps the identifier of the previously deployed head, so an existing database is recognised as up to date and is not re-migrated; no stamp or manual step is required.
- The container now runs `alembic upgrade head` before serving traffic, matching Bloom. A separate `docker compose run --rm bud alembic upgrade head` step is no longer needed.

### Removed

- The stale `ui/dist/index.html` build artifact is no longer tracked in the repository.
- The stale duplicate CI workflow and pull request template under `ui/.github/`, neither of which GitHub ever read.

## 1.0.0 - 2026-07-24

Initial public beta release of Bud TMP by EmbedLabs — a self-hosted test
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
