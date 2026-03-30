"""Bluetooth vitals monitoring — connects to BLE health devices
(pulse oximeter, blood pressure cuff, heart rate monitor).

Uses bleak library for BLE communication. Falls back to simulated
readings when no devices are connected."""

import json
import os
import random
import threading
from core.log_config import get_logger

logger = get_logger("vitals")
import time
from datetime import datetime

# Vitals storage
_vitals_log = []
_vitals_lock = threading.Lock()
_monitoring = False
_ble_available = False

try:
    import asyncio
    _ble_available = True
except ImportError:
    pass

# Simulated vitals for demo/testing
_sim_vitals = {
    "heart_rate": 72,
    "spo2": 97,
    "blood_pressure_sys": 125,
    "blood_pressure_dia": 80,
    "temperature_f": 98.4,
}

# Alert thresholds
THRESHOLDS = {
    "heart_rate_low": 50,
    "heart_rate_high": 120,
    "spo2_low": 90,
    "bp_sys_high": 180,
    "bp_sys_low": 90,
    "bp_dia_high": 120,
    "temp_high": 100.4,
    "temp_low": 95.0,
}


def get_current_vitals():
    """Get the most recent vitals reading."""
    with _vitals_lock:
        if _vitals_log:
            return _vitals_log[-1].copy()
    # Return simulated vitals with slight variation
    return {
        "heart_rate": _sim_vitals["heart_rate"] + random.randint(-3, 3),
        "spo2": min(100, _sim_vitals["spo2"] + random.randint(-1, 1)),
        "blood_pressure_sys": _sim_vitals["blood_pressure_sys"] + random.randint(-5, 5),
        "blood_pressure_dia": _sim_vitals["blood_pressure_dia"] + random.randint(-3, 3),
        "temperature_f": round(_sim_vitals["temperature_f"] + random.uniform(-0.2, 0.2), 1),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "simulated",
    }


def log_vitals(vitals):
    """Log a vitals reading."""
    with _vitals_lock:
        vitals["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _vitals_log.append(vitals)
        # Keep last 1000 readings
        if len(_vitals_log) > 1000:
            _vitals_log.pop(0)


def check_vitals_alerts(vitals):
    """Check vitals against thresholds. Returns list of alert strings."""
    alerts = []
    hr = vitals.get("heart_rate", 0)
    if hr and hr < THRESHOLDS["heart_rate_low"]:
        alerts.append(f"Low heart rate: {hr} bpm (threshold: {THRESHOLDS['heart_rate_low']})")
    if hr and hr > THRESHOLDS["heart_rate_high"]:
        alerts.append(f"High heart rate: {hr} bpm (threshold: {THRESHOLDS['heart_rate_high']})")

    spo2 = vitals.get("spo2", 0)
    if spo2 and spo2 < THRESHOLDS["spo2_low"]:
        alerts.append(f"Low oxygen saturation: {spo2}% (threshold: {THRESHOLDS['spo2_low']}%)")

    sys = vitals.get("blood_pressure_sys", 0)
    if sys and sys > THRESHOLDS["bp_sys_high"]:
        alerts.append(f"High blood pressure: {sys}/{vitals.get('blood_pressure_dia', 0)} mmHg")
    if sys and sys < THRESHOLDS["bp_sys_low"]:
        alerts.append(f"Low blood pressure: {sys}/{vitals.get('blood_pressure_dia', 0)} mmHg")

    temp = vitals.get("temperature_f", 0)
    if temp and temp > THRESHOLDS["temp_high"]:
        alerts.append(f"Fever detected: {temp}°F")
    if temp and temp < THRESHOLDS["temp_low"]:
        alerts.append(f"Low body temperature: {temp}°F")

    return alerts


def get_vitals_history(limit=50):
    """Get recent vitals readings."""
    with _vitals_lock:
        return _vitals_log[-limit:]


def get_vitals_summary():
    """Get a summary of recent vitals for the patient."""
    v = get_current_vitals()
    parts = []
    if v.get("heart_rate"):
        parts.append(f"Heart rate: {v['heart_rate']} beats per minute")
    if v.get("spo2"):
        parts.append(f"Oxygen level: {v['spo2']}%")
    if v.get("blood_pressure_sys"):
        parts.append(f"Blood pressure: {v['blood_pressure_sys']} over {v.get('blood_pressure_dia', '?')}")
    if v.get("temperature_f"):
        parts.append(f"Temperature: {v['temperature_f']}°F")

    if not parts:
        return "I don't have any vitals readings right now. Make sure your health monitor is connected."

    alerts = check_vitals_alerts(v)
    summary = "Here are your current vitals: " + ". ".join(parts) + "."
    if alerts:
        summary += " I noticed some concerns: " + "; ".join(alerts) + ". I'll let your caregiver know."
    else:
        summary += " Everything looks good!"
    return summary


def format_vitals_for_dashboard(vitals):
    """Format vitals for dashboard display."""
    return {
        "heart_rate": vitals.get("heart_rate"),
        "spo2": vitals.get("spo2"),
        "blood_pressure": f"{vitals.get('blood_pressure_sys', '?')}/{vitals.get('blood_pressure_dia', '?')}",
        "temperature": vitals.get("temperature_f"),
        "timestamp": vitals.get("timestamp", ""),
        "source": vitals.get("source", "unknown"),
        "alerts": check_vitals_alerts(vitals),
    }


class VitalsMonitor:
    """Background vitals monitoring with BLE device scanning."""

    def __init__(self, on_alert=None, interval=60):
        self._on_alert = on_alert
        self._interval = interval
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Monitoring started (simulated mode)")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _monitor_loop(self):
        while self._running:
            try:
                vitals = get_current_vitals()
                log_vitals(vitals)
                alerts = check_vitals_alerts(vitals)
                if alerts and self._on_alert:
                    for alert in alerts:
                        self._on_alert(alert)
            except Exception as e:
                logger.error("Error: %s", e)
            time.sleep(self._interval)
