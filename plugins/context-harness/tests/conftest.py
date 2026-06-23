import time

import pytest


@pytest.fixture(autouse=True)
def stable_timezone(monkeypatch):
    monkeypatch.setenv("TZ", "UTC")
    if hasattr(time, "tzset"):
        time.tzset()
    yield
    if hasattr(time, "tzset"):
        time.tzset()


@pytest.fixture
def set_timezone(monkeypatch):
    def _set_timezone(timezone_name: str) -> None:
        monkeypatch.setenv("TZ", timezone_name)
        if hasattr(time, "tzset"):
            time.tzset()

    return _set_timezone
