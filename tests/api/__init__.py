"""The Bud suites of tests/api, as bud-runner run-tests -t tests.api.SUITES runs them."""

import tests.config  # noqa: F401

SUITES = [
    "tests.api.BUD_run_stats_distinct.RunStatsDistinctTest",
    "tests.api.BUD_health.HealthTest",
    "tests.api.BUD_html_artifacts.HtmlArtifactsTest",
    "tests.api.BUD_run_report_assertions.RunReportAssertionsTest",
    "tests.api.BUD_observability.ObservabilityTest",
    "tests.api.BUD_users.UsersTest",
    "tests.api.BUD_setup_api.SetupApiTest",
    "tests.api.BUD_notification_channels_api.NotificationChannelsApiTest",
    "tests.api.BUD_products_and_stations_api.ProductsAndStationsApiTest",
    "tests.api.BUD_artifact_storage.ArtifactStorageTest",
    "tests.api.BUD_results_listing_payload_api.ResultsListingPayloadApiTest",
    "tests.api.BUD_station_naming.StationNamingTest",
    "tests.api.BUD_bloom_artefact_backlink.BloomArtefactBacklinkTest",
    "tests.api.BUD_run_stats_api.RunStatsApiTest",
    "tests.api.BUD_profile_picture_http.ProfilePictureHttpTest",
    "tests.api.BUD_object_storage.ObjectStorageTest",
    "tests.api.BUD_unhandled_errors_http.UnhandledErrorsHttpTest",
    "tests.api.BUD_run_artifacts_api.RunArtifactsApiTest",
    "tests.api.BUD_results_api.ResultsApiTest",
    "tests.api.BUD_runs_api.RunsApiTest",
    "tests.api.BUD_runner_api_keys.RunnerApiKeysTest",
    "tests.api.BUD_runners_register_api.RunnersRegisterApiTest",
    "tests.api.BUD_results_upload_api.ResultsUploadApiTest",
    "tests.api.BUD_run_reports_stored.RunReportsStoredTest",
    "tests.api.BUD_users_api.UsersApiTest",
    "tests.api.BUD_group_overlap_api.GroupOverlapApiTest",
    "tests.api.BUD_bloom_sync.BloomSyncTest",
]
