"""
* @file     ${tests/pg/BUD_integrity_conflict_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A unique constraint violated on PostgreSQL is answered as a 409 naming the request, not the constraint.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module serves one extra route that flushes two stations with one account on the live app.
"""

from fastapi import Depends

from app.db.database import get_db
from app.models import Runner
from tests.pg.integrity_conflict_pg import IntegrityConflictPgBase

PATH = "/api/__flush_conflict__"


class IntegrityConflictPgTest(IntegrityConflictPgBase):

    def setUpClass(self):
        super().setUpClass()
        self.bud.bud_start_live_app()
        unique = self.bud.bud_unique

        async def flush_conflict(db=Depends(get_db)):
            account = unique("bench")
            db.add(Runner(account=account, password_hash="x", token="t", socket_port=53035))
            db.add(Runner(account=account, password_hash="y", token="u", socket_port=53035))
            await db.flush()
            return {"ok": True}

        self.bud.bud_add_route(PATH, flush_conflict)
        first = self.bud.bud_request(self.parameters.GET, PATH)
        second = self.bud.bud_request(self.parameters.GET, PATH)
        self.bud.bud_remove_routes()
        try:
            body = first.json()
        except ValueError:
            body = {}
        self.tc_checks = {
            "conflict": {
                "the violation is a conflict": (first.status_code, self.parameters.STATUS_CONFLICT),
                "the answer says it already exists": ("already exists" in str(body.get("detail")), True),
                "the answer names a request": (bool(body.get("request_id")), True),
                "the detail quotes the request": (str(body.get("request_id")) in str(body.get("detail")), True),
            },
            "leak": {
                f"the answer leaves out {text}": (text in second.text, False)
                for text in ("runners_account_key", "INSERT INTO", "UniqueViolationError")
            },
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    IntegrityConflictPgTest().run()
