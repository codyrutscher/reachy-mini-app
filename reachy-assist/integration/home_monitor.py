"""Home Monitor — Reachy monitors the room and alerts caregivers to unusual situations.

Periodically captures frames and uses GPT-4o vision to detect:
- Patient not in expected location
- Unusual postures (on the floor, slumped)
- Environmental hazards (spills, obstacles)
- Extended inactivity
"""

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)


class HomeMonitor:
    """Periodic room monitoring with vision-based anomaly detection."""

    def __init__(self, dashboard_url: str = "http://localhost:5555"):
        self._dashboard_url = dashboard_url
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
        self._check_interval = 300  # seconds between checks (5 min)
        self._alert_cooldown = 600  # don't re-alert same issue for 10 min
        self._last_alerts = {}  # type -> timestamp
        self._total_checks = 0
        self._alerts_sent = 0

    def start(self, interval: int = 300) -> str:
        if self._running:
            return "Home monitor already running."
        self._check_interval = max(60, interval)
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Home monitor started, checking every %ds", self._check_interval)
        return f"Home monitoring active — checking every {self._check_interval // 60} minutes."

    def stop(self) -> str:
        if not self._running:
            return "Home monitor is not running."
        self._stop_event.set()
        self._running = False
        return f"Home monitoring stopped. Ran {self._total_checks} checks, sent {self._alerts_sent} alerts."

    def check_now(self) -> str:
        """Run an immediate check."""
        return self._analyze_room()

    def _monitor_loop(self):
        try:
            while not self._stop_event.is_set():
                self._analyze_room()
                self._stop_event.wait(self._check_interval)
        except Exception as e:
            logger.error("Monitor loop error: %s", e)
        finally:
            self._running = False

    def _analyze_room(self) -> str:
        """Capture frame and analyze for safety concerns."""
        self._total_checks += 1

        try:
            from perception.vision import capture_frame
            frame_b64 = capture_frame()
            if not frame_b64:
                return "Camera not available."
        except Exception:
            return "Camera not available."

        try:
            import json
            import urllib.request

            api_key = os.environ.get("OPENAI_API_KEY", "")
            body = json.dumps({
                "model": "gpt-4o",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": (
                            "You are a home safety monitor for an elderly person. "
                            "Analyze this room image for safety concerns. Check for:\n"
                            "1. Is a person visible? What are they doing?\n"
                            "2. Any fall risk? (person on floor, unsteady posture)\n"
                            "3. Environmental hazards? (spills, obstacles, open flames)\n"
                            "4. Anything unusual or concerning?\n\n"
                            "Respond in JSON format:\n"
                            '{"person_visible": true/false, "activity": "description", '
                            '"concerns": ["list of concerns or empty"], '
                            '"severity": "none/low/medium/high", '
                            '"summary": "one sentence summary"}'
                        )},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{frame_b64}",
                            "detail": "low",
                        }},
                    ],
                }],
                "max_tokens": 300,
            }).encode()

            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp = urllib.request.urlopen(req, timeout=15)
            result = json.loads(resp.read().decode())
            text = result["choices"][0]["message"]["content"].strip()

            # Parse JSON response
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:-1])
            analysis = json.loads(text)

            severity = analysis.get("severity", "none")
            concerns = analysis.get("concerns", [])
            summary = analysis.get("summary", "")

            if severity in ("medium", "high") and concerns:
                self._send_alert(severity, summary, concerns)

            logger.info("Room check #%d: %s", self._total_checks, summary)
            return summary

        except Exception as e:
            logger.error("Room analysis failed: %s", e)
            return f"Analysis failed: {e}"

    def _send_alert(self, severity: str, summary: str, concerns: list):
        """Send alert to dashboard."""
        now = time.time()
        alert_key = summary[:50]
        if alert_key in self._last_alerts and now - self._last_alerts[alert_key] < self._alert_cooldown:
            return
        self._last_alerts[alert_key] = now
        self._alerts_sent += 1

        try:
            import json
            import urllib.request
            data = json.dumps({
                "type": "HOME_MONITOR",
                "message": f"[{severity.upper()}] {summary}",
                "severity": severity,
            }).encode()
            req = urllib.request.Request(
                f"{self._dashboard_url}/api/alerts",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
            logger.warning("Home monitor alert: %s", summary)
        except Exception as e:
            logger.error("Failed to send monitor alert: %s", e)

    @property
    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "interval_seconds": self._check_interval,
            "total_checks": self._total_checks,
            "alerts_sent": self._alerts_sent,
        }
