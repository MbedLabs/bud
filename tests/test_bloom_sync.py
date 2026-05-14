from types import SimpleNamespace

from app.services.bloom_sync import _coalesce_results_by_tc_id


async def async_iter(iterable):
    for item in iterable:
        yield item


async def test_coalesce_results_by_tc_id_reduces_methods_to_one_tc_result():
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

    coalesced = await _coalesce_results_by_tc_id(async_iter(results), 5)
    payload = sorted(coalesced, key=lambda item: item["tc_id"])

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
            "comment": f"Last result from Bud run 5, executed at {payload[1]['executed_at']}",
            "executed_at": payload[1]["executed_at"],
            "status": "Passed",
            "tc_id": "FLT-TC-035",
        },
    ]
