"""Pytest options shared by the scripts/ test suite."""

from __future__ import annotations


def pytest_addoption(parser) -> None:
    parser.addoption("--snapshot-update", action="store_true",
                     help="Rewrite the rendered baseline instead of asserting against it")
