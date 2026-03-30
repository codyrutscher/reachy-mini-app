"""Weather module — fetches current weather from wttr.in (no API key needed)."""

import json
import urllib.request


def get_weather(city: str = "auto") -> dict:
    """Fetch current weather. Use city='auto' for IP-based location."""
    try:
        url = f"https://wttr.in/{city}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "reachy-assist/1.0"})
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read().decode("utf-8"))
        current = data.get("current_condition", [{}])[0]
        area = data.get("nearest_area", [{}])[0]
        location = area.get("areaName", [{}])[0].get("value", city)
        return {
            "location": location,
            "temp_c": current.get("temp_C", "?"),
            "temp_f": current.get("temp_F", "?"),
            "feels_like_c": current.get("FeelsLikeC", "?"),
            "feels_like_f": current.get("FeelsLikeF", "?"),
            "description": current.get("weatherDesc", [{}])[0].get("value", "Unknown"),
            "humidity": current.get("humidity", "?"),
            "wind_mph": current.get("windspeedMiles", "?"),
            "ok": True,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def weather_briefing(city: str = "auto") -> str:
    """Return a spoken weather briefing string."""
    w = get_weather(city)
    if not w["ok"]:
        return "I couldn't get the weather right now. Maybe check again later."
    return (
        f"The weather in {w['location']} is currently {w['description'].lower()}, "
        f"{w['temp_f']} degrees Fahrenheit, feels like {w['feels_like_f']}. "
        f"Humidity is {w['humidity']} percent."
    )

def weather_advice(city: str = "auto") -> str:
    """Return weather-based advice for the patient."""
    w = get_weather(city)
    if not w["ok"]:
        return "I can't check the weather right now."
    temp = int(w["temp_f"])
    if temp < 40:
        return f"It's {temp}°F in {w['location']} -- bundle up with a warm coat!"
    elif temp < 60:
        return f"It's {temp}°F in {w['location']} -- a jacket or sweater should do."
    elif temp < 80:
        return f"It's {temp}°F in {w['location']} -- nice weather out there!"
    else:
        return f"It's {temp}°F in {w['location']} -- stay hydrated and keep cool!"
