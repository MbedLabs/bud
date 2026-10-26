# Safe local testing

Pytest always disables operator dotenv loading. Inherited application signing keys, administrator credentials, integration keys, SMTP settings and storage credentials are replaced with test-only values before application imports. Both prefixed and unprefixed settings are covered. Ambient AWS credentials and provider paths are replaced with dummy credentials; SDK credential files and metadata access are disabled.

PostgreSQL tests accept only the test_user/test_password identity on localhost or loopback at the dedicated test port 15432 (the default when DATABASE_URL is unset), with database test_bud. The local development ports 5432, 5433 and 5434 and a URL without an explicit port are refused. Connection override query parameters and alternate drivers are rejected. SQLite startup URLs must use an in-memory database. An unsafe explicit DATABASE_URL stops collection without printing its value. Tests that inspect configuration may set synthetic values inside the test.

Test SMTP connects only to a Mailpit on loopback at the dedicated test port 11025. TEST_SMTP_PORT may select another unprivileged port, but the local development ports 25, 465, 587, 1025, 2525 and 8025 are refused, so no test mail reaches the development Mailpit. SMTP authentication is rejected before any AUTH payload is sent. Mailpit uses no SMTP username, password or TLS. Start the test services before running pytest, with their own names and loopback test ports:

```sh
docker run -d --rm --name test-pg -e POSTGRES_USER=test_user -e POSTGRES_PASSWORD=test_password -e POSTGRES_DB=test_bud --tmpfs /var/lib/postgresql/data -p 127.0.0.1:15432:5432 postgres:16
docker run -d --rm --name test-mailpit -p 127.0.0.1:11025:1025 -p 127.0.0.1:18025:8025 axllent/mailpit:latest --disable-version-check
```

The captured mailbox is available at http://localhost:18025. CI starts its own Mailpit service. Unit tests may replace the SMTP transport with an in-process fake; they do not need an external mail service. Do not source operator environment files before running tests or migrations. Set BUD_DOTENV_DISABLED=1 for migration and standalone validation commands, which run outside pytest.
