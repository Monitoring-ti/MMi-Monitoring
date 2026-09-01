"""Motor MMI — consulta por activo y síntoma."""

from mmi.motor.analyze import analyze_motor, resolve_asset
from mmi.motor.hypotheses import INFERENCE_DISCLAIMER, process_hypotheses
from mmi.motor.oem_limits import extract_limits_from_text
from mmi.motor.page import load_motor_fixture, render_motor_html, write_motor_html
from mmi.motor.sensors import get_sensor_readings, load_sensor_fixture
from mmi.motor.session import MotorSession, MotorSessionStore
from mmi.motor.verified_facts import build_measurement_facts

__all__ = [
    "analyze_motor",
    "build_measurement_facts",
    "INFERENCE_DISCLAIMER",
    "process_hypotheses",
    "extract_limits_from_text",
    "get_sensor_readings",
    "load_motor_fixture",
    "load_sensor_fixture",
    "render_motor_html",
    "resolve_asset",
    "MotorSession",
    "MotorSessionStore",
    "write_motor_html",
]
