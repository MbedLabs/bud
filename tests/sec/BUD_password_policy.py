"""
* @file     ${tests/sec/BUD_password_policy.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The password policy holds at every entry point where a user chooses a password.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests the shared validator and the four request schemas that use it.
"""

from app.core.passwords import PASSWORD_MAX_BYTES, PASSWORD_MIN_LENGTH, validate_password_strength
from app.schemas import auth
from tests.sec.password_policy import PasswordPolicyBase


class PasswordPolicyTest(PasswordPolicyBase):

    def setUpClass(self):
        super().setUpClass()
        attempt, validate = self.bud.bud_attempt, validate_password_strength
        minimum, self.max_bytes = PASSWORD_MIN_LENGTH, PASSWORD_MAX_BYTES
        character = self.parameters.PASSWORD_CHARACTER
        self.minimum_password = character * minimum
        self.minimum = attempt(lambda: validate(self.minimum_password))
        lengths = dict(zip(self.parameters.PASSWORD_SHORT_CASES, (0, 1, minimum - 1)))
        self.short = {
            case: attempt(lambda length=length: validate(character * length))
            for case, length in lengths.items()
        }
        self.overlong = attempt(lambda: validate(character * (self.max_bytes + 1)))
        self.multibyte = attempt(lambda: validate(self.parameters.PASSWORD_MULTIBYTE))
        self.schema_short = {}
        self.schema_valid = {}
        for schema, (field, values) in self.parameters.PASSWORD_SCHEMAS.items():
            model = getattr(auth, schema)
            self.schema_short[schema] = attempt(
                lambda model=model, field=field, values=values: model(
                    **values, **{field: self.parameters.PASSWORD_SHORT}
                )
            )
            self.schema_valid[schema] = attempt(
                lambda model=model, field=field, values=values: model(
                    **values, **{field: self.parameters.PASSWORD_VALID}
                )
            )

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    PasswordPolicyTest().run()
