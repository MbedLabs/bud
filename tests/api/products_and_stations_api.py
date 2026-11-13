"""
* @file     ${tests/api/products_and_stations_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the product and Test Station endpoints.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of products and Test Stations.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class ProductsAndStationsApiBase(BudAppTestCase):

    def bud_product_is_added(self):
        p = self.parameters
        self.print_variables({"status": self.tc_created.status_code, "body": self.tc_created.text})
        self.assertEqual(self.tc_created.status_code, p.STATUS_CREATED, msg=p.MSG_PRODUCT_CREATED)
        self.assertEqual(
            self.tc_created.json().get("name"), p.PRODUCT["name"], msg=p.MSG_PRODUCT_NAME
        )

    def bud_duplicate_product_is_refused(self):
        p = self.parameters
        self.print_variables({"first": self.tc_first, "second": self.tc_second.text})
        self.assertEqual(self.tc_first, p.STATUS_CREATED, msg=p.MSG_PRODUCT_FIRST)
        self.assertEqual(
            self.tc_second.status_code, p.STATUS_BAD_REQUEST, msg=p.MSG_PRODUCT_DUPLICATE
        )
        self.assertIn(
            p.PRODUCT_DUPLICATE_TEXT,
            str(self.tc_second.json().get("detail")).lower(),
            msg=p.MSG_PRODUCT_DUPLICATE_TEXT,
        )

    def bud_products_are_listed_by_name(self):
        self.assertEqual(
            self.tc_listed, sorted(self.tc_listed), msg=self.parameters.MSG_PRODUCT_SORTED
        )

    def bud_one_product_is_read(self):
        p = self.parameters
        self.print_variables({"status": self.tc_fetched.status_code, "body": self.tc_fetched.text})
        self.assertEqual(self.tc_fetched.status_code, p.STATUS_OK, msg=p.MSG_PRODUCT_FETCHED)
        self.assertEqual(
            self.tc_fetched.json().get("name"), p.PRODUCT_FETCHED, msg=p.MSG_PRODUCT_NAME
        )

    def bud_unknown_product_is_not_found(self):
        self.assertEqual(
            self.tc_missing_product,
            self.parameters.STATUS_NOT_FOUND,
            msg=self.parameters.MSG_PRODUCT_MISSING,
        )

    def bud_product_is_deleted(self):
        p = self.parameters
        self.assertEqual(self.tc_product_deleted, p.STATUS_NO_CONTENT, msg=p.MSG_PRODUCT_DELETED)
        self.assertEqual(len(self.tc_product_left), 0, msg=p.MSG_PRODUCT_GONE)

    def bud_deleting_an_unknown_product_is_not_found(self):
        self.assertEqual(
            self.tc_product_delete_missing,
            self.parameters.STATUS_NOT_FOUND,
            msg=self.parameters.MSG_PRODUCT_DELETE_MISSING,
        )

    def bud_product_is_edited(self):
        p = self.parameters
        self.print_variables({"status": self.tc_edited.status_code, "body": self.tc_edited.text})
        body = self.tc_edited.json()
        self.assertEqual(self.tc_edited.status_code, p.STATUS_OK, msg=p.MSG_PRODUCT_EDITED)
        self.assertEqual(
            (body.get("name"), body.get("description"), body.get("status")),
            p.PRODUCT_EDITED_ANSWER,
            msg=p.MSG_PRODUCT_EDITED_VALUES,
        )

    def bud_new_product_is_active(self):
        self.assertEqual(
            self.tc_new_status,
            self.parameters.PRODUCT_STATUS_ACTIVE,
            msg=self.parameters.MSG_PRODUCT_NEW_ACTIVE,
        )

    def bud_product_is_archived(self):
        p = self.parameters
        self.print_variables(
            {"status": self.tc_archived.status_code, "body": self.tc_archived.text}
        )
        self.assertEqual(self.tc_archived.status_code, p.STATUS_OK, msg=p.MSG_PRODUCT_ARCHIVED)
        self.assertEqual(
            self.tc_archived.json().get("status"),
            p.PRODUCT_STATUS_ARCHIVED,
            msg=p.MSG_PRODUCT_ARCHIVED,
        )

    def bud_archived_product_refuses_a_new_run(self):
        p = self.parameters
        self.print_variables(
            {"status": self.tc_archived_run.status_code, "body": self.tc_archived_run.text}
        )
        self.assertEqual(
            self.tc_archived_run.status_code, p.STATUS_CONFLICT, msg=p.MSG_PRODUCT_ARCHIVED_RUN
        )
        self.assertEqual(
            self.tc_archived_run.json().get("detail"),
            p.PRODUCT_ARCHIVED_TEXT,
            msg=p.MSG_PRODUCT_ARCHIVED_TEXT,
        )

    def bud_archived_product_refuses_a_result_upload(self):
        p = self.parameters
        self.print_variables(
            {"status": self.tc_archived_upload.status_code, "body": self.tc_archived_upload.text}
        )
        self.assertEqual(
            self.tc_archived_upload.status_code,
            p.STATUS_CONFLICT,
            msg=p.MSG_PRODUCT_ARCHIVED_UPLOAD,
        )
        self.assertEqual(
            self.tc_archived_upload.json().get("detail"),
            p.PRODUCT_ARCHIVED_TEXT,
            msg=p.MSG_PRODUCT_ARCHIVED_TEXT,
        )

    def bud_archived_product_is_restored(self):
        self.assertEqual(
            self.tc_restored,
            self.parameters.PRODUCT_STATUS_ACTIVE,
            msg=self.parameters.MSG_PRODUCT_RESTORED,
        )

    def bud_restored_product_takes_a_new_run(self):
        self.assertEqual(
            self.tc_restored_run,
            self.parameters.STATUS_CREATED,
            msg=self.parameters.MSG_PRODUCT_RESTORED_RUN,
        )

    def bud_restored_product_takes_a_result_upload(self):
        self.assertEqual(
            self.tc_restored_upload,
            self.parameters.STATUS_CREATED,
            msg=self.parameters.MSG_PRODUCT_RESTORED_UPLOAD,
        )

    def bud_product_changes_are_audited(self):
        self.print_variables({"details": self.tc_updates})
        self.assertEqual(
            self.tc_updates,
            self.parameters.PRODUCT_UPDATED_DETAILS,
            msg=self.parameters.MSG_PRODUCT_AUDITED,
        )

    def bud_renaming_to_a_name_in_use_is_refused(self):
        p = self.parameters
        self.print_variables(
            {"status": self.tc_rename_taken.status_code, "body": self.tc_rename_taken.text}
        )
        self.assertEqual(
            self.tc_rename_taken.status_code, p.STATUS_BAD_REQUEST, msg=p.MSG_PRODUCT_NAME_TAKEN
        )
        self.assertEqual(self.tc_rename_kept, p.PRODUCT_RENAMABLE, msg=p.MSG_PRODUCT_NAME_KEPT)

    def bud_editing_an_unknown_product_is_not_found(self):
        self.assertEqual(
            self.tc_edit_missing,
            self.parameters.STATUS_NOT_FOUND,
            msg=self.parameters.MSG_PRODUCT_EDIT_MISSING,
        )

    def bud_unknown_product_status_is_refused(self):
        self.assertEqual(
            self.tc_unknown_status,
            self.parameters.STATUS_UNPROCESSABLE,
            msg=self.parameters.MSG_PRODUCT_UNKNOWN_STATUS,
        )

    def bud_user_without_manage_cannot_edit_a_product(self):
        self.assertEqual(
            self.tc_viewer_edit,
            self.parameters.STATUS_FORBIDDEN,
            msg=self.parameters.MSG_PRODUCT_VIEWER_EDIT,
        )

    @parameterized(params.PRODUCT_SIGNED_OUT_CALLS)
    def bud_signed_out_visitor_cannot_reach_products(self, method, path):
        self.assertEqual(
            self.tc_signed_out[(method, path)],
            self.parameters.STATUS_UNAUTHORIZED,
            msg=self.parameters.MSG_PRODUCT_SIGNED_OUT,
        )

    def bud_status_lists_the_registered_station(self):
        p = self.parameters
        self.print_variables({"status": self.tc_status.status_code, "body": self.tc_status.text})
        self.assertEqual(self.tc_status.status_code, p.STATUS_OK, msg=p.MSG_STATION_STATUS)
        accounts = {station["account"] for station in self.tc_status.json().get("runners", [])}
        self.assertIn(p.STATION_LISTED, accounts, msg=p.MSG_STATION_LISTED)

    def bud_one_station_is_read(self):
        p = self.parameters
        self.print_variables({"status": self.tc_station.status_code, "body": self.tc_station.text})
        self.assertEqual(self.tc_station.status_code, p.STATUS_OK, msg=p.MSG_STATION_FETCHED)
        self.assertEqual(
            self.tc_station.json().get("account"), p.STATION_SOLO, msg=p.MSG_STATION_ACCOUNT
        )

    def bud_unknown_station_is_not_found(self):
        self.assertEqual(
            self.tc_missing_station,
            self.parameters.STATUS_NOT_FOUND,
            msg=self.parameters.MSG_STATION_MISSING,
        )

    def bud_station_is_deleted(self):
        p = self.parameters
        self.assertEqual(self.tc_station_deleted, p.STATUS_NO_CONTENT, msg=p.MSG_STATION_DELETED)
        self.assertEqual(len(self.tc_station_left), 0, msg=p.MSG_STATION_GONE)

    def bud_deleting_an_unknown_station_is_not_found(self):
        self.assertEqual(
            self.tc_station_delete_missing,
            self.parameters.STATUS_NOT_FOUND,
            msg=self.parameters.MSG_STATION_DELETE_MISSING,
        )

    @parameterized(params.STATION_SIGNED_OUT_CALLS)
    def bud_signed_out_visitor_cannot_reach_stations(self, method, path):
        self.assertEqual(
            self.tc_signed_out[(method, path)],
            self.parameters.STATUS_UNAUTHORIZED,
            msg=self.parameters.MSG_STATION_SIGNED_OUT,
        )
