"""Persistent user settings (%USERPROFILE%\\.evnia-ambiglow\\settings.json)."""
import json
import os
import threading
from pathlib import Path

DEFAULTS = {
    "mode": "screen",          # screen | music | static | effect | monitor | off
    "brightness": 1.0,         # 0..1, all modes
    "saturation": 1.25,        # screen mode
    "smoothing_ms": 20.0,      # screen mode easing time constant
    "black_level": 10.0,       # screen mode: at or below this the LEDs go off
    "spread": 0.12,            # screen mode: sampling area per LED
    "output": 0,               # screen mode: display index
    "color": "#ff6a00",        # static colour, also used by some effects / music style
    "effect": "rainbow",       # rainbow | breathing | cycle | wave
    "effect_speed": 1.0,
    "music_style": "spectrum", # spectrum | pulse | color
    "music_sensitivity": 1.0,
}


def app_dir():
    # not %APPDATA%: the Microsoft Store Python silently redirects writes there
    # into its own package folder, where users would never find log.txt
    d = Path.home() / ".evnia-ambiglow"
    d.mkdir(parents=True, exist_ok=True)
    return d


class Settings:
    """Thread-safe settings shared by the UI (writer) and the engine (reader)."""

    def __init__(self, path=None):
        self.path = Path(path) if path else app_dir() / "settings.json"
        self._lock = threading.Lock()
        self._data = dict(DEFAULTS)
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
            self._data.update({k: v for k, v in stored.items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass

    def snapshot(self):
        with self._lock:
            return dict(self._data)

    def get(self, key):
        with self._lock:
            return self._data[key]

    def set(self, key, value):
        with self._lock:
            self._data[key] = value

    def save(self):
        data = self.snapshot()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
