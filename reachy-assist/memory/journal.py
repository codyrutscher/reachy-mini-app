"""Voice journaling — patient dictates entries, saved to dashboard."""

import json
import os
import urllib.request
from datetime import datetime

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:5555")

_journal_active = False
_current_entry = []


def _post(endpoint, data):
    try:
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            f"{DASHBOARD_URL}{endpoint}", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass


def start_journal() -> str:
    global _journal_active, _current_entry
    _journal_active = True
    _current_entry = []
    now = datetime.now().strftime("%A, %B %d")
    return (
        f"Journal entry for {now}. I'm listening — just talk and I'll write it all down. "
        "Say 'save journal' when you're done, or 'cancel journal' to discard."
    )


def add_to_journal(text: str) -> str:
    global _current_entry
    _current_entry.append(text)
    count = len(_current_entry)
    return f"Got it. ({count} lines so far.) Keep going, or say 'save journal' to finish."


def save_journal() -> str:
    global _journal_active, _current_entry
    if not _current_entry:
        _journal_active = False
        return "Nothing to save. Journal cancelled."
    entry = " ".join(_current_entry)
    now = datetime.now()
    _post("/api/activity", {
        "action": "journal_entry",
        "details": entry[:200],
    })
    # Also save as a conversation note
    _post("/api/conversation", {
        "speaker": "journal",
        "text": f"[Journal {now.strftime('%m/%d %I:%M%p')}] {entry}",
    })
    count = len(_current_entry)
    _journal_active = False
    _current_entry = []
    return f"Journal saved! {count} lines recorded. Your thoughts are safe with me."


def cancel_journal() -> str:
    global _journal_active, _current_entry
    _journal_active = False
    _current_entry = []
    return "Journal entry discarded. We can try again anytime."


def is_active() -> bool:
    return _journal_active
