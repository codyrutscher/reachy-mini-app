"""Lightweight Flask API for receiving teleoperation commands from the dashboard.
Started automatically by the interaction loop or can run standalone."""

import threading
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from core.log_config import get_logger

from typing import Any, Optional

logger = get_logger("webapp")

app = Flask(__name__)
CORS(app)

# ── Request logging middleware ──────────────────────────────────────

import uuid as _uuid

_req_logger = get_logger("webapp.request")

@app.before_request
def _log_request_start():
    request._start_time = time.time()
    request._request_id = _uuid.uuid4().hex[:8]

@app.after_request
def _log_request_end(response):
    global _request_count, _error_count
    _request_count += 1
    if response.status_code >= 400:
        _error_count += 1
    duration_ms = round((time.time() - getattr(request, "_start_time", time.time())) * 1000, 1)
    _req_logger.info(
        "%s %s %s %sms",
        request.method, request.path, response.status_code, duration_ms,
        extra={
            "request_id": getattr(request, "_request_id", ""),
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "ip": request.remote_addr,
        },
    )
    response.headers["X-Request-Id"] = getattr(request, "_request_id", "")
    return response

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


def set_robot(robot: Any) -> None:
    global _robot
    _robot = robot


def _update_state(**kwargs: Any) -> None:
    with _state_lock:
        _state.update(kwargs)


_webapp_start_time: float = time.time()
_request_count: int = 0
_error_count: int = 0

@app.route("/api/health", methods=["GET"])
def health():
    with _robot_lock:
        connected = _robot is not None
        sim = _robot._sim_mode if _robot else False
    uptime_s = round(time.time() - _webapp_start_time)
    return jsonify({
        "status": "ok",
        "robot_connected": connected,
        "sim_mode": sim,
        "uptime_seconds": uptime_s,
        "requests_served": _request_count,
        "errors": _error_count,
    })


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
        logger.info("Expression: %s (duration=%.1f)", emotion, duration)
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
        logger.info("Action: %s → %s", action, "ok" if ok else "unknown")
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
        logger.info("Pose reset to neutral")
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Radio DJ endpoints ───────────────────────────────────────────

_radio_dj = None

def set_radio(dj):
    global _radio_dj
    _radio_dj = dj

@app.route("/api/radio/status", methods=["GET"])
def radio_status():
    if not _radio_dj:
        return jsonify({"on_air": False, "error": "Radio not initialized"}), 200
    return jsonify(_radio_dj.get_status())

@app.route("/api/radio/start", methods=["POST"])
def radio_start():
    if not _radio_dj:
        return jsonify({"error": "Radio not initialized"}), 503
    msg = _radio_dj.start()
    return jsonify({"status": "ok", "message": msg})

@app.route("/api/radio/stop", methods=["POST"])
def radio_stop():
    if not _radio_dj:
        return jsonify({"error": "Radio not initialized"}), 503
    msg = _radio_dj.stop()
    return jsonify({"status": "ok", "message": msg})

@app.route("/api/radio/skip", methods=["POST"])
def radio_skip():
    if not _radio_dj:
        return jsonify({"error": "Radio not initialized"}), 503
    msg = _radio_dj.skip()
    return jsonify({"status": "ok", "message": msg})

@app.route("/api/radio/request", methods=["POST"])
def radio_request():
    if not _radio_dj:
        return jsonify({"error": "Radio not initialized"}), 503
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "text required"}), 400
    msg = _radio_dj.request(text)
    return jsonify({"status": "ok", "message": msg})

@app.route("/api/radio/mood", methods=["POST"])
def radio_mood():
    if not _radio_dj:
        return jsonify({"error": "Radio not initialized"}), 503
    data = request.get_json(silent=True) or {}
    mood = data.get("mood", "neutral")
    _radio_dj.set_mood(mood)
    return jsonify({"status": "ok", "mood": mood})


# ── Voice Clone endpoints ────────────────────────────────────────

_voice_manager = None

def set_voice_manager(vm):
    global _voice_manager
    _voice_manager = vm

@app.route("/api/voice/status", methods=["GET"])
def voice_status():
    if not _voice_manager:
        return jsonify({"available": False, "profiles": []})
    return jsonify(_voice_manager.get_status())

@app.route("/api/voice/profiles", methods=["GET"])
def voice_list():
    if not _voice_manager:
        return jsonify([])
    return jsonify(_voice_manager.list_voices())

@app.route("/api/voice/create", methods=["POST"])
def voice_create():
    if not _voice_manager:
        return jsonify({"error": "Voice manager not initialized"}), 503
    # Expect multipart form: name, description, sample (file)
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "")
    if not name:
        return jsonify({"error": "name is required"}), 400
    sample = request.files.get("sample")
    if not sample:
        return jsonify({"error": "sample audio file is required"}), 400
    # Save uploaded file temporarily
    import tempfile
    ext = os.path.splitext(sample.filename or "")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        sample.save(tmp)
        tmp_path = tmp.name
    result = _voice_manager.create_voice(name, tmp_path, description)
    # Clean up temp file (voice_clone copies it)
    try:
        os.unlink(tmp_path)
    except Exception:
        pass
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)

@app.route("/api/voice/delete", methods=["POST"])
def voice_delete():
    if not _voice_manager:
        return jsonify({"error": "Voice manager not initialized"}), 503
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")
    if not name:
        return jsonify({"error": "name is required"}), 400
    result = _voice_manager.delete_voice(name)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)

@app.route("/api/voice/activate", methods=["POST"])
def voice_activate():
    if not _voice_manager:
        return jsonify({"error": "Voice manager not initialized"}), 503
    data = request.get_json(silent=True) or {}
    name = data.get("name")  # None = reset to default
    ok = _voice_manager.set_active_voice(name)
    if not ok:
        return jsonify({"error": f"Voice '{name}' not found"}), 404
    return jsonify({"status": "ok", "active_voice": name})

@app.route("/api/voice/preview", methods=["POST"])
def voice_preview():
    if not _voice_manager:
        return jsonify({"error": "Voice manager not initialized"}), 503
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")
    if not name:
        return jsonify({"error": "name is required"}), 400
    path = _voice_manager.preview_voice(name)
    if not path:
        return jsonify({"error": "Preview generation failed"}), 500
    from flask import send_file
    return send_file(path, mimetype="audio/mpeg", as_attachment=False)


# ── Personality endpoints ─────────────────────────────────────────
_personality_mgr = None


def set_personality_manager(pm):
    global _personality_mgr
    _personality_mgr = pm


@app.route("/api/personalities", methods=["GET"])
def personality_list():
    if not _personality_mgr:
        return jsonify({"error": "Personality manager not available"}), 503
    return jsonify(_personality_mgr.list_profiles())


@app.route("/api/personalities/activate", methods=["POST"])
def personality_activate():
    if not _personality_mgr:
        return jsonify({"error": "Personality manager not available"}), 503
    data = request.get_json(force=True)
    pid = data.get("id", "")
    msg = _personality_mgr.activate(pid)
    return jsonify({"message": msg, "active": pid})


# ── Freestyle rapper endpoints ────────────────────────────────────
_freestyle_rapper = None


def set_freestyle_rapper(fr):
    global _freestyle_rapper
    _freestyle_rapper = fr


@app.route("/api/freestyle/status", methods=["GET"])
def freestyle_status():
    if not _freestyle_rapper:
        return jsonify({"error": "Freestyle rapper not available"}), 503
    return jsonify(_freestyle_rapper.get_status())


@app.route("/api/freestyle/perform", methods=["POST"])
def freestyle_perform():
    if not _freestyle_rapper:
        return jsonify({"error": "Freestyle rapper not available"}), 503
    data = request.get_json(force=True)
    topic = data.get("topic", "")
    rap = _freestyle_rapper.perform(topic)
    return jsonify({"rap": rap})


@app.route("/api/freestyle/stop", methods=["POST"])
def freestyle_stop():
    if not _freestyle_rapper:
        return jsonify({"error": "Freestyle rapper not available"}), 503
    msg = _freestyle_rapper.stop()
    return jsonify({"message": msg})


# ── Coding assistant endpoints ────────────────────────────────────
_coding_assistant = None


def set_coding_assistant(ca):
    global _coding_assistant
    _coding_assistant = ca


@app.route("/api/code/generate", methods=["POST"])
def code_generate():
    if not _coding_assistant:
        return jsonify({"error": "Coding assistant not available"}), 503
    data = request.get_json(force=True)
    prompt = data.get("prompt", "")
    language = data.get("language", "")
    result = _coding_assistant.generate_code(prompt, language)
    return jsonify(result)


@app.route("/api/code/explain", methods=["POST"])
def code_explain():
    if not _coding_assistant:
        return jsonify({"error": "Coding assistant not available"}), 503
    data = request.get_json(force=True)
    code = data.get("code", "")
    explanation = _coding_assistant.explain_code(code)
    return jsonify({"explanation": explanation})


@app.route("/api/code/history", methods=["GET"])
def code_history():
    if not _coding_assistant:
        return jsonify([])
    return jsonify(_coding_assistant.get_history())


def start_server(robot: Any = None, port: int = 5557) -> threading.Thread:
    if robot:
        set_robot(robot)
    t = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    t.start()
    logger.info("Robot control API running on port %d", port)
    return t


if __name__ == "__main__":
    from robot.robot import Robot
    r = Robot()
    r.connect()
    set_robot(r)
    logger.info("Robot Teleoperation API — http://localhost:5557")
    app.run(host="0.0.0.0", port=5557, debug=True)
