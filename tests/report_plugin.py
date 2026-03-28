"""
Custom pytest plugin for enhanced HTML test reports.

Injects service version, build info, and target URL into the pytest-html
report header. Provides a clear summary of what was tested and when.
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

    # Use synchronous httpx client (session hooks are sync)
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


@pytest.hookimpl(optionalhook=True)
def pytest_html_report_title(report):
    """Set the HTML report title."""
    report.title = "ID Generator - Test Report"


@pytest.hookimpl(optionalhook=True)
def pytest_html_results_summary(prefix, summary, postfix):
    """Inject service metadata into the report summary section."""
    # This hook is only available if pytest-html is installed
    pass


@pytest.hookimpl(tryfirst=True, optionalhook=True)
def pytest_metadata(metadata, config):
    """
    Add service metadata to the Environment table in the HTML report.

    This uses pytest-metadata (bundled with pytest-html) to populate
    the 'Environment' section of the report.
    """
    meta = config._idgen_metadata
    metadata["Service Version"] = meta["service_version"]
    metadata["Git Commit"] = meta["git_commit"]
    metadata["Build Time"] = meta["build_time"]
    metadata["Target URL"] = meta["target_url"]
    metadata["Test Run Time"] = meta["test_run_time"]
