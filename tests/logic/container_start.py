"""
* @file     ${tests/logic/container_start.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests how the image starts its processes.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of start.sh, supervisord.conf and the Dockerfile.
"""

from tests.bud_test_base import BudAppTestCase


class ContainerStartBase(BudAppTestCase):

    def bud_start_script_ends_with_supervisord_as_appuser(self):
        self.assertEqual(
            self.start_lines[-1],
            self.parameters.START_SUPERVISORD,
            msg=self.parameters.MSG_START_LAST,
            abort_on_fail=False,
        )

    def bud_start_script_starts_supervisord_once(self):
        self.assertEqual(
            self.start_lines.count(self.parameters.START_SUPERVISORD),
            self.parameters.START_SUPERVISORD_TIMES,
            msg=self.parameters.MSG_START_ONCE,
            abort_on_fail=False,
        )

    def bud_start_script_names_appuser(self):
        self.assertIn(
            self.parameters.START_APP_USER,
            self.start_lines,
            msg=self.parameters.MSG_START_APP_USER,
            abort_on_fail=False,
        )

    def bud_start_script_goes_through_the_output_descriptors(self):
        self.assertIn(
            self.parameters.START_FD_LOOP,
            self.start,
            msg=self.parameters.MSG_START_FD_LOOP,
            abort_on_fail=False,
        )

    def bud_start_script_checks_each_descriptor(self):
        self.assertIn(
            self.parameters.START_FD_WRITABLE,
            self.start,
            msg=self.parameters.MSG_START_FD_WRITABLE,
            abort_on_fail=False,
        )

    def bud_start_script_gives_a_descriptor_to_appuser(self):
        self.assertIn(
            self.parameters.START_FD_CHOWN,
            self.start,
            msg=self.parameters.MSG_START_FD_CHOWN,
            abort_on_fail=False,
        )

    def bud_descriptors_are_given_before_supervisord_starts(self):
        loop = self.start.index(self.parameters.START_FD_LOOP)
        start = self.start.index(self.parameters.START_SUPERVISORD_PREFIX)
        self.print_variables({"descriptor loop at": loop, "supervisord at": start})
        self.assertLess(loop, start, msg=self.parameters.MSG_START_FD_FIRST, abort_on_fail=False)

    def bud_cloudron_data_is_given_to_appuser(self):
        self.print_variables({"Cloudron block": self.cloudron_block})
        self.assertIn(
            self.parameters.START_DATA_CHOWN,
            self.cloudron_block,
            msg=self.parameters.MSG_START_DATA_CHOWN,
            abort_on_fail=False,
        )

    def bud_cloudron_data_is_given_before_the_migration(self):
        chown = self.cloudron_block.index(self.parameters.START_DATA_CHOWN)
        migration = self.cloudron_block.index(self.parameters.START_MIGRATION)
        self.print_variables({"chown at": chown, "migration at": migration})
        self.assertLess(
            chown, migration, msg=self.parameters.MSG_START_DATA_FIRST, abort_on_fail=False
        )

    def bud_supervisord_has_no_root_user(self):
        self.assertNotIn(
            self.parameters.SUPERVISORD_ROOT,
            self.supervisord_lines,
            msg=self.parameters.MSG_SUPERVISORD_ROOT,
            abort_on_fail=False,
        )

    def bud_supervisord_pid_file_is_in_the_appuser_folder(self):
        self.assertIn(
            self.parameters.SUPERVISORD_PIDFILE,
            self.supervisord_lines,
            msg=self.parameters.MSG_SUPERVISORD_PIDFILE,
            abort_on_fail=False,
        )

    def bud_image_starts_as_root(self):
        self.assertRegex(
            self.dockerfile,
            self.parameters.DOCKERFILE_ROOT_USER,
            msg=self.parameters.MSG_DOCKERFILE_ROOT,
            abort_on_fail=False,
        )

    def bud_dockerfile_writes_no_nginx_user(self):
        self.assertNotIn(
            self.parameters.DOCKERFILE_NGINX_USER,
            self.dockerfile,
            msg=self.parameters.MSG_DOCKERFILE_NGINX_USER,
            abort_on_fail=False,
        )

    def bud_dockerfile_drops_the_nginx_user(self):
        self.assertIn(
            self.parameters.DOCKERFILE_NGINX_USER_DROP,
            self.dockerfile,
            msg=self.parameters.MSG_DOCKERFILE_NGINX_DROP,
            abort_on_fail=False,
        )
