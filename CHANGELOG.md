# Changelog

## Unreleased

## 1.0.1 - 2026-09-07

### Added

- **Cloudron packaging.** Bud installs on a Cloudron box from the same image published for every other deployment; there is no separate Cloudron variant to build, test or keep in step. The manifest requests PostgreSQL and local storage and declares the mail addon optional, and the image runs under Cloudron's read-only root filesystem - application data and generated secrets live in `/app/data`, and everything else that needs writing is redirected to `/tmp` or `/run`, which is a fresh tmpfs on every boot. CI runs a Cloudron compatibility smoke test against the normal image, so the contract is checked on every build rather than at install time. `minBoxVersion` is 9.1.0, the release that introduced community publishing.

- **First-run setup.** An instance with no users offers to create its first administrator. `GET /api/setup/status` reports whether setup is required and `POST /api/setup` creates the account; the endpoint then closes permanently, refusing with 409 once any user exists, and takes a PostgreSQL advisory lock so two browsers racing cannot both succeed. A packaged install has no way to set the environment variables the seeded administrator relied on, and nothing in the Cloudron environment carries user identity - the eight `CLOUDRON_*` variables name domains and origins, not people - so the operator's own address is asked for rather than inferred.

- **The runner API key is shown once, to the browser that completed setup.** A packaged deployment generates `RUNNER_API_KEY` at first boot into `/app/data/secrets.env` and nothing in the product ever displayed it, so enrolling a test station required a shell on the server. It is now revealed at the end of setup behind a toggle, with a copy button, and held in component state only - deliberately never written to `localStorage` or `sessionStorage`, since a key that outlives the tab is not a one-time reveal, and a test asserts it appears in neither.

- **A confirmation email after setup**, carrying no key. Mail cannot be unsent or recalled and is retained far longer than the secret should be, so it says only that an administrator now exists and that anything shown during setup was not repeated. The send is best effort and never fatal: `SMTP_ENABLED` defaults to false under docker-compose and Cloudron's mail addon is optional, so a mail failure aborting setup would leave those installs unable to create an administrator at all.

- **Custom runs.** Pick test cases from what Bud already knows and queue them on the bench that can run them. `GET /api/test-catalog` lists every test case Bud has a record of, grouped by suite, with the Test Stations it has run on and how it last finished; `POST /api/test-runs/custom` queues the selection; `POST /api/runners/claim-run` hands a station its next queued run. The new Custom Run screen puts the three together.

  A test case can only be queued where it has already run — Bud never reads a station's workspace, so evidence is the only honest source, and a case that has never run does not appear. A selection spanning two stations therefore becomes **two queued runs, one per station**, rather than a refusal, and the screen says so before you commit. A case that has run on several stations follows the ones that had no choice, so it never splits a selection unnecessarily.

  The direction is a queue, not a push: Bud marks a run Pending and the station asks for its next one when it checks in. Nothing reaches into the lab, so a bench needs no inbound port. The claim is a compare-and-set on the run's status, so two pollers racing cannot both take the same run.

  `test_runs.selected_tests` carries the selection as the importable `module.Class` paths the station's loader takes. It is NULL for an ordinary run, whose `test_case_list` still names a list the station resolves in its own workspace — nothing about existing runs changes.

- Dashboard statistics can be filtered by time range, Test Station, and test suite.
- `GET /api/test-runs/stats` and `GET /api/test-runs/filter-options` expose those aggregates.
- `GET /api/test-runs` accepts a `suite` filter.
- `GET /api/test-runs` accepts `q` (matching the run name, the test case list, or the runner account) and `location` (every runner at a location, not one).
- `GET /api/test-runs/{run_id}/artifacts` lists the files uploaded against a run, and the run detail page shows them with a download for each. Artifacts could already be uploaded and fetched by id, but nothing enumerated them and nothing in the UI referenced them, so a screenshot or a capture attached to a run was reachable only by someone who already knew its integer id. Access is the run's own, and downloads go through the API client so they carry a token.
- The upload allowlist covers what a test run actually produces: CSV, SVG, PDF, `application/vnd.tcpdump.pcap`, `application/x-pcapng`, `application/cap`, gzip, tar, GIF and WebP join the existing types. Packet captures and vector plots previously depended on the client guessing `application/octet-stream`, and CSV and PDF were refused outright with a 415 in the middle of a CI run. HTML is still refused - it is the one shape that would turn a stored artifact into a scripting vector.
- `artifacts` is indexed on `test_run_id` and `created_at`. The table carried only its primary key, so listing a run's files, unlinking them when a run is deleted, and the retention sweep at every startup were each a sequential scan.

### Note for `bud_runner`

Two things are ready on Bud's side and need the matching half in the runner:

- **Artifacts.** `upload_artifact` exists in the runner's API client but no command calls it, so a CI run still sends only its results. Bud accepts and displays them.
- **Custom runs.** A station needs to poll `POST /api/runners/claim-run` and, when it receives a run, execute `selected_tests` — a list of `module.Class` paths, which is what `TestExecutor._load_test_class` already takes — instead of resolving `test_case_list` as a module path. A 204 means nothing is waiting.

### Changed

- Transactional mail is sent in Bud's own colours. Every template was hardcoded to `#1a73e8`, so both products sent identical Google-blue mail that matched neither of them. The palette is derived from the same HSL tokens `index.css` already defines, so the mail cannot drift from the product it came from. Copy is unchanged; only the shell was replaced, and its styles are inlined rather than kept in a `<style>` block, because several clients - Gmail among them - drop or rewrite head styles on forwarded mail, which left the buttons unstyled.

- The frontend is split by route. Every visit downloaded and parsed 448 KB of JavaScript in a single chunk before anything rendered; the entry chunk is now 348 KB across 20, with everything behind authentication loaded on demand. The screens a signed-out visitor can land on directly - login, setup, and the four opened straight from an email link - stay eager, because they are the first paint. The Suspense boundary sits at the layout's outlet rather than around the whole route table, so the sidebar and header stay mounted while a page loads. A test imports every declared lazy path and asserts a component comes back, since `lazy(() => import(...))` is not checked the way a static import is: a renamed module builds clean and fails only when a user navigates there.

- Dispatching a custom run reloaded each created run with its own query. That is now one statement, with the response still ordered by the plan rather than by whatever order the rows come back in.

- Coverage measurement was blind to most of the application. SQLAlchemy's async bridge runs endpoint bodies inside greenlets and the test client drives the app from a worker thread, neither of which coverage traces by default, so an endpoint could be exercised by a passing HTTP test and still be reported as entirely unhit. With `concurrency = ["thread", "greenlet"]` the real figure is 91%, not the 73% previously reported; the CI gate moves from 60% to 85%.

- Upgraded to React 19 and React Router 8, which resolves GHSA-qwww-vcr4-c8h2 (React Router RSC-mode CSRF). The frontend now imports from `react-router` instead of the retired `react-router-dom` package. Frontend builds and CI run on Node 24; Node 22.22 is the supported minimum.
- Upgraded `lucide-react`, whose pinned release declared support only up to React 18.
- The dependency audit no longer carries any reviewed-advisory exception; every advisory now fails the build.
- The migration history is collapsed into a single locked baseline of explicit DDL. The base revision previously called `Base.metadata.create_all()`, which meant it always produced whatever the models currently described, so every later revision had to be written with inspect-then-add guards and the real `ALTER` path was never exercised by the fresh-install CI check. The baseline keeps the identifier of the previously deployed head, so an existing database is recognised as up to date and is not re-migrated; no stamp or manual step is required.
- The container now runs `alembic upgrade head` before serving traffic, matching Bloom. A separate `docker compose run --rm bud alembic upgrade head` step is no longer needed.

### Fixed

- Mail on Cloudron. The packaging pointed `SMTP_PORT` at `CLOUDRON_MAIL_SMTP_PORT` (2525) while also setting `SMTP_STARTTLS=true`, but the relay offers STARTTLS only on `CLOUDRON_MAIL_STARTTLS_PORT` (2587); 2525 is plaintext and answers a STARTTLS command with "extension not supported". Probing the relay confirms it - 2525 no STARTTLS, 2587 STARTTLS, 2465 implicit TLS - so the port and the TLS mode are now chosen together, preferring the encrypted port.

- Mail transport failures are diagnosable. Every endpoint that sends mail catches `MailConfigurationError` and returns a 503 carrying the message, but nothing caught transport errors, so a failed invitation came back as a bare 500 with an empty body - no indication that mail was even involved. `send_email` now translates `smtplib` and socket failures into `MailDeliveryError`, naming the host, port and TLS mode alongside the underlying error. It subclasses `MailConfigurationError`, so all seven existing handlers pick it up unchanged, covering invitations, resends, password resets, verification and email changes at once.

- `packageUrl` is gone from the Cloudron manifest. Cloudron 9.2.0 rejects the whole manifest with "must NOT have additional properties" when it is present, so the app could not be installed at all. The packaging documentation lists it as a valid optional property, but the schema the box actually enforces does not accept it; probing every documented property against that schema, it is the only one rejected. `documentationUrl` already points at the repository.

- A guard fails the build on a Tailwind gradient class the app's own config does not define. Bud and Bloom define different gradient names, so a class copied between the repositories produces no CSS and no error - which is how Bloom's setup screen shipped with an invisible button. Bud was already clean; this keeps it that way.

- A run's result listing no longer carries the per-method traceback. Nothing renders it - the trace shown against a failure comes from inside that assertion - so `GET /api/results/{run_id}` was reading a full stack trace per failed method out of the database on every visit to a run and discarding it. The listing selects only the columns the screen draws; `GET /api/results/detail/{result_id}` still returns the traceback, and the column is still written on upload.
- `TestResult.artifacts` is gone from the frontend types. The backend has no such column and never sent one, so the field was always `undefined`.
- Searching the test-run list, and filtering it by location, reached every run rather than the twenty on screen. Both were applied in the browser to the page the server had already sent, while the pager went on reporting the server's unfiltered total - so a run on page three was invisible to a search that named it, picking a location showed only that location's runs which happened to be on the current page, and the footer read "Showing 1 to 20 of 137 runs" beside a table holding three. This matters most for location, which is how a lab with several benches is normally sliced.
- `latest_per_suite` no longer loads every test run in the database. It fetched all of them, deduplicated by suite name in Python and sliced the result - and the run list asks for it on every page view, so the cost grew with every run ever recorded. A window function does the same in one pass, and the count and the page stay in SQL. Filters are applied before the deduplication, so a suite name shared by two locations no longer leaves one of them looking idle.
- PDF reports. `GET /api/reports/test-runs.pdf` renders the current dashboard selection - time range, Test Station and suite - as a document with a passed/failed/skipped pie chart and breakdown tables per suite, per Test Station and per day. `GET /api/reports/test-runs/{run_id}.pdf` reports a single run, carrying its run id, station, product, timings and every recorded result. Both carry the Bud logo, a "Powered by EmbedLabs" footer on every page, and real PDF link annotations: the run's repositories, the run's page in Bud, and the EmbedLabs site are all clickable. The Dashboard and the run detail page each have a download button.

- Test run summary tiles reported assertion counts under a "Total Tests" label. Test cases and assertions are now counted separately and shown together on the Total, Passed, and Failed tiles.
- Dashboard counters were derived from only the first page of test runs, so the pass rate depended on the page size. They are now aggregated in the database across the whole filtered set, and runs still in progress no longer count against the pass rate.

### Security

- Revoking an invitation now revokes its link. It previously only deactivated the account, leaving the emailed token valid until its TTL: whoever held the link could still accept the invitation and set a password, which then worked the moment an administrator reactivated the account.

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
