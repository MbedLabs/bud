"""
* @file     ${tests/logic/BUD_config_settings.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Settings read BUD_ and plain variables, keep safe upload defaults and refuse weak production values.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module builds the settings without a dotenv file in an environment cleared of every setting variable.
"""

import os
from unittest import mock

from app.core import config
from tests.logic.config_settings import ConfigSettingsBase


def type_name(value):
    """The type name of a value."""
    return type(value).__name__


class ConfigSettingsTest(ConfigSettingsBase):

    def setUpClass(self):
        super().setUpClass()
        self.tc_checks = {case: self.checks(case) for case in self.parameters.CONFIG_CASES}

    def build(self, environment):
        """The settings built from an environment holding only the given setting variables, or the
        error building them raises."""
        with mock.patch.dict(os.environ):
            for key in self.parameters.CONFIG_ENV_KEYS:
                os.environ.pop(key, None)
            os.environ.update(environment)
            try:
                return config.Settings(_env_file=None)
            except ValueError as error:
                return error

    def checks(self, case):
        """The named checks of one environment."""
        p = self.parameters
        environment, values, error = p.CONFIG_CASES[case]
        built = self.build(environment)
        if error:
            return {
                "the settings are refused": (isinstance(built, ValueError), True),
                f"the refusal names {error}": (
                    isinstance(built, ValueError) and error in str(built),
                    True,
                ),
            }
        checks = {"the settings are built": (type_name(built), "Settings")}
        for field, expected in values.items():
            found = getattr(built, field, None)
            checks[field] = (str(found) if field in p.CONFIG_STRING_FIELDS else found, expected)
        if "BUD_SMTP_FROM_NAME" in environment:
            checks["the sender name is not a setting"] = (
                hasattr(built, p.CONFIG_DROPPED_FIELD),
                False,
            )
        if "BUD_DB_PASSWORD" in environment:
            checks["the database address carries the password"] = (
                p.CONFIG_BUILT_PASSWORD in str(getattr(built, "DATABASE_URL", "")),
                True,
            )
        return checks

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ConfigSettingsTest().run()
