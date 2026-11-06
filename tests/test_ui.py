"""
UI tests for Streamlit application using official Streamlit AppTest framework.
Verifies all 7 sections of OPSRECALL dashboard render without exceptions.
"""

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
    sidebar_radio = at.sidebar.radio[0]
    sidebar_radio.set_value("Incident Console").run(timeout=15)
    assert not at.exception
    assert "Incident Telemetry Console" in at.title[0].value


def test_navigation_to_investigation_and_comparison():
    at = AppTest.from_file("app.py")
    at.run(timeout=15)
    sidebar_radio = at.sidebar.radio[0]
    sidebar_radio.set_value("AI Investigation & Comparison").run(timeout=15)
    assert not at.exception
    assert "AI Incident Investigation & Comparison" in at.title[0].value


def test_navigation_to_memory_explorer():
    at = AppTest.from_file("app.py")
    at.run(timeout=15)
    sidebar_radio = at.sidebar.radio[0]
    sidebar_radio.set_value("Memory Explorer").run(timeout=15)
    assert not at.exception
    assert "Hindsight Memory Explorer" in at.title[0].value


def test_navigation_to_learning_center():
    at = AppTest.from_file("app.py")
    at.run(timeout=15)
    sidebar_radio = at.sidebar.radio[0]
    sidebar_radio.set_value("Learning Center").run(timeout=15)
    assert not at.exception
    assert "Incident Learning Center" in at.title[0].value


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
