"""
* @file     ${tests/logic/BUD_access_token_format.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A standard HS256 token decodes; an expired one or one with another algorithm does not.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests hand-signed tokens and an expired Test Station token.
"""

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from app.core import security
from app.core.config import settings
from tests.logic.access_token_format import AccessTokenFormatBase


def token_part(value):
    """One base64url token part of a JSON value, without padding."""
    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def signed_token(header, payload, hashes):
    """A token signed with the secret key by the header's algorithm, unsigned for another one."""
    signing_input = f"{token_part(header)}.{token_part(payload)}"
    if header["alg"] not in hashes:
        return f"{signing_input}."
    digest = hmac.new(
        settings.SECRET_KEY.encode(),
        signing_input.encode(),
        getattr(hashlib, hashes[header["alg"]]),
    )
    signature = base64.urlsafe_b64encode(digest.digest()).rstrip(b"=").decode()
    return f"{signing_input}.{signature}"


class AccessTokenFormatTest(AccessTokenFormatBase):

    def setUpClass(self):
        super().setUpClass()
        hashes = self.parameters.TOKEN_HASHES
        self.tc_standard = security.decode_access_token(
            signed_token(
                self.parameters.TOKEN_HS256,
                self.claims(self.parameters.TOKEN_VALID_MINUTES),
                hashes,
            )
        )
        self.tc_issued = security.decode_access_token(
            security.create_access_token(
                {
                    "sub": self.parameters.TOKEN_USER_ID,
                    "type": self.parameters.TOKEN_USER_TYPE,
                    "ver": self.parameters.TOKEN_VERSION,
                }
            )
        )
        self.tc_refused = {
            case: security.decode_access_token(signed_token(header, self.claims(minutes), hashes))
            for case, (header, minutes) in self.parameters.TOKEN_REFUSED_CASES.items()
        }
        station = signed_token(
            self.parameters.TOKEN_HS256,
            {
                **self.claims(self.parameters.TOKEN_STATION_EXPIRED_MINUTES),
                "type": self.parameters.TOKEN_STATION_TYPE,
                "jti": self.parameters.TOKEN_STATION_JTI,
            },
            hashes,
        )
        self.tc_station_checked = security.decode_access_token(station)
        self.tc_station_unchecked = security.decode_access_token(station, verify_exp=False)

    def claims(self, minutes):
        """User claims expiring the given number of minutes from now."""
        expires = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        return {
            "sub": self.parameters.TOKEN_USER_ID,
            "type": self.parameters.TOKEN_USER_TYPE,
            "ver": self.parameters.TOKEN_VERSION,
            "exp": int(expires.timestamp()),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    AccessTokenFormatTest().run()
