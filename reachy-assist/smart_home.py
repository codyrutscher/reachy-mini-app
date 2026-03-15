"""Smart home integration — connects Reachy to Home Assistant
or similar systems for voice-controlled home automation.

Supports: lights, thermostat, TV, blinds/curtains, and custom devices.
Uses Home Assistant REST API or falls back to simulated mode."""

import json
import os
import urllib.request

HA_URL = os.environ.get("HOME_ASSISTANT_URL", "")
HA_TOKEN = os.environ.get("HOME_ASSISTANT_TOKEN", "")

# Simulated device state when no HA connection
_sim_devices = {
    "lights": {"state": "off", "brightness": 100, "room": "bedroom"},
    "thermostat": {"state": "on", "temperature": 72, "mode": "auto"},
    "tv": {"state": "off", "channel": ""},
    "blinds": {"state": "closed"},
    "fan": {"state": "off", "speed": "medium"},
}


def _ha_request(endpoint, method="GET", data=None):
    """Make a request to Home Assistant API."""
    if not HA_URL or not HA_TOKEN:
        return None
    try:
        url = f"{HA_URL}/api/{endpoint}"
        headers = {
            "Authorization": f"Bearer {HA_TOKEN}",
            "Content-Type": "application/json",
        }
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[SMART_HOME] HA request failed: {e}")
        return None


def _is_connected():
    return bool(HA_URL and HA_TOKEN)


# ── Light control ───────────────────────────────────────────────────

def lights_on(room="bedroom", brightness=100):
    if _is_connected():
        _ha_request("services/light/turn_on", "POST", {
            "entity_id": f"light.{room}",
            "brightness_pct": brightness,
        })
    else:
        _sim_devices["lights"]["state"] = "on"
        _sim_devices["lights"]["brightness"] = brightness
    return f"Lights are on in the {room} at {brightness}% brightness."


def lights_off(room="bedroom"):
    if _is_connected():
        _ha_request("services/light/turn_off", "POST", {
            "entity_id": f"light.{room}",
        })
    else:
        _sim_devices["lights"]["state"] = "off"
    return f"Lights are off in the {room}."


def dim_lights(room="bedroom", level=30):
    return lights_on(room, level)


# ── Thermostat control ──────────────────────────────────────────────

def set_temperature(temp, unit="F"):
    if _is_connected():
        _ha_request("services/climate/set_temperature", "POST", {
            "entity_id": "climate.thermostat",
            "temperature": temp,
        })
    else:
        _sim_devices["thermostat"]["temperature"] = temp
    return f"Thermostat set to {temp}°{unit}."


def get_temperature():
    if _is_connected():
        state = _ha_request("states/climate.thermostat")
        if state:
            return f"The current temperature is {state.get('attributes', {}).get('current_temperature', 'unknown')}°."
    temp = _sim_devices["thermostat"]["temperature"]
    return f"The thermostat is set to {temp}°F."


# ── TV control ──────────────────────────────────────────────────────

def tv_on():
    if _is_connected():
        _ha_request("services/media_player/turn_on", "POST", {
            "entity_id": "media_player.tv",
        })
    else:
        _sim_devices["tv"]["state"] = "on"
    return "TV is on."


def tv_off():
    if _is_connected():
        _ha_request("services/media_player/turn_off", "POST", {
            "entity_id": "media_player.tv",
        })
    else:
        _sim_devices["tv"]["state"] = "off"
    return "TV is off."


# ── Blinds / curtains ──────────────────────────────────────────────

def open_blinds():
    if _is_connected():
        _ha_request("services/cover/open_cover", "POST", {
            "entity_id": "cover.blinds",
        })
    else:
        _sim_devices["blinds"]["state"] = "open"
    return "Blinds are open. Let the sunshine in!"


def close_blinds():
    if _is_connected():
        _ha_request("services/cover/close_cover", "POST", {
            "entity_id": "cover.blinds",
        })
    else:
        _sim_devices["blinds"]["state"] = "closed"
    return "Blinds are closed."


# ── Fan control ─────────────────────────────────────────────────────

def fan_on(speed="medium"):
    if _is_connected():
        _ha_request("services/fan/turn_on", "POST", {
            "entity_id": "fan.bedroom",
            "percentage": {"low": 33, "medium": 66, "high": 100}.get(speed, 66),
        })
    else:
        _sim_devices["fan"]["state"] = "on"
        _sim_devices["fan"]["speed"] = speed
    return f"Fan is on at {speed} speed."


def fan_off():
    if _is_connected():
        _ha_request("services/fan/turn_off", "POST", {"entity_id": "fan.bedroom"})
    else:
        _sim_devices["fan"]["state"] = "off"
    return "Fan is off."


# ── Scene presets ───────────────────────────────────────────────────

def set_scene(scene_name):
    """Activate a predefined scene."""
    scenes = {
        "bedtime": lambda: (dim_lights(level=10), close_blinds(), set_temperature(68)),
        "morning": lambda: (lights_on(brightness=80), open_blinds(), set_temperature(72)),
        "movie": lambda: (dim_lights(level=15), close_blinds(), tv_on()),
        "relax": lambda: (dim_lights(level=40), fan_on("low")),
        "bright": lambda: (lights_on(brightness=100), open_blinds()),
    }
    if scene_name in scenes:
        scenes[scene_name]()
        return f"Scene '{scene_name}' activated."
    available = ", ".join(scenes.keys())
    return f"I don't know that scene. Available scenes: {available}"


def get_device_status():
    """Get status of all devices."""
    if _is_connected():
        states = _ha_request("states")
        if states:
            return {s["entity_id"]: s["state"] for s in states[:20]}
    return _sim_devices.copy()


def parse_smart_home_command(text):
    """Parse natural language into smart home actions. Returns (response, handled)."""
    lower = text.lower()

    # Lights
    if any(w in lower for w in ["turn on the light", "lights on", "turn on light",
                                 "switch on the light", "light on"]):
        brightness = 100
        if "dim" in lower or "low" in lower:
            brightness = 30
        return lights_on(brightness=brightness), True

    if any(w in lower for w in ["turn off the light", "lights off", "turn off light",
                                 "switch off the light", "light off"]):
        return lights_off(), True

    if any(w in lower for w in ["dim the light", "dim light", "lower the light"]):
        return dim_lights(level=30), True

    if "brighten" in lower or "brighter" in lower:
        return lights_on(brightness=100), True

    # Thermostat
    if any(w in lower for w in ["what's the temperature", "how warm", "how cold",
                                 "temperature"]) and "set" not in lower:
        return get_temperature(), True

    if any(w in lower for w in ["set temperature", "set the temperature", "make it warmer",
                                 "make it cooler", "turn up the heat", "turn down the heat"]):
        import re
        nums = re.findall(r'\d+', text)
        if nums:
            temp = int(nums[0])
            if 50 <= temp <= 90:
                return set_temperature(temp), True
        if "warmer" in lower or "up" in lower:
            return set_temperature(75), True
        if "cooler" in lower or "down" in lower:
            return set_temperature(68), True
        return "What temperature would you like? Just say a number between 60 and 80.", True

    # TV
    if any(w in lower for w in ["turn on the tv", "tv on", "turn on tv",
                                 "switch on the tv", "put on the tv"]):
        return tv_on(), True
    if any(w in lower for w in ["turn off the tv", "tv off", "turn off tv",
                                 "switch off the tv"]):
        return tv_off(), True

    # Blinds
    if any(w in lower for w in ["open the blinds", "open blinds", "open the curtains",
                                 "open curtains", "let in the light"]):
        return open_blinds(), True
    if any(w in lower for w in ["close the blinds", "close blinds", "close the curtains",
                                 "close curtains"]):
        return close_blinds(), True

    # Fan
    if any(w in lower for w in ["turn on the fan", "fan on", "i'm hot"]):
        return fan_on(), True
    if any(w in lower for w in ["turn off the fan", "fan off"]):
        return fan_off(), True

    # Scenes
    if "bedtime scene" in lower or "bedtime mode" in lower:
        return set_scene("bedtime"), True
    if "morning scene" in lower or "morning mode" in lower:
        return set_scene("morning"), True
    if "movie mode" in lower or "movie scene" in lower:
        return set_scene("movie"), True
    if "relax mode" in lower or "relax scene" in lower:
        return set_scene("relax"), True

    return None, False
