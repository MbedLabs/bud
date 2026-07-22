# Changelog

## Unreleased

### Added

- User-first deployment and operations guidance for the published Bud by EmbedLabs container image.
- Configurable 25 MiB per-file upload limit, with an operator opt-in up to 100 MiB for trace-heavy runners.
- A 250 MiB aggregate quota per run, upload rate and concurrency limits, free-space protection, retention, and orphan-file cleanup.

### Changed

- Bloom integration now uses a revocable, time-limited `test-results:write` credential instead of an administrator token.
- Bud sends test-case execution outcomes by Bloom `tc_id`; it does not create or synchronize campaigns.

### Fixed

- Login failures now show the useful API error detail instead of a generic HTTP status message.
- Runner, user, and Test Station authorization boundaries are consistently enforced.

### Security

- Artifact uploads are validated and written while streaming.
- Bloom integration credentials are encrypted at rest and are never returned through settings APIs.
- Python and npm dependency vulnerability scans block CI on actionable findings.

## 1.0.0

- Initial beta release of Bud by EmbedLabs as a self-hosted test management and execution platform.
- Published a multi-architecture container image with PostgreSQL-backed deployment, migrations, health checks, and persistent artifact storage.
