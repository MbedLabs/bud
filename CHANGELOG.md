# Changelog

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
