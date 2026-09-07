import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_status_route_exposes_build_release_and_monitoring_identity():
    page = (ROOT / "src/pages/status/index.astro").read_text(encoding="utf-8")
    endpoint = (ROOT / "src/pages/status.json.ts").read_text(encoding="utf-8")
    status_lib = (ROOT / "src/lib/build-status.ts").read_text(encoding="utf-8")

    assert "Deployed build" in page
    assert "Release freshness" in page
    assert "Synthetic monitoring" in page
    assert "getBuildStatus()" in endpoint
    assert "project-finer-status-v1" in status_lib
    assert "GITHUB_SHA" in status_lib
    assert "freshnessTargetDays" in status_lib


def test_release_catalog_supports_the_public_freshness_measure():
    catalog = json.loads((ROOT / "public/releases/index.json").read_text(encoding="utf-8"))

    assert catalog["releases"]
    assert all(release.get("latestPeriod") for release in catalog["releases"])


def test_synthetic_monitor_checks_routes_commit_and_freshness():
    workflow = (ROOT / ".github/workflows/site-monitor.yml").read_text(encoding="utf-8")

    assert "schedule:" in workflow
    assert "/status.json" in workflow
    assert "/commits/main" in workflow
    assert "deployed_sha != main_sha" in workflow
    assert "freshnessStatus" in workflow
