"""
* @file     ${tests/sec/BUD_trusted_proxy_address.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The client address comes from X-Forwarded-For only through a proxy in TRUSTED_PROXY_NETWORKS.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests requests delivered as the image delivers them, each scenario on a fresh app.
"""

import ipaddress
from unittest import mock

from app.core import observability
from app.core.config import settings
from app.models import AuditEvent
from tests.sec.trusted_proxy_address import TrustedProxyAddressBase


class TrustedProxyAddressTest(TrustedProxyAddressBase):

    def setUpClass(self):
        super().setUpClass()
        p, send = self.parameters, self.bud.bud_request_through_proxy
        networks = [ipaddress.ip_network(p.PROXY_NETWORK)]
        self.tc_default = settings.model_fields["TRUSTED_PROXY_NETWORKS"].default
        trusted = mock.patch.object(settings, "TRUSTED_PROXY_NETWORKS", networks)
        self.tc_addresses = {}
        for case, (trust, peer, forwarded, _) in p.PROXY_ADDRESS_CASES.items():
            self.bud.bud_start_app(signed_in=False)
            with mock.patch.object(settings, "TRUSTED_PROXY_NETWORKS", networks if trust else []):
                response = send(p.GET, p.HEALTH_PATH, peer, forwarded)
            self.tc_addresses[case] = (response.status_code, self.recorded_address(response))
        self.bud.bud_start_app(signed_in=False)
        with trusted:
            self.tc_refusals = []
            for _ in range(p.REFUSALS_BELOW_THRESHOLD):
                for client in (p.PROXY_OUTSIDER, p.PROXY_OTHER_OUTSIDER):
                    self.tc_refusals.append(
                        send(p.GET, p.AUTH_ME_PATH, p.PROXY_ADDRESS, client).status_code
                    )
            self.tc_flags_before = self.bud.bud_find_in_app(AuditEvent, action=p.REFUSALS_ACTION)
            last = send(p.GET, p.AUTH_ME_PATH, p.PROXY_ADDRESS, p.PROXY_OUTSIDER)
            self.tc_refusals.append(last.status_code)
        self.tc_flags = self.bud.bud_find_in_app(AuditEvent, action=p.REFUSALS_ACTION)
        self.tc_last_address = self.recorded_address(last)
        self.bud.bud_start_app(signed_in=False)
        with trusted:
            self.tc_logins = [
                send(
                    p.POST, p.LOGIN_PATH, p.PROXY_ADDRESS, p.PROXY_OUTSIDER, json=p.PROXY_LOGIN
                ).status_code
                for _ in range(p.PROXY_LOGIN_ATTEMPTS)
            ]
            self.tc_other_login = send(
                p.POST, p.LOGIN_PATH, p.PROXY_ADDRESS, p.PROXY_OTHER_OUTSIDER, json=p.PROXY_LOGIN
            ).status_code
        self.tc_walks = {
            case: observability.forwarded_client(peer, hops, networks if trust else [])
            for case, (peer, hops, trust, _) in p.PROXY_WALK_CASES.items()
        }
        self.tc_nginx = self.bud.bud_read_repository_file(p.NGINX_CONF)
        commands = [
            line
            for line in self.bud.bud_read_repository_file(p.SUPERVISORD_CONF).splitlines()
            if line.startswith(p.UVICORN_COMMAND)
        ]
        self.tc_uvicorn = commands[0] if len(commands) == 1 else str(commands)

    def recorded_address(self, response):
        """The client address the api.request event of a response recorded."""
        events = self.bud.bud_find_in_app(
            AuditEvent,
            action=self.parameters.API_REQUEST_ACTION,
            request_id=response.headers.get("x-request-id"),
        )
        return events[0].ip if len(events) == 1 else [event.ip for event in events]

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    TrustedProxyAddressTest().run()
