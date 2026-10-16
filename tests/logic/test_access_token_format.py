"""Access tokens: a standard HS256 token decodes; an expired one or one with another
algorithm does not, and an expired runner token still decodes when expiry is not checked."""

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token


def _part(value: dict) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _signed(header: dict, payload: dict) -> str:
    signing_input = f"{_part(header)}.{_part(payload)}"
    hashes = {"HS256": hashlib.sha256, "HS512": hashlib.sha512}
    if header["alg"] not in hashes:
        return f"{signing_input}."
    digest = hmac.new(settings.SECRET_KEY.encode(), signing_input.encode(), hashes[header["alg"]])
    signature = base64.urlsafe_b64encode(digest.digest()).rstrip(b"=").decode()
    return f"{signing_input}.{signature}"


def _claims(minutes: int) -> dict:
    expires = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return {"sub": "7", "type": "user", "ver": 1, "exp": int(expires.timestamp())}


def test_a_standard_hs256_token_decodes():
    token = _signed({"alg": "HS256", "typ": "JWT"}, _claims(5))
    assert decode_access_token(token)["sub"] == "7"
    issued = create_access_token({"sub": "7", "type": "user", "ver": 1})
    assert decode_access_token(issued)["type"] == "user"


@pytest.mark.parametrize(
    "header, minutes",
    [
        ({"alg": "HS256", "typ": "JWT"}, -5),
        ({"alg": "HS512", "typ": "JWT"}, 5),
        ({"alg": "none", "typ": "JWT"}, 5),
    ],
)
def test_an_expired_token_or_another_algorithm_is_refused(header, minutes):
    assert decode_access_token(_signed(header, _claims(minutes))) is None


def test_an_expired_runner_token_decodes_without_the_expiry_check():
    payload = {**_claims(-60), "type": "runner", "jti": "abc"}
    token = _signed({"alg": "HS256", "typ": "JWT"}, payload)
    assert decode_access_token(token) is None
    assert decode_access_token(token, verify_exp=False)["jti"] == "abc"
