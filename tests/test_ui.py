"""
UI tests for Streamlit application using official Streamlit AppTest framework.
"""

import pytest
from streamlit.testing.v1 import AppTest


def test_command_center_renders_cleanly():
    at = AppTest.from_file("app.py")
    at.run(timeout=15)
    assert not at.exception
    assert len(at.title) >= 1
    assert "Command Center" in at.title[0].value
    assert len(at.metric) >= 4


def test_navigation_to_incident_console():
    at = AppTest.from_file("app.py")
    at.run(timeout=15)
    # Switch to Incident Console
    sidebar_radio = at.sidebar.radio[0]
    sidebar_radio.set_value("Incident Console").run(timeout=15)
    assert not at.exception
    assert "Incident Telemetry Console" in at.title[0].value


def test_navigation_to_evaluation_lab():
    at = AppTest.from_file("app.py")
    at.run(timeout=15)
    sidebar_radio = at.sidebar.radio[0]
    sidebar_radio.set_value("Evaluation Lab").run(timeout=15)
    assert not at.exception
    assert "Evaluation Lab" in at.title[0].value


def test_navigation_to_architecture():
    at = AppTest.from_file("app.py")
    at.run(timeout=15)
    sidebar_radio = at.sidebar.radio[0]
    sidebar_radio.set_value("Architecture & About").run(timeout=15)
    assert not at.exception
    assert "Architecture & Technology" in at.title[0].value

