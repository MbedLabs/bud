"""The CLI sign-in approval page of the built Bud UI in Chromium, its API calls answered from fixtures."""

import functools
import json
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from budtestlibrary import BudTestCase
from playwright.sync_api import sync_playwright

from tests.budtests.config import UiCliAuth as c
from tests.budtests.messages import UiCliAuth as m
from tests.budtests.parameters import UiCliAuth as p


class _BuiltUi(SimpleHTTPRequestHandler):
    """Serves the built UI; a path without a file answers index.html."""

    def send_head(self):
        """The file of the path, or index.html when there is none."""
        if not os.path.isfile(self.translate_path(self.path.split("?", 1)[0])):
            self.path = "/index.html"
        return super().send_head()

    def log_message(self, format, *args):
        """Writes no access log."""


class UiCliAuth(BudTestCase):
    """A signed-in viewer opens the approval page of a pending CLI sign-in."""

    def setUpClass(self):
        """Serve the built UI on a free loopback port and open Chromium with the API answered from
        fixtures."""
        handler = functools.partial(_BuiltUi, directory=str(c.DIST))
        self.server = ThreadingHTTPServer((c.HOST, 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://{c.HOST}:{self.server.server_address[1]}"
        self.fixtures = {
            ("POST", c.REFRESH_PATH): p.SIGN_IN,
            ("GET", c.ME_PATH): p.USER,
            ("GET", c.SESSION_PATH.format(session_id=p.SESSION_ID)): p.SESSION,
        }
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch()
        self.page = self.browser.new_page()
        self.page.set_default_timeout(c.TIMEOUT_MS)
        self.page.route(c.API_PATTERN, self._answer)

    def tearDownClass(self):
        """Close Chromium and stop serving the UI."""
        self.browser.close()
        self.playwright.stop()
        self.server.shutdown()
        self.server.server_close()

    def _answer(self, route):
        """Answer an API call from its fixture, or with 404."""
        body = self.fixtures.get((route.request.method, urlparse(route.request.url).path))
        route.fulfill(
            status=p.OK if body is not None else p.MISSING,
            content_type=c.JSON,
            body=json.dumps(body if body is not None else p.NOT_FOUND),
        )

    def bud_the_page_shows_eight_named_boxes_with_a_hyphen_after_the_fourth(self):
        """The request code group holds eight boxes named by position, with a hyphen between the fourth
        and the fifth."""
        self.page.goto(self.base + c.PAGE_ROUTE.format(session_id=p.SESSION_ID))
        group = self.page.get_by_role("group", name=m.GROUP_NAME)
        group.wait_for()
        names = group.evaluate(
            "group => Array.from(group.querySelectorAll('input')).map(e => e.getAttribute('aria-label'))"
        )
        self.assertEqual(len(names), p.BOXES, f"the group holds {p.BOXES} boxes")
        self.assertEqual(
            names,
            [m.BOX_NAME.format(number=number, boxes=p.BOXES) for number in range(1, p.BOXES + 1)],
            "each box is named by its position",
        )
        order = group.evaluate(
            "group => Array.from(group.querySelectorAll('input, span'))"
            ".map(e => e.tagName === 'INPUT' ? 'box' : e.textContent)"
        )
        self.assertEqual(order, p.BOX_ORDER, f"the group holds {p.BOX_ORDER}")
