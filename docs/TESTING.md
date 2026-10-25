# Safe local testing

Pytest always disables operator dotenv loading. Inherited application signing keys, administrator credentials, integration keys, SMTP settings and storage credentials are replaced with test-only values before application imports. Both prefixed and unprefixed settings are covered. Ambient AWS credentials and provider paths are replaced with dummy credentials; SDK credential files and metadata access are disabled.

PostgreSQL tests accept only the test_user/test_password identity on localhost or loopback, with database test_bud. Connection override query parameters and alternate drivers are rejected. SQLite startup URLs must use an in-memory database. An unsafe explicit DATABASE_URL stops collection without printing its value. Tests that inspect configuration may set synthetic values inside the test.

Test SMTP connects only to local Mailpit on port 1025. SMTP authentication is rejected before any AUTH payload is sent. Mailpit uses no SMTP username, password or TLS. Run Mailpit locally before testing actual email delivery:

```sh
docker run -d --name test-mailpit -p 127.0.0.1:1025:1025 -p 127.0.0.1:8025:8025 axllent/mailpit:latest --disable-version-check
```

The captured mailbox is available at http://localhost:8025. CI starts its own Mailpit service. Unit tests may replace the SMTP transport with an in-process fake; they do not need an external mail service. Do not source operator environment files before running tests or migrations. Set BUD_DOTENV_DISABLED=1 for migration and standalone validation commands, which run outside pytest.
