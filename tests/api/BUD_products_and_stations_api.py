"""
* @file     ${tests/api/BUD_products_and_stations_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Administrators add, list, read and delete products and read and delete Test Stations.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests each scenario on a freshly started app; signed-out calls get 401.
"""

from app.models import AuditEvent, Product, Runner, User
from tests.api.products_and_stations_api import ProductsAndStationsApiBase


class ProductsAndStationsApiTest(ProductsAndStationsApiBase):

    def setUpClass(self):
        super().setUpClass()
        p, start, request = self.parameters, self.bud.bud_start_app, self.bud.bud_request
        start()
        self.tc_created = request(p.POST, p.PRODUCTS_PATH, json=p.PRODUCT)
        start()
        self.tc_first = request(p.POST, p.PRODUCTS_PATH, json=p.PRODUCT_DUPLICATE).status_code
        self.tc_second = request(p.POST, p.PRODUCTS_PATH, json=p.PRODUCT_DUPLICATE)
        start()
        for name in p.PRODUCT_NAMES:
            request(p.POST, p.PRODUCTS_PATH, json={"name": name})
        self.tc_listed = [product["name"] for product in request(p.GET, p.PRODUCTS_PATH).json()]
        start()
        product_id = request(p.POST, p.PRODUCTS_PATH, json={"name": p.PRODUCT_FETCHED}).json().get("id")
        self.tc_fetched = request(p.GET, p.PRODUCT_PATH.format(product_id))
        start()
        self.tc_missing_product = request(
            p.GET, p.PRODUCT_PATH.format(p.PRODUCT_MISSING_ID)
        ).status_code
        start()
        product_id = request(p.POST, p.PRODUCTS_PATH, json={"name": p.PRODUCT_DELETED}).json().get("id")
        self.tc_product_deleted = request(p.DELETE, p.PRODUCT_PATH.format(product_id)).status_code
        self.tc_product_left = self.bud.bud_find_in_app(Product, id=product_id)
        start()
        self.tc_product_delete_missing = request(
            p.DELETE, p.PRODUCT_PATH.format(p.PRODUCT_MISSING_ID)
        ).status_code
        start()
        product_id = request(p.POST, p.PRODUCTS_PATH, json=p.PRODUCT_EDITABLE).json().get("id")
        self.tc_edited = request(p.PATCH, p.PRODUCT_PATH.format(product_id), json=p.PRODUCT_EDIT)
        start()
        self.archive_and_restore()
        start()
        request(p.POST, p.PRODUCTS_PATH, json={"name": p.PRODUCT_NAME_TAKEN})
        product_id = request(p.POST, p.PRODUCTS_PATH, json={"name": p.PRODUCT_RENAMABLE}).json().get("id")
        path = p.PRODUCT_PATH.format(product_id)
        self.tc_rename_taken = request(p.PATCH, path, json={"name": p.PRODUCT_NAME_TAKEN})
        self.tc_rename_kept = request(p.GET, path).json().get("name")
        self.tc_unknown_status = request(p.PATCH, path, json=p.PRODUCT_UNKNOWN_STATUS).status_code
        self.bud.bud_sign_in_as(self.bud.bud_add_to_app(User(**p.PRODUCT_VIEWER)))
        self.tc_viewer_edit = request(p.PATCH, path, json=p.PRODUCT_EDIT).status_code
        start()
        self.tc_edit_missing = request(
            p.PATCH, p.PRODUCT_PATH.format(p.PRODUCT_MISSING_ID), json=p.PRODUCT_EDIT
        ).status_code
        start()
        self.add_station(p.STATION_LISTED)
        self.tc_status = request(p.GET, p.STATIONS_STATUS_PATH)
        start()
        self.add_station(p.STATION_SOLO)
        self.tc_station = request(p.GET, p.STATION_PATH.format(p.STATION_SOLO))
        start()
        self.tc_missing_station = request(p.GET, p.STATION_PATH.format(p.STATION_GHOST)).status_code
        start()
        self.add_station(p.STATION_GONE)
        self.tc_station_deleted = request(
            p.DELETE, p.STATION_PATH.format(p.STATION_GONE)
        ).status_code
        self.tc_station_left = self.bud.bud_find_in_app(Runner, account=p.STATION_GONE)
        start()
        self.tc_station_delete_missing = request(
            p.DELETE, p.STATION_PATH.format(p.STATION_GHOST)
        ).status_code
        start(signed_in=False)
        self.tc_signed_out = {
            (method, path): request(method, path, json=p.PRODUCT_SIGNED_OUT_BODY).status_code
            for method, path in p.PRODUCT_SIGNED_OUT_CALLS
        }
        start(signed_in=False)
        self.tc_signed_out.update(
            {
                (method, path): request(method, path).status_code
                for method, path in p.STATION_SIGNED_OUT_CALLS
            }
        )

    def archive_and_restore(self):
        """Archive a product, send it a run and an upload, then restore it and send both again."""
        p, request, station = self.parameters, self.bud.bud_request, self.bud.bud_station_request
        product_id = request(p.POST, p.PRODUCTS_PATH, json={"name": p.PRODUCT_ARCHIVABLE}).json().get("id")
        path = p.PRODUCT_PATH.format(product_id)
        run = {**p.PRODUCT_RUN, "product_composition_id": product_id}
        upload = {
            "product_id": product_id,
            "test_suite_name": p.PRODUCT_UPLOAD_SUITE,
            "results": [p.UPLOAD_RESULT],
        }
        self.bud.bud_add_test_station(with_run=False)
        self.tc_new_status = request(p.GET, path).json().get("status")
        self.tc_archived = request(p.PATCH, path, json=p.PRODUCT_ARCHIVE)
        self.tc_archived_run = station(p.POST, p.TEST_RUNS_PATH, json=run)
        self.tc_archived_upload = station(p.POST, p.RESULTS_PATH, json=upload)
        self.tc_restored = request(p.PATCH, path, json=p.PRODUCT_RESTORE).json().get("status")
        self.tc_restored_run = station(p.POST, p.TEST_RUNS_PATH, json=run).status_code
        self.tc_restored_upload = station(p.POST, p.RESULTS_PATH, json=upload).status_code
        self.tc_updates = [
            event.details
            for event in self.bud.bud_find_in_app(AuditEvent, action=p.PRODUCT_UPDATED_ACTION)
        ]

    def add_station(self, account):
        """Register a Test Station with the given account."""
        return self.bud.bud_add_to_app(
            Runner(
                account=account,
                password_hash=self.parameters.STATION_PASSWORD,
                token=self.parameters.STATION_TOKEN_PREFIX + account,
            )
        )

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ProductsAndStationsApiTest().run()
