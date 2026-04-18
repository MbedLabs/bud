from datetime import timedelta
import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-at-least-32-characters-long")

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_runner_token,
)


def test_create_access_token_round_trip():
    token = create_access_token({"sub": "user@example.com"}, expires_delta=timedelta(minutes=5))
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "user@example.com"
    assert "exp" in payload


def test_generate_runner_token_contains_runner_claims():
    token = generate_runner_token("runner-01")
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "runner-01"
    assert payload["type"] == "runner"
