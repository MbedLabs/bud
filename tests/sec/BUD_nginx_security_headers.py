"""
* @file     ${tests/sec/BUD_nginx_security_headers.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Every nginx location carries the security headers, not only those that set none.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests the repository's nginx.conf, security-headers.conf and Dockerfile.
"""

import re

from tests.sec.nginx_security_headers import NginxSecurityHeadersBase


def location_blocks(text, pattern):
    """Each location block of an nginx config, as its header line and its body."""
    blocks = []
    for match in re.finditer(pattern, text, re.MULTILINE):
        start = match.end()
        depth = 1
        index = start
        while index < len(text) and depth:
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
            index += 1
        blocks.append((match.group(1).strip(), text[start : index - 1]))
    return blocks


class NginxSecurityHeadersTest(NginxSecurityHeadersBase):

    def setUpClass(self):
        super().setUpClass()
        read = self.bud.bud_read_repository_file
        nginx = read(self.parameters.NGINX_CONF)
        self.tc_headers = read(self.parameters.SECURITY_HEADERS_CONF)
        self.tc_dockerfile = read(self.parameters.DOCKERFILE)
        self.tc_locations = location_blocks(nginx, self.parameters.NGINX_LOCATION)
        first = re.search(self.parameters.NGINX_LOCATION, nginx, re.MULTILINE)
        self.tc_server_head = nginx[: first.start()] if first else nginx
        self.tc_csp = next(
            line
            for line in self.tc_headers.splitlines()
            if self.parameters.CSP_HEADER in line and self.parameters.NGINX_ADD_HEADER in line
        )

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    NginxSecurityHeadersTest().run()
