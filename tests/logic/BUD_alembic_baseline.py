"""
* @file     ${tests/logic/BUD_alembic_baseline.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The migration chain stays a single explicit-DDL baseline with named successors.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests the repository's alembic/versions folder; the baseline keeps the deployed head id.
"""

import ast

from tests.logic.alembic_baseline import AlembicBaselineBase


def create_all_calls(source):
    """The names of the create_all calls in a Python source."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Attribute) and function.attr == "create_all":
            found.append(function.attr)
        elif isinstance(function, ast.Name) and function.id == "create_all":
            found.append(function.id)
    return found


class AlembicBaselineTest(AlembicBaselineBase):

    def setUpClass(self):
        super().setUpClass()
        folder = self.parameters.ALEMBIC_VERSIONS
        names = [
            name
            for name in self.bud.bud_repository_files(folder, self.parameters.ALEMBIC_PATTERN)
            if name != self.parameters.ALEMBIC_PACKAGE_FILE
        ]
        sources = {
            name: self.bud.bud_read_repository_file(f"{folder}/{name}") for name in names
        }
        self.tc_roots = [
            name
            for name, source in sources.items()
            if any(marker in source for marker in self.parameters.ALEMBIC_ROOT_MARKERS)
        ]
        self.tc_baseline = sources.get(self.parameters.ALEMBIC_BASELINE, "")
        self.tc_later = {
            name: source
            for name, source in sources.items()
            if name != self.parameters.ALEMBIC_BASELINE
        }
        self.tc_create_all_calls = create_all_calls(self.tc_baseline)

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    AlembicBaselineTest().run()
