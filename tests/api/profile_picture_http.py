"""
* @file     ${tests/api/profile_picture_http.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests an account's own profile picture over HTTP.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of picture upload, validation and isolation.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class ProfilePictureHttpBase(BudAppTestCase):

    def bud_picture_round_trip_is_account_scoped(self):
        p, found = self.parameters, self.tc_round_trip
        self.print_variables(found)
        self.assertEqual(found["none yet"], p.STATUS_NOT_FOUND, msg=p.MSG_PICTURE_NONE_YET)
        self.assertEqual(found["saved"], p.STATUS_OK, msg=p.MSG_PICTURE_SAVED)
        self.assertEqual(found["flag"], True, msg=p.MSG_PICTURE_FLAG)
        self.assertEqual(found["bytes in view"], False, msg=p.MSG_PICTURE_NOT_IN_VIEW)
        self.assertEqual(found["read"], p.STATUS_OK, msg=p.MSG_PICTURE_READ)
        self.assertEqual(found["type"], p.PICTURE_PNG, msg=p.MSG_PICTURE_TYPE)
        self.assertEqual(found["cache"], p.PICTURE_NO_STORE, msg=p.MSG_PICTURE_NO_STORE)
        self.assertEqual(found["size"], p.PICTURE_STORED_SIZE, msg=p.MSG_PICTURE_SIZE)
        self.assertEqual(found["metadata kept"], False, msg=p.MSG_PICTURE_NO_METADATA)
        self.assertEqual(found["view flag"], True, msg=p.MSG_PICTURE_FLAG)
        self.assertEqual(found["other none"], p.STATUS_NOT_FOUND, msg=p.MSG_PICTURE_OTHER_NONE)
        self.assertEqual(found["other saved"], p.STATUS_OK, msg=p.MSG_PICTURE_OTHER_SAVED)
        self.assertEqual(found["first unchanged"], True, msg=p.MSG_PICTURE_KEPT)
        self.assertEqual(found["replaced saved"], p.STATUS_OK, msg=p.MSG_PICTURE_SAVED)
        self.assertEqual(found["replaced"], True, msg=p.MSG_PICTURE_REPLACED)

    def bud_profile_save_keeps_the_permissions(self):
        p, found = self.parameters, self.tc_profile
        self.print_variables(found)
        self.assertEqual(found["saved"], p.STATUS_OK, msg=p.MSG_PICTURE_PROFILE_SAVED)
        self.assertEqual(found["name"], p.PICTURE_RENAMED, msg=p.MSG_PICTURE_PROFILE_NAME)
        self.assertEqual(bool(found["before"]), True, msg=p.MSG_PICTURE_PERMISSIONS)
        self.assertEqual(found["after"], found["before"], msg=p.MSG_PICTURE_PERMISSIONS_KEPT)

    @parameterized(params.PICTURE_REJECTED)
    def bud_rejected_upload_keeps_the_saved_picture(self, case):
        p = self.parameters
        saved, status, kept = self.tc_rejected[case]
        self.print_variables({"case": case, "saved": saved, "status": status, "kept": kept})
        self.assertEqual(saved, p.STATUS_OK, msg=p.MSG_PICTURE_SAVED)
        self.assertEqual(status, p.PICTURE_REJECTED[case][2], msg=p.MSG_PICTURE_REJECTED)
        self.assertEqual(kept, True, msg=p.MSG_PICTURE_PRESERVED)

    def bud_signed_out_visitor_cannot_reach_a_picture(self):
        self.print_variables({"statuses": self.tc_signed_out})
        self.assertEqual(
            self.tc_signed_out,
            [self.parameters.STATUS_UNAUTHORIZED] * 3,
            msg=self.parameters.MSG_PICTURE_SIGNED_OUT,
        )

    def bud_removal_is_account_scoped_and_repeatable(self):
        p, found = self.parameters, self.tc_removal
        self.print_variables(found)
        self.assertEqual(found["saved"], [p.STATUS_OK, p.STATUS_OK], msg=p.MSG_PICTURE_SAVED)
        self.assertEqual(found["removed"], p.STATUS_OK, msg=p.MSG_PICTURE_REMOVED)
        self.assertEqual(found["flag"], False, msg=p.MSG_PICTURE_REMOVED_FLAG)
        self.assertEqual(found["bytes in view"], False, msg=p.MSG_PICTURE_NOT_IN_VIEW)
        self.assertEqual(found["view after"], found["view before"], msg=p.MSG_PICTURE_VIEW_KEPT)
        self.assertEqual(found["gone"], p.STATUS_NOT_FOUND, msg=p.MSG_PICTURE_GONE)
        self.assertEqual(found["other view kept"], True, msg=p.MSG_PICTURE_OTHER_VIEW_KEPT)
        self.assertEqual(found["other picture kept"], True, msg=p.MSG_PICTURE_KEPT)
        self.assertEqual(found["removed again"], p.STATUS_OK, msg=p.MSG_PICTURE_REMOVED_AGAIN)
        self.assertEqual(found["saved again"], p.STATUS_OK, msg=p.MSG_PICTURE_UPLOAD_AGAIN)
        self.assertEqual(found["read again"], p.STATUS_OK, msg=p.MSG_PICTURE_READ)

    def bud_format_must_match_and_size_is_bounded(self):
        p, found = self.parameters, self.tc_bounds
        self.print_variables(found)
        self.assertEqual(found["mismatch"], p.STATUS_UNSUPPORTED_MEDIA, msg=p.MSG_PICTURE_MISMATCH)
        self.assertEqual(found["huge"], p.STATUS_UNPROCESSABLE, msg=p.MSG_PICTURE_TOO_LARGE)
        self.assertEqual(found["none saved"], p.STATUS_NOT_FOUND, msg=p.MSG_PICTURE_NONE_SAVED)

    def bud_jpeg_orientation_is_applied_without_exif(self):
        p, found = self.parameters, self.tc_jpeg
        self.print_variables(found)
        self.assertEqual(found["saved"], p.STATUS_OK, msg=p.MSG_PICTURE_JPEG)
        self.assertEqual(found["size"], p.PICTURE_ROTATED_SIZE, msg=p.MSG_PICTURE_ORIENTED)
        self.assertEqual(found["exif"], False, msg=p.MSG_PICTURE_NO_EXIF)
