from types import SimpleNamespace

from app.services.bloom_sync import _coalesce_results_by_tc_id


def test_coalesce_results_by_tc_id_reduces_methods_to_one_tc_result():
    results = [
        SimpleNamespace(
            passed=True,
            error_message=None,
            created_at=None,
            test_metadata={"tc_id": "FLT-TC-001"},
        ),
        SimpleNamespace(
            passed=False,
            error_message="Invalid credentials produce a documented failure outcome",
            created_at=None,
            test_metadata={"tc_id": "FLT-TC-001"},
        ),
        SimpleNamespace(
            passed=True,
            error_message=None,
            created_at=None,
            test_metadata={"tc_id": "FLT-TC-035"},
        ),
    ]

    payload = sorted(_coalesce_results_by_tc_id(results, 5), key=lambda item: item["tc_id"])

    assert payload == [
        {
            "bud_run_id": 5,
            "comment": "Invalid credentials produce a documented failure outcome",
            "executed_at": payload[0]["executed_at"],
            "status": "Failed",
            "tc_id": "FLT-TC-001",
        },
        {
            "bud_run_id": 5,
            "comment": "Automated sync from Bud TMP",
            "executed_at": payload[1]["executed_at"],
            "status": "Passed",
            "tc_id": "FLT-TC-035",
        },
    ]
