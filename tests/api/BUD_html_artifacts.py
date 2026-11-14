"""
* @file     ${tests/api/BUD_html_artifacts.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    An HTML report uploads as an artifact and only ever downloads, sandboxed.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests a log.html with a script, uploaded by a Test Station to its run.
"""

from tests.api.html_artifacts import HtmlArtifactsBase


class HtmlArtifactsTest(HtmlArtifactsBase):

    def setUpClass(self):
        super().setUpClass()
        self.bud.bud_start_app()
        self.bud.bud_add_test_station()
        self.tc_upload = self.bud.bud_station_upload(
            self.parameters.HTML_REPORT_NAME,
            self.parameters.HTML_REPORT_CONTENT,
            self.parameters.HTML_TYPE,
        )
        self.tc_download = self.bud.bud_request(
            self.parameters.GET,
            self.parameters.UPLOAD_PATH.format(self.tc_upload.json().get("id")),
        )

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    HtmlArtifactsTest().run()
