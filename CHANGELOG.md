# Changelog

## Unreleased

### Security and reliability

- enforce user, runner, and Test Station authorization boundaries across API routes
- stream artifact uploads with per-file, per-run, rate, concurrency, and free-space limits
- add artifact retention and orphan-file cleanup
- store Bloom result-sync credentials encrypted and never return them through settings APIs
- run blocking Python and npm dependency vulnerability checks in CI

### Integration

- use Bloom's short-lived, narrowly scoped `test-results:write` service credential
- clarify that Bud sends test-case outcomes by Bloom `tc_id` and never synchronizes campaigns

## 1.0.0

- Combined the Bud backend and web interface into one product repository and image.
- Added PostgreSQL-backed deployment, migrations, health checks, and product CI.
