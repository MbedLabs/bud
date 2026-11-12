"""
* @file     ${tests/sec/BUD_access_requests_http.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A user without Publish to Bloom asks the administrators for it, once per run per day.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests each scenario on a fresh app database with signed-in people and the request emails captured.
"""

from unittest import mock

from app.api import access_requests
from app.core.security import get_password_hash
from app.models import AccessGroup, AccessGroupMember, AccessRequest, AuditEvent, Product, TestRun
from app.models.user import User, UserRole
from tests.sec.access_requests_http import AccessRequestsHttpBase


def body_of(response):
    """The JSON answer, or an empty one."""
    try:
        return response.json() or {}
    except ValueError:
        return {}


def type_name(value):
    """The type name of a value."""
    return type(value).__name__


class AccessRequestsHttpTest(AccessRequestsHttpBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.sent = []
        self.mail = mock.patch.object(
            access_requests, "send_access_request_email", lambda **mail: self.sent.append(mail)
        )
        self.mail.start()
        self.tc_checks = {}
        self.daily()
        self.decision()
        self.anonymous()
        self.types()
        self.pictures()
        for holder, (role, group) in p.ACCESS_HOLDERS.items():
            self.holder(holder, role, group)
        self.earlier_pending()
        self.own_request()
        self.earlier_types()
        self.mail.stop()

    def fresh(self):
        """A fresh app with nobody signed in and no captured mail."""
        self.bud.bud_start_app(signed_in=False)
        self.sent.clear()
        self.logins = []

    def person(self, email, role="viewer", picture=None):
        """Store an active person with the test password."""
        return self.bud.bud_add_to_app(
            User(
                email=email,
                full_name=email.split("@")[0],
                hashed_password=get_password_hash(self.parameters.ACCESS_PASSWORD),
                role=UserRole(role),
                is_active=True,
                profile_picture=picture,
            )
        )

    def stored_run(self, name=None):
        """Store a completed run and return its id."""
        return self.bud.bud_add_to_app(
            TestRun(
                name=name or self.parameters.ACCESS_RUN_NAME,
                test_case_list="suite",
                status="Completed",
            )
        ).id

    def give(self, user_id, system_key):
        """Give a person the shipped group with this system key."""
        group = self.bud.bud_find_in_app(AccessGroup, system_key=system_key)[0]
        self.bud.bud_add_to_app(AccessGroupMember(group_id=group.id, user_id=user_id))

    def headers(self, email):
        """The headers of a signed-in person, the sign-in status kept."""
        response = self.bud.bud_log_in(email, self.parameters.ACCESS_PASSWORD)
        self.logins.append(response.status_code)
        return {"Authorization": f"Bearer {body_of(response).get('access_token')}"}

    def signed_in(self):
        """The check that every sign-in of the scenario succeeded."""
        return {"every sign-in succeeds": (set(self.logins), {self.parameters.STATUS_OK})}

    def ask(self, request, headers):
        """Post one access request."""
        return self.bud.bud_request(
            self.parameters.POST,
            self.parameters.ACCESS_REQUESTS_PATH,
            json=request,
            headers=headers,
        )

    def mine(self, request, headers):
        """Read one's own request for a resource."""
        return self.bud.bud_request(
            self.parameters.GET, self.parameters.ACCESS_MINE_PATH, params=request, headers=headers
        )

    def listed(self, headers=None):
        """The reviewers' list of requests."""
        return self.bud.bud_request(
            self.parameters.GET, self.parameters.ACCESS_REQUESTS_PATH, headers=headers or {}
        )

    def decide(self, request_id, decision, headers):
        """Decide one request."""
        p = self.parameters
        return self.bud.bud_request(
            p.POST,
            p.ACCESS_DECISION_PATH.format(request_id),
            json={"decision": decision},
            headers=headers,
        )

    def request_for(self, run_id):
        """A Publish to Bloom request for a stored run."""
        return {"resource_type": self.parameters.ACCESS_TYPE, "resource_ref": str(run_id)}

    def daily(self):
        """A member asks twice on one day."""
        p = self.parameters
        self.fresh()
        self.person(p.ACCESS_BOSS, "admin")
        self.person(p.ACCESS_MEMBER)
        headers = self.headers(p.ACCESS_MEMBER)
        request = self.request_for(self.stored_run())
        first = self.ask(request, headers)
        again = self.ask(request, headers)
        mine = self.mine(request, headers)
        boss_mail = [mail for mail in self.sent if mail.get("to_email") == p.ACCESS_BOSS] or [{}]
        events = self.bud.bud_find_in_app(AuditEvent, action=p.ACCESS_REQUESTED)
        self.tc_checks["daily"] = {
            **self.signed_in(),
            "the first request is created": (first.status_code, p.STATUS_CREATED),
            "the first request is mailed": (body_of(first).get("mail_sent"), True),
            "the same request again is answered": (again.status_code, p.STATUS_OK),
            "the answer says it was already requested": (
                body_of(again).get("already_requested"),
                True,
            ),
            "the member reads their request": (body_of(mine).get("id"), body_of(first).get("id")),
            "the administrator gets one mail": (
                len([mail for mail in self.sent if mail.get("to_email") == p.ACCESS_BOSS]),
                1,
            ),
            "the mail links the review page": (
                str(boss_mail[0].get("review_link")).endswith(p.ACCESS_REVIEW_SUFFIX),
                True,
            ),
            "the mail carries the request reference": (
                boss_mail[0].get("request_id"),
                first.headers.get("x-request-id"),
            ),
            "the mail names the resource": (
                boss_mail[0].get("resource"),
                p.ACCESS_RESOURCE.format(request["resource_ref"]),
            ),
            "the request is audited once": (
                [(event.target_type, event.target_id) for event in events],
                [(p.ACCESS_TYPE, request["resource_ref"])],
            ),
        }

    def decision(self):
        """A member's request refused by an administrator, then decided again."""
        p = self.parameters
        self.fresh()
        self.person(p.ACCESS_BOSS, "admin")
        member = self.person(p.ACCESS_MEMBER)
        member_headers = self.headers(p.ACCESS_MEMBER)
        admin_headers = self.headers(p.ACCESS_BOSS)
        created = body_of(self.ask(self.request_for(self.stored_run()), member_headers))
        listed = body_of(self.listed(admin_headers))
        listed = listed if isinstance(listed, list) else []
        by_member = self.decide(created.get("id"), "refused", member_headers)
        refused = self.decide(created.get("id"), "refused", admin_headers)
        twice = self.decide(created.get("id"), "granted", admin_headers)
        events = self.bud.bud_find_in_app(AuditEvent, action=p.ACCESS_REFUSED) or [
            AuditEvent(details={})
        ]
        self.tc_checks["decision"] = {
            **self.signed_in(),
            "the list names the requester": (
                [row.get("requester_email") for row in listed],
                [p.ACCESS_MEMBER],
            ),
            "the list names the run": (
                [(row.get("resource_label"), row.get("resource_deleted")) for row in listed],
                [(p.ACCESS_RUN_NAME, False)],
            ),
            "the member cannot decide": (by_member.status_code, p.STATUS_FORBIDDEN),
            "the administrator refuses": (refused.status_code, p.STATUS_OK),
            "the request is refused": (body_of(refused).get("status"), "refused"),
            "a second decision is a conflict": (twice.status_code, p.STATUS_CONFLICT),
            "the refusal audit names the requester": (
                (events[0].details or {}).get("requester_user_id"),
                member.id,
            ),
        }

    def anonymous(self):
        """A request without a signed-in person."""
        p = self.parameters
        self.fresh()
        response = self.ask({"resource_type": p.ACCESS_TYPE, "resource_ref": "1"}, {})
        self.tc_checks["anonymous"] = {
            "the request needs a signed-in person": (response.status_code, p.STATUS_UNAUTHORIZED)
        }

    def types(self):
        """Requests for resource types outside Publish to Bloom."""
        p = self.parameters
        self.fresh()
        self.person(p.ACCESS_MEMBER)
        headers = self.headers(p.ACCESS_MEMBER)
        checks = self.signed_in()
        for kind in p.ACCESS_OTHER_TYPES:
            request = {"resource_type": kind, "resource_ref": "1"}
            checks[f"a {kind} request is refused"] = (
                self.ask(request, headers).status_code,
                p.STATUS_UNPROCESSABLE,
            )
            checks[f"a {kind} read is refused"] = (
                self.mine(request, headers).status_code,
                p.STATUS_UNPROCESSABLE,
            )
        checks["nobody is mailed"] = (list(self.sent), [])
        self.tc_checks["types"] = checks

    def pictures(self):
        """Two requesters with pictures, as reviewers and requesters see them."""
        p = self.parameters
        self.fresh()
        people = {
            email: self.person(email, role, picture) for email, role, picture in p.ACCESS_PICTURES
        }
        admin_email, first_email, second_email = (email for email, _, _ in p.ACCESS_PICTURES)
        admin_headers = self.headers(admin_email)
        request = self.request_for(self.stored_run())
        checks = {}
        for email in (first_email, second_email):
            headers = self.headers(email)
            created = self.ask(request, headers)
            mine = self.mine(request, headers)
            checks[f"{email} creates a request"] = (created.status_code, p.STATUS_CREATED)
            checks[f"{email} gets no picture back"] = (
                type_name(body_of(created).get("requester_profile_picture_url")),
                p.NONE_TYPE,
            )
            checks[f"{email} reads the request"] = (mine.status_code, p.STATUS_OK)
            checks[f"{email} reads no picture"] = (
                type_name(body_of(mine).get("requester_profile_picture_url")),
                p.NONE_TYPE,
            )
            checks[f"{email} cannot list requests"] = (
                self.listed(headers).status_code,
                p.STATUS_FORBIDDEN,
            )
        checks["a signed-out visitor cannot list requests"] = (
            self.listed().status_code,
            p.STATUS_UNAUTHORIZED,
        )
        admin_picture = people[admin_email].profile_picture_url
        second_picture = people[second_email].profile_picture_url
        first = people[first_email]
        for picture in p.ACCESS_FIRST_PICTURES:
            first.profile_picture = picture
            first = self.bud.bud_add_to_app(first)
            response = self.listed(admin_headers)
            rows = body_of(response) if isinstance(body_of(response), list) else []
            requesters = {row.get("requester_email"): row for row in rows}
            label = picture.decode() if picture else "no picture"
            checks[f"with {label}, the administrator lists requests"] = (
                response.status_code,
                p.STATUS_OK,
            )
            shown = requesters.get(first_email, {}).get("requester_profile_picture_url")
            expected = User(profile_picture=picture).profile_picture_url
            checks[f"with {label}, the first requester's picture"] = (
                (shown, expected) if picture else (type_name(shown), p.NONE_TYPE)
            )
            checks[f"with {label}, the second requester's picture"] = (
                requesters.get(second_email, {}).get("requester_profile_picture_url"),
                second_picture,
            )
            checks[f"with {label}, the second requester's picture is not the administrator's"] = (
                requesters.get(second_email, {}).get("requester_profile_picture_url")
                != admin_picture,
                True,
            )
        self.tc_checks["pictures"] = {**self.signed_in(), **checks}

    def holder(self, name, role, group):
        """A request by a holder of Publish to Bloom."""
        p = self.parameters
        self.fresh()
        self.person(p.ACCESS_BOSS, "admin")
        holder = self.person("holder@example.com", role)
        if group:
            self.give(holder.id, group)
        headers = self.headers("holder@example.com")
        created = self.ask(self.request_for(self.stored_run()), headers)
        self.tc_checks[name] = {
            **self.signed_in(),
            "the request is a conflict": (created.status_code, p.STATUS_CONFLICT),
            "the refusal says Publish to Bloom is held": (
                body_of(created).get("detail"),
                access_requests.ALREADY_HELD,
            ),
            "nobody is mailed": (list(self.sent), []),
            "no request is stored": (len(self.bud.bud_find_in_app(AccessRequest)), 0),
            "no request is audited": (
                len(self.bud.bud_find_in_app(AuditEvent, action=p.ACCESS_REQUESTED)),
                0,
            ),
        }

    def earlier_pending(self):
        """A member who asked, was then given Test Operators, and asks again."""
        p = self.parameters
        self.fresh()
        member = self.person(p.ACCESS_MEMBER)
        headers = self.headers(p.ACCESS_MEMBER)
        request = self.request_for(self.stored_run())
        first = self.ask(request, headers)
        self.give(member.id, p.ACCESS_OPERATORS)
        again = self.ask(request, headers)
        self.tc_checks["earlier pending"] = {
            **self.signed_in(),
            "the first request is created": (first.status_code, p.STATUS_CREATED),
            "the request as a holder is a conflict": (again.status_code, p.STATUS_CONFLICT),
        }

    def own_request(self):
        """A request by an access manager."""
        p = self.parameters
        self.fresh()
        self.person(p.ACCESS_BOSS, "admin")
        manager = self.person(p.ACCESS_MANAGER)
        self.give(manager.id, p.ACCESS_MANAGERS)
        created = self.ask(self.request_for(self.stored_run()), self.headers(p.ACCESS_MANAGER))
        recipients = [mail.get("to_email") for mail in self.sent]
        self.tc_checks["own request"] = {
            **self.signed_in(),
            "the request is created": (created.status_code, p.STATUS_CREATED),
            "the administrator is mailed": (p.ACCESS_BOSS in recipients, True),
            "the requester is not mailed": (p.ACCESS_MANAGER in recipients, False),
        }

    def earlier_types(self):
        """Stored requests for a run, a product and a removed run."""
        p = self.parameters
        self.fresh()
        self.person(p.ACCESS_BOSS, "admin")
        member = self.person(p.ACCESS_MEMBER)
        run_id = self.stored_run()
        product = self.bud.bud_add_to_app(Product(name=p.ACCESS_PRODUCT))
        gone_id = self.stored_run(p.ACCESS_GONE_RUN)
        self.bud.bud_delete_in_app(TestRun, id=gone_id)
        rows = [
            self.bud.bud_add_to_app(
                AccessRequest(user_id=member.id, resource_type=kind, resource_ref=str(ref))
            )
            for kind, ref in (
                ("test-run", run_id),
                ("product", product.id),
                (p.ACCESS_TYPE, gone_id),
            )
        ]
        headers = self.headers(p.ACCESS_BOSS)
        listed = self.listed(headers)
        refused = self.decide(rows[0].id, "refused", headers)
        named = {
            row.get("resource_type"): (
                row.get("resource_ref"),
                row.get("resource_label"),
                row.get("resource_deleted"),
            )
            for row in (body_of(listed) if isinstance(body_of(listed), list) else [])
        }
        self.tc_checks["earlier types"] = {
            **self.signed_in(),
            "the administrator lists requests": (listed.status_code, p.STATUS_OK),
            "each request is named": (
                named,
                {
                    "test-run": (str(run_id), p.ACCESS_RUN_NAME, False),
                    "product": (str(product.id), p.ACCESS_PRODUCT, False),
                    p.ACCESS_TYPE: (str(gone_id), None, True),
                },
            ),
            "the run request is refused": (refused.status_code, p.STATUS_OK),
            "the refusal keeps the run's name": (
                (body_of(refused).get("status"), body_of(refused).get("resource_label")),
                ("refused", p.ACCESS_RUN_NAME),
            ),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    AccessRequestsHttpTest().run()
