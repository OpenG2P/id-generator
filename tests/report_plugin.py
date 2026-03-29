"""
Custom pytest plugin for enhanced HTML test reports.

Injects service version, build info, and target URL into the pytest-html
report. Works with pytest-html >= 4.0 and pytest-metadata >= 3.0.
"""

import os
from datetime import datetime, timezone

import httpx
import pytest


def pytest_configure(config):
    """Store metadata on config for later use by report hooks."""
    config._idgen_metadata = {
        "service_version": "unknown",
        "git_commit": "unknown",
        "build_time": "unknown",
        "target_url": "unknown",
        "test_run_time": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        ),
    }


def pytest_sessionstart(session):
    """Fetch version info from the service at session start."""
    base_url = session.config.getoption("--base-url", default=None)
    if base_url is None:
        base_url = os.environ.get("IDGEN_BASE_URL", "http://localhost:8000")
    base_url = base_url.rstrip("/")

    session.config._idgen_metadata["target_url"] = base_url

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{base_url}/v1/idgenerator/version")
            if resp.status_code == 200:
                data = resp.json()
                version_info = data.get("response", {})
                session.config._idgen_metadata["service_version"] = (
                    version_info.get("service_version", "unknown")
                )
                session.config._idgen_metadata["git_commit"] = (
                    version_info.get("git_commit", "unknown")
                )
                session.config._idgen_metadata["build_time"] = (
                    version_info.get("build_time", "unknown")
                )
    except Exception:
        pass  # Metadata stays as "unknown"

    # Update the pytest-metadata stash so it appears in the Environment table.
    # pytest-metadata 3.x stores data in config.stash[metadata_key].
    # This runs after pytest_configure, so the stash already exists.
    try:
        from pytest_metadata.plugin import metadata_key

        meta = session.config._idgen_metadata
        stash = session.config.stash[metadata_key]
        stash["Service Version"] = meta["service_version"]
        stash["Git Commit"] = meta["git_commit"]
        stash["Build Time"] = meta["build_time"]
        stash["Target URL"] = meta["target_url"]
        stash["Test Run Time"] = meta["test_run_time"]
    except Exception:
        pass


@pytest.hookimpl(optionalhook=True)
def pytest_html_report_title(report):
    """Set the HTML report title."""
    report.title = "ID Generator - Test Report"
