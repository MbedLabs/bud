"""Times Bud writes for people: UTC, to the second."""

from datetime import datetime, timedelta, timezone

from app.core.timestamps import second_utc


def test_second_utc_stops_at_seconds():
    assert second_utc(datetime(2026, 9, 27, 12, 34, 56, 789)) == "2026-09-27 12:34:56 UTC"
    assert second_utc(None) == ""


def test_second_utc_converts_an_aware_time_to_utc():
    local = datetime(2026, 9, 27, 14, 34, 56, tzinfo=timezone(timedelta(hours=2)))
    assert second_utc(local) == "2026-09-27 12:34:56 UTC"
