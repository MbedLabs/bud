"""
* @file     ${tests/api/BUD_profile_picture_http.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    An account uploads, reads, replaces and removes its own picture, validated and normalized.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests two accounts with real bearer tokens, each scenario on a fresh app.
"""

import io

from PIL import Image, PngImagePlugin

from app.core.security import create_access_token
from app.models import User
from app.models.user import UserRole
from tests.api.profile_picture_http import ProfilePictureHttpBase


class ProfilePictureHttpTest(ProfilePictureHttpBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        purple, green, blue, orange = p.PICTURE_COLORS
        first, second = self.accounts()
        found = {"none yet": self.read(first).status_code}
        saved = self.upload(first, self.picture(purple))
        stored = self.read(first)
        size, _, metadata = self.picture_facts(stored.content)
        found.update(
            {
                "saved": saved.status_code,
                "flag": saved.json().get("has_profile_picture"),
                "bytes in view": "profile_picture" in saved.json(),
                "read": stored.status_code,
                "type": stored.headers.get("content-type"),
                "cache": stored.headers.get("cache-control"),
                "size": size,
                "metadata kept": metadata,
                "view flag": self.me(first).get("has_profile_picture"),
                "other none": self.read(second).status_code,
                "other saved": self.upload(second, self.picture(green)).status_code,
                "first unchanged": self.read(first).content == stored.content,
                "replaced saved": self.upload(first, self.picture(blue)).status_code,
                "replaced": self.read(first).content != stored.content,
            }
        )
        self.tc_round_trip = found
        first, _ = self.accounts()
        before = self.me(first)
        updated = self.bud.bud_request(
            p.PUT, p.ME_PATH, headers=first, json={"full_name": p.PICTURE_RENAMED}
        )
        self.tc_profile = {
            "saved": updated.status_code,
            "name": updated.json().get("full_name"),
            "before": before.get("permissions"),
            "after": updated.json().get("permissions"),
        }
        self.tc_rejected = {}
        for case, (data, mime, _) in p.PICTURE_REJECTED.items():
            first, _ = self.accounts()
            saved = self.upload(first, self.picture(purple)).status_code
            kept = self.read(first).content
            status = self.upload(first, data, mime).status_code
            self.tc_rejected[case] = (saved, status, self.read(first).content == kept)
        self.accounts()
        self.tc_signed_out = [
            self.bud.bud_request(p.GET, p.PICTURE_PATH).status_code,
            self.upload({}, self.picture(purple)).status_code,
            self.bud.bud_request(p.DELETE, p.PICTURE_PATH).status_code,
        ]
        self.tc_removal = self.removal()
        first, _ = self.accounts()
        huge = io.BytesIO()
        Image.new("1", p.PICTURE_HUGE_SIZE).save(huge, format="PNG")
        self.tc_bounds = {
            "mismatch": self.upload(first, self.picture(purple), p.PICTURE_JPEG).status_code,
            "huge": self.upload(first, huge.getvalue()).status_code,
            "none saved": self.read(first).status_code,
        }
        first, _ = self.accounts()
        original = io.BytesIO()
        exif = Image.Exif()
        exif[p.PICTURE_EXIF_ORIENTATION] = p.PICTURE_ROTATE_90
        Image.new("RGB", p.PICTURE_SIZE, orange).save(original, format="JPEG", exif=exif)
        saved = self.upload(first, original.getvalue(), p.PICTURE_JPEG)
        size, exif, _ = self.picture_facts(self.read(first).content)
        self.tc_jpeg = {"saved": saved.status_code, "size": size, "exif": exif}

    def picture_facts(self, content):
        """The size of a stored picture, whether it keeps EXIF data and whether it keeps the
        metadata text, or the reading error for each."""
        try:
            with Image.open(io.BytesIO(content)) as picture:
                return (
                    picture.size,
                    bool(picture.getexif()),
                    self.parameters.PICTURE_METADATA_KEY in picture.info,
                )
        except OSError as error:
            return str(error), str(error), str(error)

    def removal(self):
        """Remove one account's picture while the other keeps its own."""
        p = self.parameters
        purple, green, blue, _ = p.PICTURE_COLORS
        first, second = self.accounts()
        saved = [
            self.upload(first, self.picture(purple)).status_code,
            self.upload(second, self.picture(green)).status_code,
        ]
        before_first, before_second = self.me(first), self.me(second)
        second_picture = self.read(second).content
        removed = self.bud.bud_request(p.DELETE, p.PICTURE_PATH, headers=first)
        after_first = self.me(first)
        kept_keys = set(before_first) - p.PICTURE_VIEW_KEYS_CHANGED
        return {
            "saved": saved,
            "removed": removed.status_code,
            "flag": removed.json().get("has_profile_picture"),
            "bytes in view": "profile_picture" in removed.json(),
            "view before": {key: before_first.get(key) for key in kept_keys},
            "view after": {key: after_first.get(key) for key in kept_keys},
            "gone": self.read(first).status_code,
            "other view kept": self.me(second) == before_second,
            "other picture kept": self.read(second).content == second_picture,
            "removed again": self.bud.bud_request(
                p.DELETE, p.PICTURE_PATH, headers=first
            ).status_code,
            "saved again": self.upload(first, self.picture(blue)).status_code,
            "read again": self.read(first).status_code,
        }

    def accounts(self):
        """Start the app with two viewer accounts and return their bearer headers."""
        p = self.parameters
        self.bud.bud_start_app(signed_in=False)
        headers = []
        for index in range(p.PICTURE_USERS):
            user = self.bud.bud_add_to_app(
                User(
                    email=p.PICTURE_USER_EMAIL.format(index),
                    full_name=p.PICTURE_USER_NAME.format(index),
                    hashed_password=p.PICTURE_PASSWORD_HASH,
                    role=UserRole.viewer,
                )
            )
            token = create_access_token({"sub": str(user.id), "type": "user", "ver": 1})
            headers.append({"Authorization": f"Bearer {token}"})
        return headers

    def picture(self, color):
        """A PNG picture with dimensions and metadata that need normalizing."""
        buffer = io.BytesIO()
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text(
            self.parameters.PICTURE_METADATA_KEY, self.parameters.PICTURE_METADATA_TEXT
        )
        Image.new("RGB", self.parameters.PICTURE_SIZE, color).save(
            buffer, format="PNG", pnginfo=metadata
        )
        return buffer.getvalue()

    def upload(self, headers, data, mime=None):
        """Upload a picture the way the settings page does."""
        mime = mime or self.parameters.PICTURE_PNG
        return self.bud.bud_request(
            self.parameters.PUT,
            self.parameters.PICTURE_PATH,
            headers=headers,
            files={"file": (self.parameters.PICTURE_FILE, data, mime)},
        )

    def read(self, headers):
        """Read an account's own picture."""
        return self.bud.bud_request(
            self.parameters.GET, self.parameters.PICTURE_PATH, headers=headers
        )

    def me(self, headers):
        """An account's view of itself."""
        return self.bud.bud_request(
            self.parameters.GET, self.parameters.ME_PATH, headers=headers
        ).json()

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ProfilePictureHttpTest().run()
