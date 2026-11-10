"""
* @file     ${tests/sec/nginx_security_headers.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the security headers nginx sends.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the shared header file and its includes.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class NginxSecurityHeadersBase(BudAppTestCase):

    @parameterized(params.SECURITY_HEADERS)
    def bud_shared_file_sets_the_header(self, header):
        self.assertIn(
            self.parameters.NGINX_HEADER_LINE.format(header),
            self.tc_headers,
            msg=self.parameters.MSG_NGINX_HEADER,
            abort_on_fail=False,
        )

    def bud_every_header_is_sent_always(self):
        lines = [
            line.strip()
            for line in self.tc_headers.splitlines()
            if line.strip().startswith(self.parameters.NGINX_ADD_HEADER)
        ]
        self.print_variables({"add_header lines": lines})
        without_always = [line for line in lines if not line.endswith(self.parameters.NGINX_ALWAYS)]
        self.assertEqual(
            without_always, [], msg=self.parameters.MSG_NGINX_ALWAYS, abort_on_fail=False
        )

    def bud_server_block_includes_the_shared_file(self):
        self.assertIn(
            self.parameters.NGINX_INCLUDE,
            self.tc_server_head,
            msg=self.parameters.MSG_NGINX_SERVER_INCLUDE,
            abort_on_fail=False,
        )

    def bud_locations_with_headers_include_the_shared_file(self):
        setting = [
            name for name, body in self.tc_locations if self.parameters.NGINX_ADD_HEADER in body
        ]
        self.print_variables({"locations setting a header": setting})
        missing = [
            name
            for name, body in self.tc_locations
            if self.parameters.NGINX_ADD_HEADER in body
            and self.parameters.NGINX_INCLUDE not in body
        ]
        self.assertEqual(
            missing, [], msg=self.parameters.MSG_NGINX_LOCATION_INCLUDE, abort_on_fail=False
        )

    def bud_csp_forbids_inline_script(self):
        self.print_variables({"CSP": self.tc_csp})
        self.assertIn(
            self.parameters.CSP_SCRIPT_SELF,
            self.tc_csp,
            msg=self.parameters.MSG_CSP_SCRIPT_SELF,
            abort_on_fail=False,
        )
        script_sources = self.tc_csp.split(self.parameters.CSP_SCRIPT_SOURCE)[1].split(";")[0]
        self.assertNotIn(
            self.parameters.CSP_UNSAFE_INLINE,
            script_sources,
            msg=self.parameters.MSG_CSP_NO_INLINE,
            abort_on_fail=False,
        )
        self.assertIn(
            self.parameters.CSP_FRAME_ANCESTORS,
            self.tc_csp,
            msg=self.parameters.MSG_CSP_FRAMES,
            abort_on_fail=False,
        )

    def bud_image_ships_the_shared_file(self):
        self.assertIn(
            self.parameters.DOCKERFILE_HEADERS_COPY,
            self.tc_dockerfile,
            msg=self.parameters.MSG_IMAGE_SHIPS_HEADERS,
            abort_on_fail=False,
        )
