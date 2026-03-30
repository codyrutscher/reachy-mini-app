"""Coding Assistant — Reachy generates code via voice and displays it on the dashboard.

Patient describes what they want to build, Reachy generates code using GPT,
explains it line by line, and pushes it to the dashboard Code Pad page.
"""

import json
import logging
import os
import time
import urllib.request

logger = logging.getLogger(__name__)

# Supported languages for code generation
LANGUAGES = [
    "python", "javascript", "html", "css", "sql", "bash",
    "java", "c", "cpp", "rust", "go", "ruby", "php",
    "typescript", "swift", "kotlin",
]


class CodingAssistant:
    """Voice-to-code assistant that generates and explains code."""

    def __init__(self, dashboard_url: str = "http://localhost:5555"):
        self._dashboard_url = dashboard_url
        self._current_code = ""
        self._current_language = "python"
        self._current_explanation = ""
        self._history = []  # list of {code, language, prompt, timestamp}
        self._explaining = False

    def generate_code(self, prompt: str, language: str = "") -> dict:
        """Generate code from a natural language description."""
        language = language.strip().lower() if language else self._current_language
        if language not in LANGUAGES:
            language = "python"
        self._current_language = language

        try:
            import openai
            client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": (
                        f"You are a helpful coding assistant. Generate clean, "
                        f"well-commented {language} code based on the user's request. "
                        f"Return ONLY the code, no markdown fences or explanations. "
                        f"Keep it concise and practical."
                    ),
                }, {
                    "role": "user",
                    "content": prompt,
                }],
                max_tokens=1000,
                temperature=0.3,
            )
            code = resp.choices[0].message.content.strip()
            # Strip markdown fences if GPT included them
            if code.startswith("```"):
                lines = code.split("\n")
                lines = lines[1:]  # remove opening fence
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                code = "\n".join(lines)

            self._current_code = code
            self._history.append({
                "code": code,
                "language": language,
                "prompt": prompt,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            })

            # Push to dashboard
            self._push_to_dashboard(code, language, prompt)

            logger.info("Generated %s code for: %s", language, prompt[:50])
            return {"code": code, "language": language, "prompt": prompt}

        except Exception as e:
            logger.error("Code generation failed: %s", e)
            return {"error": str(e), "code": "", "language": language}

    def explain_code(self, code: str = "") -> str:
        """Generate a line-by-line explanation of code."""
        code = code or self._current_code
        if not code:
            return "No code to explain. Generate some code first!"

        try:
            import openai
            client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": (
                        "You are a patient coding teacher explaining code to a beginner. "
                        "Explain the code line by line in simple, friendly language. "
                        "Use analogies when helpful. Keep each line explanation to 1-2 sentences."
                    ),
                }, {
                    "role": "user",
                    "content": f"Explain this code:\n\n{code}",
                }],
                max_tokens=800,
                temperature=0.5,
            )
            explanation = resp.choices[0].message.content.strip()
            self._current_explanation = explanation
            return explanation
        except Exception as e:
            logger.error("Code explanation failed: %s", e)
            return f"Sorry, I couldn't explain the code right now: {e}"

    def _push_to_dashboard(self, code: str, language: str, prompt: str):
        """Push generated code to the dashboard Code Pad page via API."""
        try:
            data = json.dumps({
                "code": code,
                "language": language,
                "prompt": prompt,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }).encode()
            req = urllib.request.Request(
                f"{self._dashboard_url}/api/code-pad",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.debug("Failed to push code to dashboard: %s", e)

    def set_language(self, language: str) -> str:
        """Set the default programming language."""
        language = language.strip().lower()
        if language in LANGUAGES:
            self._current_language = language
            return f"Language set to {language}"
        return f"Unknown language. Supported: {', '.join(LANGUAGES)}"

    def get_status(self) -> dict:
        return {
            "current_language": self._current_language,
            "has_code": bool(self._current_code),
            "history_count": len(self._history),
            "supported_languages": LANGUAGES,
        }

    def get_history(self) -> list[dict]:
        return list(reversed(self._history[-20:]))

    def get_current(self) -> dict:
        return {
            "code": self._current_code,
            "language": self._current_language,
            "explanation": self._current_explanation,
        }
