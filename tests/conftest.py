import pytest
import os


@pytest.fixture
def mock_display(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":99")
