"""⏲ Timers and stopwatches (shoji-timer): one JSON file each in $XDG_RUNTIME_DIR/shoji-timers.
No GTK here, so the shoji-timer command and the tests use it as it is.

  {"id", "label", "kind": "timer" | "stopwatch", "start": epoch of the last (re)start,
   "spent": seconds run before that start, "paused": epoch or null, "seconds": a timer's length}
"""
import json
import os
import re
import time
import uuid
from pathlib import Path

DIR = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "shoji-timers"


def parse_duration(text):
    """'10m' '90s' '1h30m' '1:30' (m:ss) '25' (minutes) -> seconds, or None."""
    t = text.strip().lower()
    if re.fullmatch(r"\d+", t):
        return int(t) * 60 or None
    m = re.fullmatch(r"(\d+):(\d{1,2})", t)
    if m:
        return int(m[1]) * 60 + int(m[2]) or None
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m(?:in)?)?(?:(\d+)s)?", t)
    if m and any(m.groups()):
        return int(m[1] or 0) * 3600 + int(m[2] or 0) * 60 + int(m[3] or 0) or None
    return None


def ran(t, now):
    """Seconds it has run, pauses left out."""
    return t.get("spent", 0) + (0 if t.get("paused") else max(0.0, now - t["start"]))


def left(t, now):
    return t["seconds"] - ran(t, now)


def fmt(seconds):
    """9:58 · 1:02:03 (whole seconds, rounded up for a countdown by the caller)."""
    s = max(0, int(seconds))
    h, m, s = s // 3600, s % 3600 // 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def load(now=None):
    """Every timer, the one ending first first, then the stopwatches, oldest first."""
    now = now or time.time()
    out = []
    for f in DIR.glob("*.json") if DIR.is_dir() else []:
        try:
            t = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(t, dict) and t.get("kind") in ("timer", "stopwatch") and "start" in t:
            out.append(t)
    return sorted(out, key=lambda t: (t["kind"] != "timer", left(t, now) if t["kind"] == "timer" else t["start"]))


def save(t):
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = DIR / f".{t['id']}.tmp"
    tmp.write_text(json.dumps(t))
    tmp.replace(DIR / f"{t['id']}.json")


def remove(tid):
    (DIR / f"{tid}.json").unlink(missing_ok=True)


def new(kind, seconds=None, label="", now=None):
    t = {"id": uuid.uuid4().hex[:6], "label": label.strip(), "kind": kind, "start": now or time.time(),
         "spent": 0, "paused": None}
    if kind == "timer":
        t["seconds"] = seconds
    save(t)
    return t


def pause(t, now=None):
    now = now or time.time()
    if not t.get("paused"):
        t["spent"], t["paused"] = ran(t, now), now
        save(t)


def resume(t, now=None):
    if t.get("paused"):
        t["start"], t["paused"] = now or time.time(), None
        save(t)
