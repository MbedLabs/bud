"""
* @file     ${tests/logic/alembic_baseline.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the shape of the migration chain.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the explicit-DDL baseline and its successors.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class AlembicBaselineBase(BudAppTestCase):

    def bud_baseline_is_the_only_root(self):
        self.assertEqual(
            self.tc_roots,
            [self.parameters.ALEMBIC_BASELINE],
            msg=self.parameters.MSG_ALEMBIC_ONE_ROOT,
            abort_on_fail=False,
        )

    def bud_every_later_revision_names_a_parent(self):
        self.print_variables({"later revisions": list(self.tc_later)})
        without_parent = [
            name
            for name, source in self.tc_later.items()
            if self.parameters.ALEMBIC_PARENT not in source
        ]
        self.assertEqual(
            without_parent, [], msg=self.parameters.MSG_ALEMBIC_PARENT, abort_on_fail=False
        )
        roots = [
            name
            for name, source in self.tc_later.items()
            if self.parameters.ALEMBIC_NO_PARENT in source
        ]
        self.assertEqual(roots, [], msg=self.parameters.MSG_ALEMBIC_NOT_ROOT, abort_on_fail=False)

    def bud_no_later_revision_rebuilds_the_schema(self):
        rebuilding = [
            name
            for name, source in self.tc_later.items()
            if self.parameters.ALEMBIC_CREATE_ALL in source
        ]
        self.assertEqual(
            rebuilding, [], msg=self.parameters.MSG_ALEMBIC_LATER_CREATE_ALL, abort_on_fail=False
        )

    def bud_baseline_keeps_the_deployed_head_id(self):
        self.assertIn(
            self.parameters.ALEMBIC_REVISION_ID.format(self.parameters.ALEMBIC_HEAD),
            self.tc_baseline,
            msg=self.parameters.MSG_ALEMBIC_HEAD_ID,
            abort_on_fail=False,
        )
        self.assertIn(
            self.parameters.ALEMBIC_TYPED_ROOT,
            self.tc_baseline,
            msg=self.parameters.MSG_ALEMBIC_BASELINE_ROOT,
            abort_on_fail=False,
        )

    def bud_baseline_uses_explicit_ddl(self):
        self.assertEqual(
            self.tc_create_all_calls,
            [],
            msg=self.parameters.MSG_ALEMBIC_NO_CREATE_ALL,
            abort_on_fail=False,
        )
        self.assertIn(
            self.parameters.ALEMBIC_CREATE_TABLE,
            self.tc_baseline,
            msg=self.parameters.MSG_ALEMBIC_EXPLICIT_DDL,
            abort_on_fail=False,
        )

    @parameterized(params.ALEMBIC_CORE_TABLES)
    def bud_baseline_creates_the_core_table(self, table):
        self.assertIn(
            self.parameters.ALEMBIC_TABLE_NAME.format(table),
            self.tc_baseline,
            msg=self.parameters.MSG_ALEMBIC_CORE_TABLE,
            abort_on_fail=False,
        )

    def bud_baseline_drops_enum_types_on_downgrade(self):
        self.assertIn(
            self.parameters.ALEMBIC_DROP_TYPE,
            self.tc_baseline,
            msg=self.parameters.MSG_ALEMBIC_DROP_TYPE,
            abort_on_fail=False,
        )
