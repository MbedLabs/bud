"""The CLI sign-in approval page of the built Bud UI in Chromium, its API calls answered from fixtures."""

import functools
import json
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from budtestlibrary import BudTestCase
from playwright.sync_api import TimeoutError as PlaywrightTimeout
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
    """A signed-in viewer answers a pending CLI sign-in on its approval page."""

    def setUpClass(self):
        """Serve the built UI on a free loopback port and start Chromium."""
        handler = functools.partial(_BuiltUi, directory=str(c.DIST))
        self.server = ThreadingHTTPServer((c.HOST, 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://{c.HOST}:{self.server.server_address[1]}"
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch()

    def tearDownClass(self):
        """Close Chromium and stop serving the UI."""
        self.browser.close()
        self.playwright.stop()
        self.server.shutdown()
        self.server.server_close()

    def setUp(self):
        """A fresh page whose API calls get the default answers and whose loopback callback answers
        a blank page."""
        self.answers = {
            ("POST", c.REFRESH_PATH): [(p.OK, p.SIGN_IN)],
            ("GET", c.ME_PATH): [(p.OK, p.USER)],
            ("GET", c.SESSION_PATH.format(session_id=p.SESSION_ID)): [(p.OK, p.CODE_SESSION)],
            ("POST", c.CHECK_PATH): [(p.OK, p.NOTHING)],
            ("POST", c.APPROVE_PATH): [(p.OK, p.EXCHANGE)],
            ("POST", c.DENY_PATH): [(p.OK, p.NOTHING)],
        }
        self.calls = []
        self.held = []
        self.context = self.browser.new_context(permissions=c.CLIPBOARD)
        self.page = self.context.new_page()
        self.page.set_default_timeout(c.TIMEOUT_MS)
        self.page.route(c.API_PATTERN, self._answer)
        self.page.route(c.LOOPBACK_PATTERN, lambda route: route.fulfill(status=p.OK, content_type=c.HTML, body=""))

    def tearDown(self):
        """Close the page."""
        self.context.close()

    def _answer(self, route):
        """Record an API call and answer it with the next answer set for it, holding it when that
        answer is p.HOLD, or with 404."""
        request = route.request
        path = urlparse(request.url).path
        self.calls.append((request.method, path, request.post_data_json if request.post_data else None))
        queue = self.answers.get((request.method, path))
        if not queue:
            route.fulfill(status=p.MISSING, content_type=c.JSON, body=json.dumps(p.NOT_FOUND))
            return
        answer = queue.pop(0) if len(queue) > 1 else queue[0]
        if answer == p.HOLD:
            self.held.append(route)
            return
        status, body = answer
        route.fulfill(status=status, content_type=c.JSON, body=json.dumps(body))

    def answer(self, method: str, path: str, *answers):
        """Set the answers of an API call, used in order; the last one repeats."""
        self.answers[(method, path)] = list(answers)

    def callback_session(self, port: str) -> dict:
        """A pending callback-mode session whose loopback listener is on a port."""
        return {**p.CODE_SESSION, "mode": "callback", "redirect_uri": p.CALLBACK.format(port=port)}

    def open_request(self):
        """Open the approval page of the pending session and wait for its first box."""
        self.page.goto(self.base + c.PAGE_ROUTE.format(session_id=p.SESSION_ID))
        self.shown(self.box(1))

    def shown(self, locator) -> bool:
        """Whether the locator becomes visible within the timeout."""
        try:
            locator.first.wait_for(state="visible")
            return True
        except PlaywrightTimeout:
            return False

    def text(self, text: str):
        """The element showing exactly a text."""
        return self.page.get_by_text(text, exact=True)

    def box(self, number: int):
        """The request code box at a position."""
        return self.page.get_by_label(m.BOX_NAME.format(number=number, boxes=p.BOXES), exact=True)

    def values(self) -> list[str]:
        """The characters in the boxes, in order."""
        return [self.box(number).input_value() for number in range(1, p.BOXES + 1)]

    def button(self, name: str):
        """The button with a name."""
        return self.page.get_by_role("button", name=name, exact=True)

    def type_code(self, text: str):
        """Type text into the boxes from the first one."""
        self.box(1).click()
        self.page.keyboard.type(text)

    def paste(self, text: str):
        """Paste text into the first box the way a browser delivers a clipboard paste."""
        self.box(1).evaluate(
            """(element, text) => {
                const data = new DataTransfer();
                data.setData('text', text);
                element.dispatchEvent(new ClipboardEvent('paste', {clipboardData: data, bubbles: true, cancelable: true}));
            }""",
            text,
        )

    def matching_code(self):
        """Type the matching code and wait for the page to confirm it."""
        self.type_code(p.TYPED)
        self.assertTrue(self.shown(self.text(m.MATCH)), f"{m.MATCH!r} is shown", abort_on_fail=True)

    def bodies(self, method: str, path: str) -> list:
        """The bodies the page sent to an API call, in order."""
        return [body for (sent, to, body) in self.calls if sent == method and to == path]

    def local_time(self, value: str) -> str:
        """A time the way the page's browser writes it."""
        return self.page.evaluate("value => new Date(value).toLocaleString()", value)

    def page_text(self) -> str:
        """The text of the whole page."""
        return self.page.inner_text("body")

    def bud_the_page_shows_eight_named_boxes_with_a_hyphen_after_the_fourth(self):
        """The request code group holds eight boxes named by position, with a hyphen between the fourth
        and the fifth."""
        self.open_request()
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

    def bud_shows_the_unverified_client_name_the_account_the_times_and_the_warning(self):
        """Empty boxes, the help, the unverified client name, the account, both times, the warning,
        Approve and Deny without Cancel, after one lookup of the session."""
        self.open_request()
        self.assertTrue(self.shown(self.text(p.CLIENT_NAME)), f"{p.CLIENT_NAME!r} is shown")
        self.assertEqual(self.values(), p.EMPTY, "the boxes are empty")
        account = m.ACCOUNT.format(name=p.USER["full_name"], email=p.USER["email"])
        times = m.TIMES.format(requested=self.local_time(p.CREATED_AT), expires=self.local_time(p.EXPIRES_AT))
        shown = self.page_text()
        for text in (m.HELP, m.UNVERIFIED, account, times, m.WARNING):
            self.assertIn(member=text, container=shown, msg=f"{text!r} is shown")
        self.assertEqual(self.button(m.APPROVE).count(), p.ONE, "Approve is shown")
        self.assertEqual(self.button(m.DENY).count(), p.ONE, "Deny is shown")
        self.assertEqual(self.button(m.CANCEL).count(), 0, "no Cancel is shown")
        session = c.SESSION_PATH.format(session_id=p.SESSION_ID)
        self.assertEqual(
            [to for (sent, to, _) in self.calls if sent == "GET" and to == session],
            [session],
            "the session is looked up once",
        )

    def bud_warns_before_approve_in_code_mode_only(self):
        """A code-mode request shows the one-time code warning; a callback-mode request does not."""
        self.open_request()
        self.assertTrue(self.shown(self.text(m.CODE_WARNING)), "the code warning is shown in code mode")
        self.answer("GET", c.SESSION_PATH.format(session_id=p.SESSION_ID), (p.OK, self.callback_session(p.CALLBACK_PORT)))
        self.open_request()
        self.assertTrue(self.shown(self.box(1)), "the boxes are shown in callback mode")
        self.assertEqual(self.text(m.CODE_WARNING).count(), 0, "no code warning is shown in callback mode")

    def bud_shows_the_one_time_code_and_copies_it_only_on_the_user_action(self):
        """Approve shows the exchange code with its warning; the clipboard gets the code only after Copy
        code."""
        self.open_request()
        self.page.evaluate("navigator.clipboard.writeText('')")
        self.matching_code()
        self.button(m.APPROVE).click()
        self.assertTrue(self.shown(self.text(p.EXCHANGE_CODE)), "the exchange code is shown")
        self.assertEqual(
            self.bodies("POST", c.APPROVE_PATH),
            [{"session_id": p.SESSION_ID, "request_code": p.CODE}],
            "Approve sends the session and the code",
        )
        self.assertEqual(self.page.evaluate("navigator.clipboard.readText()"), "", "nothing is copied before Copy code")
        self.button(m.COPY).click()
        self.page.wait_for_timeout(c.SETTLE_MS)
        self.assertEqual(
            self.page.evaluate("navigator.clipboard.readText()"), p.EXCHANGE_CODE, "Copy code copies the code"
        )
        self.assertTrue(self.shown(self.text(m.PASTE_ONLY)), f"{m.PASTE_ONLY!r} is shown")

    def bud_reports_a_rejected_approval_without_a_code(self):
        """A failed approval shows an alert and no exchange code."""
        self.answer("POST", c.APPROVE_PATH, (p.SERVER_ERROR, p.REFUSED))
        self.open_request()
        self.matching_code()
        self.button(m.APPROVE).click()
        self.assertTrue(self.shown(self.page.get_by_role("alert")), "an alert is shown")
        self.assertEqual(self.text(p.EXCHANGE_CODE).count(), 0, "no exchange code is shown")

    def _approved_callback(self, port: str):
        """An approved callback request goes to its loopback listener on the port, without a code on
        the page."""
        session = self.callback_session(port)
        self.answer("GET", c.SESSION_PATH.format(session_id=p.SESSION_ID), (p.OK, session))
        self.answer("POST", c.APPROVE_PATH, (p.OK, {"redirect_to": p.APPROVED.format(port=port)}))
        self.open_request()
        self.matching_code()
        self.button(m.APPROVE).click()
        try:
            self.page.wait_for_url(p.SHOWN_APPROVED[port])
        except PlaywrightTimeout:
            pass
        self.assertEqual(self.page.url, p.SHOWN_APPROVED[port], f"the browser goes to the listener on port {port}")
        self.assertEqual(self.text(p.EXCHANGE_CODE).count(), 0, "no exchange code is shown")

    def bud_an_approved_callback_goes_to_its_loopback_listener_on_port_4567(self):
        """Approve in callback mode goes to http://127.0.0.1:4567/callback with the code and state."""
        self._approved_callback("4567")

    def bud_an_approved_callback_goes_to_its_loopback_listener_on_port_80(self):
        """Approve in callback mode goes to http://127.0.0.1/callback with the code and state."""
        self._approved_callback("80")

    def bud_an_approval_target_outside_the_loopback_listener_is_not_followed(self):
        """An approval answer naming another target shows an alert and the browser stays on the page."""
        self.answer(
            "GET", c.SESSION_PATH.format(session_id=p.SESSION_ID), (p.OK, self.callback_session(p.CALLBACK_PORT))
        )
        self.answer("POST", c.APPROVE_PATH, (p.OK, {"redirect_to": p.OUTSIDE}))
        self.open_request()
        page = self.page.url
        self.matching_code()
        self.button(m.APPROVE).click()
        self.assertTrue(self.shown(self.page.get_by_role("alert")), "an alert is shown")
        self.assertEqual(self.page.url, page, "the browser stays on the approval page")

    def bud_the_session_answer_puts_no_code_in_the_boxes(self):
        """A request code in the session answer appears neither in the boxes nor on the page."""
        self.answer(
            "GET", c.SESSION_PATH.format(session_id=p.SESSION_ID), (p.OK, {**p.CODE_SESSION, "request_code": p.CODE})
        )
        self.open_request()
        self.assertEqual(self.values(), p.EMPTY, "the boxes are empty")
        self.assertNotIn(member=p.CODE, container=self.page_text(), msg=f"{p.CODE!r} is not shown")

    def bud_a_typed_code_is_checked_once_at_eight_characters(self):
        """Typed lower-case letters fill the boxes in upper case and the complete code is checked once."""
        self.open_request()
        self.matching_code()
        self.assertEqual(self.values(), p.CHARACTERS, f"the boxes hold {p.CHARACTERS}")
        self.assertEqual(
            self.bodies("POST", c.CHECK_PATH),
            [{"session_id": p.SESSION_ID, "request_code": p.CODE}],
            "the code is checked once",
        )

    def bud_a_pasted_code_with_a_space_is_checked(self):
        """A pasted code with a space fills every box and is checked once."""
        self.open_request()
        self.paste(p.PASTED)
        self.assertTrue(self.shown(self.text(m.MATCH)), f"{m.MATCH!r} is shown")
        self.assertEqual(self.values(), p.CHARACTERS, f"the boxes hold {p.CHARACTERS}")
        self.assertEqual(len(self.bodies("POST", c.CHECK_PATH)), p.ONE, "the code is checked once")

    def bud_approve_is_enabled_only_while_the_checked_code_matches(self):
        """Approve is disabled while the code is incomplete, enabled once it matches, and disabled again
        after an edit."""
        self.open_request()
        self.assertTrue(self.button(m.APPROVE).is_disabled(), "Approve is disabled with empty boxes")
        self.type_code(p.SEVEN)
        self.assertTrue(self.button(m.APPROVE).is_disabled(), "Approve is disabled with seven characters")
        self.page.keyboard.type(p.EIGHTH)
        self.assertTrue(self.shown(self.text(m.MATCH)), f"{m.MATCH!r} is shown")
        self.assertTrue(self.button(m.APPROVE).is_enabled(), "Approve is enabled once the code matches")
        self.box(p.BOXES).press("Backspace")
        self.assertTrue(self.button(m.APPROVE).is_disabled(), "Approve is disabled after an edit")
        self.assertEqual(self.text(m.MATCH).count(), 0, f"{m.MATCH!r} is gone after an edit")

    def bud_a_mismatch_hides_the_server_text_and_keeps_approve_disabled(self):
        """A refused check for a pending request shows the mismatch text, not the server's text, and
        looks the session up again."""
        self.answer("POST", c.CHECK_PATH, (p.BAD_REQUEST, p.REFUSED))
        self.open_request()
        self.type_code(p.WRONG)
        self.assertTrue(self.shown(self.text(m.MISMATCH)), f"{m.MISMATCH!r} is shown")
        self.assertNotIn(member=p.SERVER_TEXT, container=self.page_text(), msg="the server's text is not shown")
        self.assertTrue(self.button(m.APPROVE).is_disabled(), "Approve stays disabled")
        session = c.SESSION_PATH.format(session_id=p.SESSION_ID)
        self.assertEqual(
            len([to for (sent, to, _) in self.calls if sent == "GET" and to == session]),
            p.TWO,
            "the session is looked up again after the refusal",
        )

    def bud_a_refused_check_for_a_gone_request_shows_the_ended_text(self):
        """A refused check whose second session lookup is refused shows the ended alert and no Approve."""
        self.answer("POST", c.CHECK_PATH, (p.BAD_REQUEST, p.REFUSED))
        self.answer(
            "GET", c.SESSION_PATH.format(session_id=p.SESSION_ID), (p.OK, p.CODE_SESSION), (p.BAD_REQUEST, p.REFUSED)
        )
        self.open_request()
        self.type_code(p.WRONG)
        alert = self.page.get_by_role("alert")
        self.assertTrue(self.shown(alert), "an alert is shown")
        self.assertIn(member=m.ENDED, container=alert.first.inner_text(), msg=f"the alert says {m.ENDED!r}")
        self.assertEqual(self.button(m.APPROVE).count(), 0, "no Approve is shown")

    def bud_a_429_on_check_asks_to_wait(self):
        """A check answered 429 asks to wait and keeps Approve disabled."""
        self.answer("POST", c.CHECK_PATH, (p.TOO_MANY, p.LIMITED))
        self.open_request()
        self.type_code(p.TYPED)
        self.assertTrue(self.shown(self.text(m.LIMITED)), f"{m.LIMITED!r} is shown")
        self.assertTrue(self.button(m.APPROVE).is_disabled(), "Approve is disabled")

    def bud_a_429_on_approve_asks_to_wait(self):
        """An approval answered 429 asks to wait and disables Approve."""
        self.answer("POST", c.APPROVE_PATH, (p.TOO_MANY, p.LIMITED))
        self.open_request()
        self.matching_code()
        self.button(m.APPROVE).click()
        self.assertTrue(self.shown(self.text(m.LIMITED)), f"{m.LIMITED!r} is shown")
        self.assertTrue(self.button(m.APPROVE).is_disabled(), "Approve is disabled")

    def bud_a_400_on_approve_for_a_pending_request_shows_the_mismatch(self):
        """An approval answered 400 while the request is still pending shows the mismatch and no alert."""
        self.answer("POST", c.APPROVE_PATH, (p.BAD_REQUEST, p.REFUSED))
        self.open_request()
        self.matching_code()
        self.button(m.APPROVE).click()
        self.assertTrue(self.shown(self.text(m.MISMATCH)), f"{m.MISMATCH!r} is shown")
        self.assertEqual(self.page.get_by_role("alert").count(), 0, "no alert is shown")

    def bud_a_check_answer_for_an_edited_code_is_ignored(self):
        """A check answer that arrives after the code was edited leaves the page without a match."""
        self.answer("POST", c.CHECK_PATH, p.HOLD)
        self.open_request()
        self.type_code(p.TYPED)
        self.page.wait_for_timeout(c.SETTLE_MS)
        self.box(p.BOXES).press("Backspace")
        for route in self.held:
            route.fulfill(status=p.OK, content_type=c.JSON, body=json.dumps(p.NOTHING))
        self.page.wait_for_timeout(c.SETTLE_MS)
        self.assertEqual(len(self.bodies("POST", c.CHECK_PATH)), p.ONE, "the code was checked once")
        self.assertEqual(self.text(m.MATCH).count(), 0, f"{m.MATCH!r} is not shown")
        self.assertTrue(self.button(m.APPROVE).is_disabled(), "Approve is disabled")

    def bud_deny_with_an_empty_code_field(self):
        """Deny with empty boxes ends the request and sends only the session."""
        self.open_request()
        self.assertEqual(self.values(), p.EMPTY, "the boxes are empty")
        self.button(m.DENY).click()
        self.assertTrue(self.shown(self.text(m.DENIED)), f"{m.DENIED!r} is shown")
        self.assertEqual(
            self.bodies("POST", c.DENY_PATH), [{"session_id": p.SESSION_ID}], "Deny sends only the session"
        )
