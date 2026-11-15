"""
* @file     ${tests/api/BUD_users.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Deleting a user removes their tokens and clears them as inviter; nobody deletes themselves.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests an administrator deleting users on the whole app.
"""

from datetime import datetime, timezone

from app.models.user import User, UserRole
from app.models.user_token import UserToken, UserTokenPurpose
from tests.api.users import UsersBase


class UsersTest(UsersBase):

    def setUpClass(self):
        super().setUpClass()
        self.bud.bud_start_app()
        user = self.bud.bud_add_to_app(
            User(
                email=self.parameters.USER_DELETED_EMAIL,
                full_name=self.parameters.USER_DELETED_NAME,
                hashed_password=self.parameters.USER_HASH,
                role=UserRole.viewer,
                is_active=True,
            )
        )
        self.bud.bud_add_to_app(
            UserToken(
                user_id=user.id,
                purpose=UserTokenPurpose.invite,
                token_hash=self.parameters.USER_INVITE_HASH,
                expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
                + self.parameters.USER_INVITE_LIFETIME,
            )
        )
        self.tc_delete = self.bud.bud_request(
            self.parameters.DELETE, self.parameters.USER_PATH.format(user.id)
        )
        self.tc_deleted_users = self.bud.bud_find_in_app(User, id=user.id)
        self.tc_deleted_tokens = self.bud.bud_find_in_app(UserToken, user_id=user.id)
        inviter = self.bud.bud_add_to_app(
            User(
                email=self.parameters.USER_INVITER_EMAIL,
                full_name=self.parameters.USER_INVITER_NAME,
                hashed_password=self.parameters.USER_HASH,
                role=UserRole.admin,
            )
        )
        invitee = self.bud.bud_add_to_app(
            User(
                email=self.parameters.USER_INVITEE_EMAIL,
                full_name=self.parameters.USER_INVITEE_NAME,
                hashed_password=self.parameters.USER_HASH,
                role=UserRole.viewer,
                invited_by_user_id=inviter.id,
            )
        )
        self.tc_inviter_delete = self.bud.bud_request(
            self.parameters.DELETE, self.parameters.USER_PATH.format(inviter.id)
        )
        self.tc_invitee = self.bud.bud_find_in_app(User, id=invitee.id)[0]
        self.tc_self = self.bud.bud_request(
            self.parameters.DELETE, self.parameters.USER_PATH.format(self.parameters.TEST_ADMIN_ID)
        )
        self.tc_missing = self.bud.bud_request(
            self.parameters.DELETE,
            self.parameters.USER_PATH.format(self.parameters.USER_MISSING_ID),
        )

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    UsersTest().run()
