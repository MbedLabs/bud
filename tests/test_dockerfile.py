from pathlib import Path


def test_ui_build_stage_runs_on_build_platform():
    dockerfile_lines = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text().splitlines()
    ui_build_from = [
        line for line in dockerfile_lines if line.startswith("FROM ") and line.endswith(" AS ui-build")
    ]

    assert len(ui_build_from) == 1
    assert "--platform=$BUILDPLATFORM" in ui_build_from[0].split()
