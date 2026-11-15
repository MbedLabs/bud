"""
* @file     ${tests/sec/BUD_group_overlap_sec.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Holding several groups never widens what the groups allow; management and giving stay guarded.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module signs every person in with a real token; groups are held through stored memberships.
"""

from app.core.security import get_password_hash
from app.models.access import AccessGroup, AccessGroupMember, Policy
from app.models.user import User, UserRole
from tests.sec.group_overlap_sec import GroupOverlapSecBase


class GroupOverlapSecTest(GroupOverlapSecBase):

    def setUpClass(self):
        super().setUpClass()
        self.tc_logins = []
        self.tc_closed = self.closed()
        self.tc_admin_group = self.admin_group()
        self.tc_viewer = self.viewer()
        self.tc_spread = self.spread()

    def closed(self):
        """A viewer holding five groups without access management."""
        p = self.fresh()
        viewer = self.user("member@example.com", UserRole.viewer)
        target = self.user("target@example.com", UserRole.viewer)
        groups = [
            self.group("Test Operators"),
            self.group("Results Viewers"),
            self.group(*p.SEC_CATALOGUE),
            self.group(*p.SEC_CONFIGURATION),
            self.group(*p.SEC_AUDITORS),
        ]
        self.hold(viewer, *groups)
        headers = self.login("member@example.com")
        return {
            "groups": self.bud.bud_request(p.GET, p.GROUPS_PATH, headers=headers).status_code,
            "users": self.bud.bud_request(p.GET, p.ACCESS_USERS_PATH, headers=headers).status_code,
            "give": self.give(groups[1], target, headers).status_code,
            "rows": self.rows(target),
        }

    def admin_group(self):
        """A developer holding access management and every other policy across groups."""
        p = self.fresh()
        giver = self.user("giver@example.com", UserRole.developer)
        holder = self.user("holder@example.com", UserRole.developer)
        recipient = self.user("recipient@example.com", UserRole.developer)
        administrators = self.group(p.SEC_ADMIN_GROUP)
        self.hold(
            giver,
            self.group("Access Managers"),
            self.group(*p.SEC_CATALOGUE),
            self.group(*p.SEC_CONFIGURATION),
            self.group(*p.SEC_AUDITORS),
            self.group("Test Operators"),
        )
        self.hold(holder, administrators)
        headers = self.login("giver@example.com")
        given = self.give(administrators, recipient, headers)
        removed = self.bud.bud_request(
            p.DELETE, p.GROUP_MEMBER_PATH.format(administrators, holder), headers=headers
        )
        return {
            "given": (given.status_code, given.json().get("detail")),
            "removed": (removed.status_code, removed.json().get("detail")),
            "recipient rows": self.rows(recipient),
            "holder rows": self.rows(holder),
        }

    def viewer(self):
        """An administrator gives management groups to a viewer holding three groups."""
        p = self.fresh()
        self.user("boss@example.com", UserRole.admin)
        viewer = self.user("member@example.com", UserRole.viewer)
        held = [
            self.group("Test Operators"),
            self.group(*p.SEC_CATALOGUE),
            self.group(*p.SEC_AUDITORS),
        ]
        self.hold(viewer, *held)
        headers = self.login("boss@example.com")
        found = {
            name: self.give(self.group(name), viewer, headers).status_code
            for name in p.SEC_STATION_GROUPS
        }
        found.update({"rows": self.rows(viewer), "held": len(held)})
        return found

    def spread(self):
        """A giver with products in one group gives groups covering more."""
        p = self.fresh()
        giver = self.user("giver@example.com", UserRole.developer)
        recipient = self.user("recipient@example.com", UserRole.developer)
        self.hold(giver, self.group("Access Managers"), self.group(*p.SEC_CATALOGUE))
        covered, wider = self.group(*p.SEC_COVERED), self.group(*p.SEC_WIDER)
        headers = self.login("giver@example.com")
        return {
            "wider": self.give(wider, recipient, headers).status_code,
            "covered": self.give(covered, recipient, headers).status_code,
            "rows": self.rows(recipient),
        }

    def fresh(self):
        """Start the app with no one signed in and return the parameters."""
        self.bud.bud_start_app(signed_in=False)
        return self.parameters

    def user(self, email, role):
        """Store an active user with the shared password and return its id."""
        return self.bud.bud_add_to_app(
            User(
                email=email,
                full_name=email.split("@")[0],
                hashed_password=get_password_hash(self.parameters.SEC_PASSWORD),
                role=role,
                is_active=True,
            )
        ).id

    def group(self, name, *policy_keys):
        """The id of the group of that name, made from the shipped policies when it is custom."""
        existing = self.bud.bud_find_in_app(AccessGroup, name=name)
        if existing:
            return existing[0].id
        policies = [self.bud.bud_find_in_app(Policy, system_key=key)[0] for key in policy_keys]
        return self.bud.bud_add_to_app(AccessGroup(name=name, policies=policies)).id

    def hold(self, user_id, *group_ids):
        """Store the user's membership of each group."""
        for group_id in group_ids:
            self.bud.bud_add_to_app(AccessGroupMember(group_id=group_id, user_id=user_id))

    def rows(self, user_id):
        """How many memberships the user has."""
        return len(self.bud.bud_find_in_app(AccessGroupMember, user_id=user_id))

    def login(self, email):
        """Sign in with the shared password and return the bearer header."""
        response = self.bud.bud_request(
            self.parameters.POST,
            self.parameters.LOGIN_PATH,
            json={"email": email, "password": self.parameters.SEC_PASSWORD},
        )
        self.tc_logins.append(response.status_code)
        return {"Authorization": f"Bearer {response.json().get('access_token')}"}

    def give(self, group_id, user_id, headers):
        """Give a group to a user."""
        return self.bud.bud_request(
            self.parameters.POST,
            self.parameters.GROUP_MEMBERS_PATH.format(group_id),
            json={"user_id": user_id},
            headers=headers,
        )

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    GroupOverlapSecTest().run()
