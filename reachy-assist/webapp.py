"""Lightweight Flask API for receiving teleoperation commands from the dashboard.
Started automatically by the interaction loop or can run standalone."""

import threading
import time
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Reference to the Robot instance — set by whoever starts this server
_robot = None
_robot_lock = threading.Lock()

# Current state for browser-based sim visualization
_state = {
    "pitch": 0, "roll": 0, "yaw": 0,
    "antennas": [0, 0],
    "body_yaw": 0,
    "expression": "neutral",
    "last_action": "",
    "last_action_time": 0,
}
_state_lock = threading.Lock()


def set_robot(robot):
    global _robot
    _robot = robot


def _update_state(**kwargs):
    with _state_lock:
        _state.update(kwargs)


@app.route("/api/health", methods=["GET"])
def health():
    with _robot_lock:
        connected = _robot is not None
        sim = _robot._sim_mode if _robot else False
    return jsonify({"status": "ok", "robot_connected": connected, "sim_mode": sim})


@app.route("/api/state", methods=["GET"])
def get_state():
    """Return current robot pose/expression for browser-based sim rendering."""
    with _state_lock:
        s = dict(_state)
    # Clear stale action text after 3 seconds
    if time.time() - s.get("last_action_time", 0) > 3:
        s["last_action"] = ""
    return jsonify(s)


@app.route("/api/pose", methods=["POST"])
def set_pose():
    if not _robot:
        return jsonify({"error": "Robot not connected"}), 503
    data = request.get_json(silent=True) or {}
    pitch = data.get("pitch", 0)
    roll = data.get("roll", 0)
    yaw = data.get("yaw", 0)
    antennas = data.get("antennas")
    body_yaw = data.get("body_yaw", 0)
    duration = data.get("duration", 0.4)

    # Always update browser sim state
    upd = {"pitch": pitch, "roll": roll, "yaw": yaw, "body_yaw": body_yaw}
    if antennas and len(antennas) == 2:
        upd["antennas"] = antennas
    _update_state(**upd)

    try:
        if _robot._sim_mode:
            return jsonify({"status": "ok", "sim": True})

        import math
        from reachy_mini.utils import create_head_pose
        head = create_head_pose(pitch=pitch, roll=roll, yaw=yaw, degrees=True)
        kwargs = {"head": head, "duration": duration}
        if antennas and len(antennas) == 2:
            kwargs["antennas"] = antennas
        if body_yaw != 0:
            kwargs["body_yaw"] = math.radians(body_yaw)
        _robot.mini.goto_target(**kwargs)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/expression", methods=["POST"])
def set_expression():
    if not _robot:
        return jsonify({"error": "Robot not connected"}), 503
    data = request.get_json(silent=True) or {}
    emotion = data.get("emotion", "neutral")
    duration = data.get("duration", 0.8)
    _update_state(expression=emotion)
    try:
        _robot.express(emotion, duration=duration)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/action", methods=["POST"])
def perform_action():
    if not _robot:
        return jsonify({"error": "Robot not connected"}), 503
    data = request.get_json(silent=True) or {}
    action = data.get("action", "")
    if not action:
        return jsonify({"error": "Action name required"}), 400
    _update_state(last_action=action, last_action_time=time.time())
    try:
        ok = _robot.perform(action)
        return jsonify({"status": "ok" if ok else "unknown_action"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reset", methods=["POST"])
def reset_pose():
    if not _robot:
        return jsonify({"error": "Robot not connected"}), 503
    _update_state(pitch=0, roll=0, yaw=0, antennas=[0, 0], body_yaw=0, expression="neutral")
    try:
        _robot.reset()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def start_server(robot=None, port=5557):
    if robot:
        set_robot(robot)
    t = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    t.start()
    print(f"[WEBAPP] Robot control API running on port {port}")
    return t


if __name__ == "__main__":
    from robot import Robot
    r = Robot()
    r.connect()
    set_robot(r)
    print("Robot Teleoperation API — http://localhost:5557")
    app.run(host="0.0.0.0", port=5557, debug=True)
