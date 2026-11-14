"""
* @file     ${tests/sec/BUD_audit_labels_http.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The audit log names the objects its events refer to and marks the deleted ones.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module stores events about stored and deleted objects and reads them as an administrator.
"""

from app.core.security import get_password_hash
from app.models import (
    AccessGroup,
    Artifact,
    AuditEvent,
    NotificationChannel,
    Policy,
    Product,
    Runner,
    RunnerApiKey,
    TestResult,
    TestRun,
)
from app.models.user import User, UserRole
from tests.sec.audit_labels_http import AuditLabelsHttpBase


class AuditLabelsHttpTest(AuditLabelsHttpBase):

    def setUpClass(self):
        super().setUpClass()
        self.tc_logins, self.tc_pages = [], []
        self.targets()
        self.odd_ids()

    def targets(self):
        """Events about a run, a deleted run, a product, a user, a station, a setting and a group."""
        p = self.parameters
        headers = self.admin()
        add = self.bud.bud_add_to_app
        run = add(TestRun(name=p.LABELS_RUN, test_case_list="suite", status="Completed"))
        product = add(Product(name=p.LABELS_PRODUCT))
        station = add(Runner(account=p.LABELS_STATION, password_hash="x", token="t"))
        member = add(
            User(
                **p.LABELS_MEMBER,
                hashed_password=get_password_hash(p.SEC_PASSWORD),
                role=UserRole.viewer,
                is_active=True,
            )
        )
        gone = add(TestRun(name=p.LABELS_GONE_RUN, test_case_list="suite", status="Completed")).id
        self.bud.bud_delete_in_app(TestRun, id=gone)
        group = self.bud.bud_find_in_app(AccessGroup, system_key=p.LABELS_GROUP_KEY)[0]
        events = {
            "label.run": dict(target_type="test_run", target_id=str(run.id)),
            "label.gone": dict(target_type="run", target_id=str(gone)),
            "label.product": dict(target_type="product", target_id=str(product.id)),
            "label.user": dict(target_type="user", target_id=str(member.id)),
            "label.account": dict(target_type="station", target_id=p.LABELS_STATION),
            "label.setting": dict(target_type="setting", target_id=p.LABELS_SETTING),
            "label.created": dict(
                target_type="group",
                target_id=str(group.id),
                details={"route": "/api/groups", "created_id": group.id, "runner_id": station.id},
            ),
            "label.upload": dict(
                details={
                    "route": "/api/results",
                    "created_test_run_id": run.id,
                    "runner_id": p.LABELS_MISSING_STATION,
                }
            ),
        }
        items = self.store_and_read(events, p.LABELS_PREFIX, headers)
        expected = {
            ("label.run", "target"): (p.LABELS_RUN, False),
            ("label.gone", "target"): (None, True),
            ("label.product", "target"): (p.LABELS_PRODUCT, False),
            ("label.user", "target"): (p.LABELS_MEMBER["full_name"], False),
            ("label.account", "target"): (None, False),
            ("label.setting", "target"): (None, False),
            ("label.created", "target"): (group.name, False),
            ("label.created", "created"): (group.name, False),
            ("label.created", "station"): (p.LABELS_STATION, False),
            ("label.upload", "created"): (p.LABELS_RUN, False),
            ("label.upload", "station"): (None, True),
            ("label.run", "station"): (None, False),
        }
        self.tc_named = {key: (self.named(items, *key), value) for key, value in expected.items()}
        self.tc_gone_id = items.get("label.gone", {}).get("target_id")
        self.tc_gone_expected = str(gone)
        stored = self.bud.bud_find_in_app(AuditEvent, action="label.run")
        self.tc_stored = [(event.target_type, event.target_id) for event in stored]
        self.tc_stored_expected = [("test_run", str(run.id))]

    def odd_ids(self):
        """Events about a policy, a key, an artifact, a result, a channel and odd run ids."""
        p = self.parameters
        headers = self.admin()
        add = self.bud.bud_add_to_app
        run = add(TestRun(name=p.LABELS_RUN, test_case_list="suite", status="Completed"))
        key = add(RunnerApiKey(**p.LABELS_KEY))
        artifact = add(Artifact(**p.LABELS_ARTIFACT, test_run_id=run.id))
        result = add(TestResult(**p.LABELS_RESULT))
        channel = add(NotificationChannel(**p.LABELS_CHANNEL))
        policy = self.bud.bud_find_in_app(Policy, system_key=p.LABELS_POLICY_KEY)[0]
        events = {
            "odd.policy": dict(target_type="policy", target_id=str(policy.id)),
            "odd.key": dict(target_type="key", target_id=str(key.id)),
            "odd.artifact": dict(target_type="artifact", target_id=str(artifact.id)),
            "odd.result": dict(target_type="result", target_id=str(result.id)),
            "odd.channel": dict(
                target_type="notification_channel",
                target_id=str(channel.id),
                details={"route": "/api/settings/notifications/channels", "created_id": channel.id},
            ),
            **{
                action: dict(target_type="run", target_id=odd)
                for action, odd in p.LABELS_ODD_IDS.items()
            },
        }
        items = self.store_and_read(events, p.LABELS_ODD_PREFIX, headers)
        self.tc_odd = {
            action: (item.get("target_label"), item.get("target_deleted"))
            for action, item in items.items()
        }
        self.tc_odd_expected = {
            "odd.policy": (policy.name, False),
            "odd.key": (p.LABELS_KEY["label"], False),
            "odd.artifact": (p.LABELS_ARTIFACT["original_filename"], False),
            "odd.result": (
                f"{p.LABELS_RESULT['test_class']}.{p.LABELS_RESULT['test_method']}",
                False,
            ),
            "odd.channel": (p.LABELS_CHANNEL["name"], False),
            **{action: (None, False) for action in p.LABELS_ODD_IDS},
        }
        self.tc_channel_created = items.get("odd.channel", {}).get("created_label")

    def admin(self):
        """Start a fresh app, store an administrator, sign in and return the header."""
        p = self.parameters
        self.bud.bud_start_app(signed_in=False)
        self.bud.bud_add_to_app(
            User(
                **p.LABELS_AUDITOR,
                hashed_password=get_password_hash(p.SEC_PASSWORD),
                role=UserRole.admin,
                is_active=True,
            )
        )
        response = self.bud.bud_request(
            p.POST,
            p.LOGIN_PATH,
            json={"email": p.LABELS_AUDITOR["email"], "password": p.SEC_PASSWORD},
        )
        self.tc_logins.append(response.status_code)
        return {"Authorization": f"Bearer {response.json().get('access_token')}"}

    def store_and_read(self, events, prefix, headers):
        """Store the events and read them back from the audit log by their action prefix."""
        for action, fields in events.items():
            self.bud.bud_add_to_app(
                AuditEvent(action=action, actor_type="user", outcome="success", **fields)
            )
        response = self.bud.bud_request(
            self.parameters.GET,
            self.parameters.AUDIT_PATH,
            params={"action": prefix, "limit": self.parameters.LABELS_LIMIT},
            headers=headers,
        )
        self.tc_pages.append(response.status_code)
        return {item["action"]: item for item in response.json().get("items", [])}

    @staticmethod
    def named(items, action, field):
        """The name and the deleted flag of one field of one event."""
        item = items.get(action, {})
        name_key = "station_name" if field == "station" else f"{field}_label"
        return item.get(name_key), item.get(f"{field}_deleted")

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    AuditLabelsHttpTest().run()
