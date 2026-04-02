"""Shared pytest fixtures and configuration for all test modules."""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "real_agent: test requires live LLM API access (KILO_API_KEY or KILOCODE_TOKEN)",
    )
