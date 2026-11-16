"""
* @file     ${tests/sec/trusted_proxy_address.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests which client address Bud records behind a proxy.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of the forwarded address and the image's proxies.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class TrustedProxyAddressBase(BudAppTestCase):

    def bud_no_proxy_is_trusted_by_default(self):
        self.assertEqual(self.default, [], msg=self.parameters.MSG_PROXY_DEFAULT)

    @parameterized(params.PROXY_ADDRESS_CASES)
    def bud_audit_records_the_resolved_address(self, case):
        status, address = self.addresses[case]
        self.print_variables({"case": case, "status": status, "recorded address": address})
        self.assertEqual(status, self.parameters.STATUS_OK, msg=self.parameters.MSG_PROXY_ANSWERS)
        self.assertEqual(
            address,
            self.parameters.PROXY_ADDRESS_CASES[case][3],
            msg=self.parameters.MSG_PROXY_ADDRESS,
        )

    def bud_repeated_refusals_count_the_resolved_address(self):
        p = self.parameters
        self.print_variables({"flags before": self.flags_before, "flags after": self.flags})
        self.assertEqual(
            self.refusals,
            [p.STATUS_UNAUTHORIZED] * len(self.refusals),
            msg=p.MSG_PROXY_REFUSED,
        )
        self.assertEqual(self.flags_before, [], msg=p.MSG_PROXY_NOT_FLAGGED)
        self.assertEqual(len(self.flags), 1, msg=p.MSG_PROXY_FLAGGED, abort_on_fail=True)
        self.assertEqual(self.flags[0].ip, p.PROXY_OUTSIDER, msg=p.MSG_PROXY_FLAG_ADDRESS)
        self.assertEqual(
            self.flags[0].details.get("denied_requests"),
            p.REFUSALS_FLAGGED,
            msg=p.MSG_PROXY_FLAG_COUNT,
        )
        self.assertEqual(self.last_address, p.PROXY_OUTSIDER, msg=p.MSG_PROXY_ADDRESS)

    def bud_rate_limit_counts_the_resolved_address(self):
        p = self.parameters
        self.print_variables({"sign-ins": self.logins, "other client": self.other_login})
        self.assertEqual(self.logins[-1], p.STATUS_TOO_MANY, msg=p.MSG_PROXY_RATE_LIMITED)
        self.assertEqual(self.other_login, p.STATUS_UNAUTHORIZED, msg=p.MSG_PROXY_OTHER_CLIENT)

    @parameterized(params.PROXY_WALK_CASES)
    def bud_forwarded_client_walks_from_the_right(self, case):
        self.assertEqual(
            self.walks[case],
            self.parameters.PROXY_WALK_CASES[case][3],
            msg=self.parameters.MSG_PROXY_WALK,
        )

    def bud_image_nginx_appends_the_received_address(self):
        p = self.parameters
        self.assertEqual(
            self.nginx.count(p.NGINX_PROXY_PASS),
            p.NGINX_LOCATIONS_PROXIED,
            msg=p.MSG_NGINX_PROXIED,
        )
        self.assertEqual(
            self.nginx.count(p.NGINX_FORWARDED_FOR),
            p.NGINX_LOCATIONS_PROXIED,
            msg=p.MSG_NGINX_APPENDS,
        )
        self.assertNotIn(p.NGINX_REAL_IP, self.nginx, msg=p.MSG_NGINX_NO_REAL_IP)

    def bud_image_uvicorn_trusts_loopback_only(self):
        self.print_variables({"uvicorn command": self.uvicorn})
        self.assertRegex(
            self.uvicorn,
            f"{self.parameters.UVICORN_FORWARDED_ALLOW}$",
            msg=self.parameters.MSG_UVICORN_LOOPBACK,
        )
