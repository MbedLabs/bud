"""
* @file     ${tests/logic/response_timestamps.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the timestamps of the API response models.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the response model scan and its UTC check.
"""

from tests.bud_test_base import BudAppTestCase


class ResponseTimestampsBase(BudAppTestCase):

    def bud_scan_finds_the_response_models(self):
        self.print_variables({"response models": len(self.tc_models)})
        self.assertGreater(
            len(self.tc_models),
            self.parameters.RESPONSE_MODELS_AT_LEAST,
            msg=self.parameters.MSG_RESPONSE_SCAN_COUNT,
            abort_on_fail=False,
        )

    def bud_scan_finds_models_of_the_api(self):
        api_models = [
            name
            for name in self.tc_models
            if name.startswith(self.parameters.RESPONSE_MODEL_API_PREFIX)
        ]
        self.print_variables({"app.api response models": api_models})
        self.assertTrue(
            bool(api_models),
            msg=self.parameters.MSG_RESPONSE_SCAN_API,
            abort_on_fail=False,
        )

    def bud_every_response_timestamp_is_utc(self):
        self.assertEqual(
            self.tc_unmarked,
            self.parameters.RESPONSE_UNMARKED,
            msg=self.parameters.MSG_RESPONSE_UTC,
            abort_on_fail=False,
        )
