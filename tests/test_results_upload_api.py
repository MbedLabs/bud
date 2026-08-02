"""Result submission: the path a Test Station actually drives."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Product, TestResult, TestRun


def _result(test_class="SmokeTests", test_method="test_boot", passed=True, **overrides) -> dict:
    base = {
        "test_class": test_class,
        "test_method": test_method,
        "passed": passed,
        "duration_seconds": 1.5,
    }
    base.update(overrides)
    return base


class TestUploadingResults:
    def test_uploads_against_an_existing_run(self, client):
        run_id = client.post(
            "/api/test-runs",
            json={"test_suite_name": "Nightly", "test_case_list": "SmokeTests"},
        ).json()["id"]

        response = client.post(
            "/api/results", json={"test_run_id": run_id, "results": [_result()]}
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["test_run_id"] == run_id
        assert body["count"] == 1

    def test_creates_a_run_when_none_is_supplied(self, client):
        """A station can post results without having opened a run first."""
        response = client.post(
            "/api/results",
            json={"test_suite_name": "Ad-hoc suite", "results": [_result()]},
        )
        assert response.status_code == 201, response.text
        run_id = response.json()["test_run_id"]

        created = client.get(f"/api/test-runs/{run_id}")
        assert created.status_code == 200
        assert "Ad-hoc suite" in created.json()["name"]

    @pytest.mark.asyncio
    async def test_the_auto_created_run_is_named_after_the_product(self, client, db_session):
        product = Product(name="Gateway ECU")
        db_session.add(product)
        await db_session.commit()
        await db_session.refresh(product)

        response = client.post(
            "/api/results",
            json={
                "product_id": product.id,
                "test_suite_name": "Regression",
                "results": [_result()],
            },
        )
        assert response.status_code == 201, response.text
        name = client.get(f"/api/test-runs/{response.json()['test_run_id']}").json()["name"]
        assert "Gateway ECU" in name
        assert "Regression" in name

    def test_uploading_to_an_unknown_run_is_404(self, client):
        response = client.post(
            "/api/results", json={"test_run_id": 99999, "results": [_result()]}
        )
        assert response.status_code == 404

    def test_accepts_a_failing_result_with_its_traceback(self, client):
        response = client.post(
            "/api/results",
            json={
                "test_suite_name": "Failures",
                "results": [
                    _result(
                        passed=False,
                        error_message="assertion failed",
                        traceback="Traceback (most recent call last): ...",
                    )
                ],
            },
        )
        assert response.status_code == 201, response.text

    def test_accepts_assertions_and_metadata(self, client):
        response = client.post(
            "/api/results",
            json={
                "test_suite_name": "Rich",
                "results": [
                    _result(
                        assertions=[{"name": "voltage", "passed": True, "actual": 3.3}],
                        metadata={"bench": "lab-01"},
                    )
                ],
            },
        )
        assert response.status_code == 201, response.text

    def test_rejects_a_payload_with_no_results_field(self, client):
        assert client.post("/api/results", json={"test_suite_name": "x"}).status_code == 422


class TestRunStatisticsFromResults:
    """The run's counters are aggregated at the test-class level, not per method."""

    def test_a_class_passes_only_when_every_method_passes(self, client):
        response = client.post(
            "/api/results",
            json={
                "test_suite_name": "Mixed",
                "results": [
                    _result("ClassA", "test_one", True),
                    _result("ClassA", "test_two", False),
                    _result("ClassB", "test_three", True),
                ],
            },
        )
        run_id = response.json()["test_run_id"]

        run = client.get(f"/api/test-runs/{run_id}").json()
        assert run["total_tests"] == 2, "two classes, not three methods"
        assert run["passed_tests"] == 1, "ClassA has a failing method"
        assert run["failed_tests"] == 1

    def test_duration_is_summed_across_every_method(self, client):
        response = client.post(
            "/api/results",
            json={
                "test_suite_name": "Timed",
                "results": [
                    _result("C", "a", True, duration_seconds=1.5),
                    _result("C", "b", True, duration_seconds=2.5),
                ],
            },
        )
        run = client.get(f"/api/test-runs/{response.json()['test_run_id']}").json()
        assert run["duration_seconds"] == pytest.approx(4.0)

    def test_uploading_completes_the_run(self, client):
        run_id = client.post(
            "/api/test-runs", json={"test_suite_name": "ToComplete", "test_case_list": "C"}
        ).json()["id"]
        assert client.get(f"/api/test-runs/{run_id}").json()["status"] == "Running"

        client.post("/api/results", json={"test_run_id": run_id, "results": [_result()]})

        completed = client.get(f"/api/test-runs/{run_id}").json()
        assert completed["status"] == "Completed"
        assert completed["completed_at"] is not None

    def test_uploading_records_an_event(self, client):
        run_id = client.post(
            "/api/test-runs", json={"test_suite_name": "Evented", "test_case_list": "C"}
        ).json()["id"]
        before = len(client.get(f"/api/test-runs/{run_id}/events").json())

        client.post("/api/results", json={"test_run_id": run_id, "results": [_result()]})
        after = client.get(f"/api/test-runs/{run_id}/events").json()
        assert len(after) > before
        assert any("Results uploaded" in event["title"] for event in after)


class TestReadingResults:
    def test_lists_the_results_of_a_run(self, client):
        response = client.post(
            "/api/results",
            json={
                "test_suite_name": "Listed",
                "results": [_result("C", "a"), _result("C", "b")],
            },
        )
        run_id = response.json()["test_run_id"]

        listed = client.get(f"/api/results/{run_id}")
        assert listed.status_code == 200, listed.text
        assert len(listed.json()) == 2

    def test_listing_an_unknown_run_is_404(self, client):
        assert client.get("/api/results/99999").status_code == 404

    @pytest.mark.asyncio
    async def test_fetches_one_result(self, client, db_session):
        response = client.post(
            "/api/results", json={"test_suite_name": "Single", "results": [_result()]}
        )
        run_id = response.json()["test_run_id"]
        result_id = (
            await db_session.execute(
                select(TestResult.id).where(TestResult.test_run_id == run_id)
            )
        ).scalar_one()

        detail = client.get(f"/api/results/detail/{result_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["test_class"] == "SmokeTests"

    def test_unknown_result_is_404(self, client):
        assert client.get("/api/results/detail/99999").status_code == 404

    def test_results_require_authentication(self, unauthenticated_client):
        for method, path in [
            ("POST", "/api/results"),
            ("GET", "/api/results/1"),
            ("GET", "/api/results/detail/1"),
        ]:
            response = unauthenticated_client.request(method, path, json={"results": []})
            assert response.status_code == 401, f"{method} {path} was {response.status_code}"
