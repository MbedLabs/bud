# Changelog

## 1.3.0 - unreleased

### Added

- Access has a People tab that shows each person's base role, every group they hold and their combined permissions.

### Changed

- Every email uses one structure: the product identity in the heading, one linked action and the same copy in HTML and plain text. The invitation, verification, password reset, access request and report request emails name Bud TMP in their next step.
- The product identity is fixed as Bud TMP by EmbedLabs across the application, emails, API, reports and run notifications. The sidebar shows Bud TMP with by EmbedLabs beneath it. The `BUD_APP_NAME` setting is removed; an existing environment variable or `.env` entry with that name is ignored.
- The confirmation dialogs, the Test Station rename dialog and the invite and email change dialogs close with Escape wherever the focus is.
- A source install needs Python 3.11 or later.
- The Access entry in the sidebar shows the same shield check icon as Bloom PLM.

### Fixed

- Administrator welcome emails confirm the account is ready and give product-specific next steps, with matching HTML and plain-text instructions. The obsolete one-time runner registration key instructions are removed.

### Security

- Pillow raised to 13.0.0, certifi to 2026.10.19, follow-redirects to 1.16.1, vitest to 4.1.12 and zod to 4.6.7, the patched releases.

## 1.2.0 - 2026-10-17

### Added

- Report requests from Bloom appear for report publishers on the dashboard and run page, and notify active publishers through configured SMTP. Publishers fulfill requests through report publishing or refuse with a reason; status returns to Bloom.

- Company logo on test-run PDF reports: a user with `settings.edit` uploads a company logo in Settings; it renders on the report letterhead (top-left) alongside the EmbedLabs tamper-evidence footer, which is always present. The Settings preview loads through the authenticated client so the uploader sees exactly what was stored.
- S3-compatible object storage: `STORAGE_BACKEND=s3` keeps run artifacts and generated reports in a bucket (AWS S3, MinIO, Hetzner, Ceph) under a per-instance prefix, with the local directory as a mirror that reads fall back to when the bucket does not answer (`STORAGE_LOCAL_MIRROR`, default on). `python -m app.storage migrate --to s3` copies existing files and checks their sizes; cleanup reconciles the bucket; `/api/ready` reports the storage. Local storage stays the default and is unchanged. Adds boto3 to the locked dependencies.
- Robot Framework runs (bud-runner `run-robot`): HTML artifacts (`text/html`, Robot's log.html and report.html) are accepted. Every artifact download is an attachment sent with `Content-Security-Policy: sandbox` and `X-Content-Type-Options: nosniff`, so user-supplied HTML or SVG never runs in the Bud origin. The Bloom sync event says how many results had no Bloom tc_id and how many skipped results were not sent.
- Access control: permissions are `resource.action` pairs: `evidence.view`, `reports.export`, `products.view`, `products.manage`, `stations.view`, `stations.manage`, `custom_runs.create`, `bloom_publish.execute`, `settings.view`, `settings.edit`, `audit.view`, `access.manage`. A policy is a named set of permissions, a group is a named set of policies, and a user can be in several groups. A user's permissions are those of their role plus those of all their groups. Roles: `viewer` has the Results policy, `developer` also has Custom runs and Reports publishing, `admin` has every permission. 8 default policies and 5 default groups (Results Viewers, Test Operators, Station Managers, Access Managers, Application Administrators) are created; changing or deleting one returns 409, `POST /{id}/duplicate` creates an editable copy. A group containing `stations.manage` can only be given to `admin` or `developer` users (422). Only `admin` can give Application Administrators and change policies (403). A user with `access.manage` can only create, change, delete or give groups whose permissions they have themselves (403). User management and deleting runs and artifacts stay `admin` only. Access is not limited by product.
- Access endpoints: `/api/policies` (with `/catalogue` and `/{id}/duplicate`), `/api/groups` (policies, members, `/{id}/duplicate`) and `GET /api/access/users`. `GET /api/auth/me` returns the user's `permissions`.
- Separate Users and Access pages: `/users` manages accounts; `/access`, for `admin` and users with `access.manage`, provides Assignments with group rosters, Groups with policy bundles, Policies with a Read/Write editor and Requests.
- Run notifications: when a run finishes, Bud posts it to every enabled channel under Settings, Notifications: Microsoft Teams (an Adaptive Card for a Power Automate Workflows URL, a MessageCard for a classic connector URL, chosen from the URL), Slack (Block Kit), Discord (embed) or plain JSON for any endpoint. The message carries the run, product, station and software under test, the counts and duration, up to five failed tests, the Bud link and the Bloom link or sync failure. A channel sends all runs, failures only, or the first failure after a green run; its URL is stored encrypted and shown as a prefix; an optional secret signs the JSON body (`X-Bud-Signature`). Each delivery is attempted up to three times and recorded, shown as a notify stage on the run timeline; Send test message checks a channel. Routing per product and per station is not in this release.
- Audit log: security-relevant events (authentication, accounts, groups, station registration, enrolment keys and station removal, configuration, deletions, exports, imports, attachments) are recorded with the acting user, the request id, the client address, the outcome and details without secrets; a failed sign-in is recorded although the request fails. Users with `audit.view` read it under Audit log (`GET /api/audit`, filtered by actor, action, target, product, outcome and time). No endpoint changes or deletes an event; `python -m app.audit prune --older-than-days N` removes old events on the operator's schedule. Event times are shown in the viewer's time zone.
- Run access requests: a run that returns 403 or 404 shows a page with a Request access button (`POST /api/access-requests`, `resource_type=test-run`). Every `admin` and every user with `access.manage` gets an email with a link to `/access`. One request per user and resource per 24 hours. Requests are decided with `POST /api/access-requests/{id}/decision`. Requests and decisions are written to the audit log; if the email fails, the request is kept and the user is told.
- Publish to Bloom requests: a user without `bloom_publish.execute` sees Request access instead of Publish on a run (`resource_type=publish-to-bloom`). Granting requires a `group_id` of a group that has `bloom_publish.execute` and adds the user to it (422 otherwise).
- Database: migrations `017_release120` and `018_report_requests` upgrade from 1.1.0 (`016_key_station_name`), including report requests. A database created by a pre-release 1.2.0 development image is converted as well: members of its development groups are moved to Test Operators (developer groups) or Results Viewers (viewer groups); the old group tables are kept and no longer used.
- Profile picture: a signed-in user uploads, replaces or removes their own picture under Settings, Account (PNG, JPEG or WebP up to 2 MB; stored as a PNG of at most 256 x 256 pixels without metadata, with the camera orientation applied). `GET`, `PUT` and `DELETE /api/auth/me/picture`; `/api/auth/me` reports `has_profile_picture`. Saved pictures appear in Users, the account menu, group memberships, audit actors and access requesters, with initials when none is stored. Replacing or removing a picture refreshes these identity views while preserving unrelated cached data.

### Changed

- Custom Run stores a human execution request and shows its assigned station; the execution link appears when that station claims it. Only authenticated Test Stations create execution records, update their execution state, submit raw results and upload artifacts; `POST /api/uploads` returns 403 for every user, `admin` included. Queued requests do not appear as completed or pending executions in reports and dashboard totals. Dashboard totals classify claimed executions as in progress until the station acknowledges completion, and a nonzero exit or execution error counts as failure even when no method results were produced.
- Run page and PDF reports: a skipped assertion and an information entry (a Robot keyword that checks nothing) are not counted as assertions; the run page shows them in neutral colour, the reports leave them out.
- Times written for people are given to the second, in UTC: the start, completion and generation times on PDF reports and the time in access-request emails.

### Fixed

- Signing out, and a session check that fails while a user is signed in, now reload the page, and a tab reloads when it next renews its session and finds it belongs to another user signed in from another tab. Nothing cached for the previous user stays in memory, and signing in empties the cache as well. Before, the next user in the same tab could be shown data cached for the previous one for up to five minutes.
- A database error while committing a request, such as a constraint violation, is answered with 409 or 500 and the request id; the commit now runs before the response is built instead of after it had started.
- Orphan cleanup measured its grace period from a UTC time read as local time, so on a host not running in UTC it was off by the UTC offset.
- User and runner API key timestamps in API responses carry the UTC marker (`Z`); without it the Users page showed the time of an email change request shifted by the viewer's UTC offset.

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
