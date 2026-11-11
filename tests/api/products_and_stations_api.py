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
