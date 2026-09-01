"""Tests Motor MMI M1 (sin red)."""

from mmi.motor.page import load_motor_fixture, render_motor_html, write_motor_html


def test_load_motor_fixture():
    data = load_motor_fixture()
    assert data.get("assets")
    assert data.get("demo_analysis")


def test_render_motor_html_contains_sections():
    html = render_motor_html()
    assert "Motor MMI" in html
    assert "motor-form" in html
    assert "verified_facts" in html or "Hipótesis del sistema" in html
    assert "CTS-DCH-ENF" in html


def test_write_motor_html(tmp_path):
    path = write_motor_html(tmp_path)
    assert path.exists()
    assert "motor.html" in path.name
