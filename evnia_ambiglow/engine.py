"""Drives the Ambiglow: takes colours from the active mode, eases them and
sends paced LampArray frames to the monitor.

Hardware facts this relies on (Evnia 27M2N8500 firmware):
- every HID report takes ~6 ms to be processed (8 LEDs per report);
- frames latched sooner than MinUpdateInterval (20 ms) after the previous
  one are dropped, so frames are paced to at most 50 fps;
- packets arriving right after a frame was latched are dropped as well, so
  frames carry at most 2 packets (16 LEDs, most-changed first).
"""
import ctypes
import logging
import math
import threading
import time

import numpy as np

from . import effects
from .colors import apply_black_level, hex_to_rgb
from .hidlamp import LampArray

log = logging.getLogger(__name__)

VID, PID = 0x0CF2, 0xB207
PACKET_S = 0.006
THRESHOLD = 3.0  # ignore changes smaller than this (sum of RGB deltas)
# Packets sent right after a frame was latched are dropped too, so a frame
# that needs 4 packets back to back loses LEDs. 2 packets (the 16 LEDs that
# changed most) per 20 ms frame stays clear of that and keeps 50 fps.
MAX_PACKETS = 2

MODES = {
    "screen": "Follow screen",
    "music": "Music",
    "static": "Static color",
    "effect": "Effect",
    "monitor": "Monitor default",
    "off": "Off",
}


def boost_priority():
    """Keep updating while a game saturates the machine: HIGH CPU priority
    class and HIGH GPU scheduling priority (no admin needed). REALTIME is
    avoided so the game itself isn't starved."""
    k32 = ctypes.WinDLL("kernel32")
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    proc = k32.GetCurrentProcess()
    k32.SetPriorityClass(proc, 0x80)  # HIGH_PRIORITY_CLASS
    gpu = ctypes.WinDLL("gdi32").D3DKMTSetProcessSchedulingPriorityClass
    gpu.argtypes = [ctypes.c_void_p, ctypes.c_int]
    gpu(proc, 4)  # D3DKMT_SCHEDULINGPRIORITYCLASS_HIGH


def set_thread_priority():
    k32 = ctypes.WinDLL("kernel32")
    k32.GetCurrentThread.restype = ctypes.c_void_p
    k32.SetThreadPriority.argtypes = [ctypes.c_void_p, ctypes.c_int]
    k32.SetThreadPriority(k32.GetCurrentThread(), 2)  # THREAD_PRIORITY_HIGHEST


def normalised_positions(positions):
    """Physical lamp (x, y) normalised to the extent of all lamps -> (n, 2)."""
    pos = np.array([(x, y) for x, y, _ in positions], dtype=float)
    lo, hi = pos.min(0), pos.max(0)
    return (pos - lo) / np.where(hi > lo, hi - lo, 1)


class Engine(threading.Thread):
    def __init__(self, settings):
        super().__init__(daemon=True, name="engine")
        self.settings = settings
        self.status = "Starting..."
        self._quit = threading.Event()
        self.dev = None
        self.uv = None
        self.screen = None
        self.audio = None
        self.audio_error = None
        self.screen_error = None  # display index whose capture failed

    def stop(self):
        self._quit.set()
        self.join(timeout=3)

    # --- device ----------------------------------------------------------
    def _connect(self):
        try:
            self.dev = LampArray.find(VID, PID)
            self.uv = normalised_positions(self.dev.lamp_positions())
            self.slots = self.dev.multi_slots()
            self.min_interval = self.dev.attributes()["min_update_interval_us"] / 1e6
        except (OSError, RuntimeError) as e:
            if self.dev:
                self.dev.close()
            self.dev = None
            self.status = "Looking for the Evnia monitor..."
            log.debug("connect failed: %s", e)
            return False
        n = len(self.uv)
        self.shown = np.zeros((n, 3))
        self.sent = np.full((n, 3), -1000.0)
        self.last_complete = 0.0
        self.autonomous = None
        log.info("connected: %d LEDs", n)
        return True

    def _disconnect(self):
        self._close_sources()
        if self.dev:
            try:
                self.dev.close()
            except OSError:
                pass
        self.dev = None

    def _set_autonomous(self, on):
        if self.autonomous != on:
            self.dev.set_autonomous(on)
            self.autonomous = on
            self.sent[:] = -1000.0  # resend everything after taking control

    # --- sources -----------------------------------------------------------
    def _close_sources(self):
        if self.screen:
            self.screen.close()
            self.screen = None
        if self.audio:
            self.audio.close()
            self.audio = None

    def _sync_sources(self, mode, s):
        want_screen = mode == "screen"
        if self.screen and (not want_screen or self.screen.output != s["output"]):
            self.screen.close()
            self.screen = None
        if want_screen and not self.screen and self.screen_error != s["output"]:
            try:
                from .screen import ScreenSource  # dxcam only loaded when needed
                self.screen = ScreenSource(int(s["output"]), self.uv, s["spread"])
                self.screen_error = None
            except Exception as e:  # noqa: BLE001 - e.g. no such display
                self.screen_error = s["output"]
                log.warning("screen capture of display %s failed: %s", s["output"], e)
        if not want_screen:
            self.screen_error = None
        if self.screen:
            self.screen.set_spread(s["spread"])

        want_audio = mode == "music"
        if self.audio and not want_audio:
            self.audio.close()
            self.audio = None
        if want_audio and not self.audio and not self.audio_error:
            try:
                from .audio import AudioSource
                self.audio = AudioSource()
            except Exception as e:  # noqa: BLE001 - no output device etc.
                self.audio_error = str(e)
                log.warning("music mode unavailable: %s", e)
        if not want_audio:
            self.audio_error = None

    def _mode_colors(self, mode, s, t, dt):
        """(colours, easing seconds) for the current mode, before brightness."""
        n = len(self.uv)
        color = hex_to_rgb(s["color"])
        if mode == "screen":
            if not self.screen:
                return np.zeros((n, 3)), 0.1
            return self.screen.colors(s["saturation"]), s["smoothing_ms"] / 1000
        if mode == "music":
            if not self.audio:
                return np.zeros((n, 3)), 0.1
            cols = self.audio.colors(self.uv, s["music_style"], s["music_sensitivity"], color, t, dt)
            return cols, 0.0
        if mode == "static":
            return np.tile(color, (n, 1)), 0.08
        if mode == "effect":
            return effects.render(s["effect"], self.uv, t, s["effect_speed"], color), 0.0
        return np.zeros((n, 3)), 0.05  # off

    # --- sending -----------------------------------------------------------
    def _send(self, out):
        """Send the LEDs that differ from what the monitor shows, paced so that
        UpdateComplete frames are at least MinUpdateInterval apart."""
        err = np.abs(out - self.sent).sum(1)
        # an LED that should be off but isn't always gets sent
        err[(out.max(1) == 0) & (self.sent.max(1) > 0)] = np.inf
        ranked = [i for i in np.argsort(-err) if err[i] > THRESHOLD]
        order = sorted(ranked[:MAX_PACKETS * self.slots])
        if not order:
            return False
        packets = -(-len(order) // self.slots)
        if time.perf_counter() + (packets - 1) * PACKET_S - self.last_complete < self.min_interval:
            return False
        rgb = np.clip(np.rint(out[order]), 0, 255).astype(int)
        self.dev.update([(int(i), tuple(int(c) for c in rgb[k])) for k, i in enumerate(order)])
        self.last_complete = time.perf_counter() - PACKET_S  # when the last packet started
        self.sent[order] = rgb
        return True

    # --- main loop ---------------------------------------------------------
    def run(self):
        boost_priority()
        set_thread_priority()
        try:
            while not self._quit.is_set():
                if not self.dev and not self._connect():
                    self._quit.wait(2)
                    continue
                try:
                    self._loop()
                except OSError as e:
                    log.warning("monitor lost: %s", e)
                    self.status = "Monitor disconnected, retrying..."
                    self._disconnect()
                    self._quit.wait(2)
        except Exception:
            log.exception("engine crashed")
            self.status = "Error, see log.txt"
            raise
        finally:
            self._close_sources()
            if self.dev:
                try:
                    self.dev.set_autonomous(True)  # hand the LEDs back to the monitor
                except OSError:
                    pass
                self.dev.close()

    def _loop(self):
        last = t_stat = time.perf_counter()
        t0 = last
        frames = 0
        while not self._quit.is_set():
            now = time.perf_counter()
            dt, last = now - last, now
            s = self.settings.snapshot()
            mode = s["mode"]
            self._sync_sources(mode, s)

            if mode == "monitor":
                self._set_autonomous(True)
                self.status = "Monitor's own Ambiglow"
                self._quit.wait(0.1)
                last = time.perf_counter()
                continue
            self._set_autonomous(False)

            target, tau = self._mode_colors(mode, s, now - t0, dt)
            target = target * s["brightness"]
            if tau <= 0:
                self.shown = target
            else:
                self.shown = self.shown + (target - self.shown) * (1 - math.exp(-dt / tau))
            out = self.shown
            if mode == "screen":
                out = apply_black_level(out, s["black_level"])

            if self._send(out):
                frames += 1
            else:
                time.sleep(0.001)

            if now - t_stat >= 1:
                fps = frames / (now - t_stat)
                frames, t_stat = 0, now
                if mode == "screen" and self.screen_error is not None:
                    self.status = f"Can't capture display {self.screen_error}"
                elif mode == "music" and self.audio_error:
                    self.status = "Music: no audio output found"
                elif mode == "music" and self.audio:
                    self.status = f"Music ({self.audio.name}) - {fps:.0f} fps"
                elif fps < 1 and mode in ("screen", "static", "off"):
                    self.status = f"{MODES[mode]} - active (nothing changing)"
                else:
                    self.status = f"{MODES[mode]} - {fps:.0f} fps"
