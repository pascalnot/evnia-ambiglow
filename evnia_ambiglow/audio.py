"""Music-reactive source: captures whatever the PC is playing (WASAPI
loopback of the default output device) and turns it into LED colours."""
import logging
import math
import threading
import time

import numpy as np
import pyaudiowpatch as pa

from .colors import hsv_to_rgb

log = logging.getLogger(__name__)

STYLES = {
    "spectrum": "Spectrum",
    "pulse": "Pulse",
    "color": "Pulse (static color)",
}

BANDS = 10
FFT = 2048
PEAK_FLOOR = 2.0    # keeps quiet noise from being auto-gained into light
RELEASE_S = 0.12    # how fast levels fall back after a hit
GAIN_DECAY_S = 4.0  # auto-gain memory


class AudioSource:
    def __init__(self):
        self.p = pa.PyAudio()
        dev = self.p.get_default_wasapi_loopback()
        self.name = dev["name"]
        self.rate = int(dev["defaultSampleRate"])
        self.channels = dev["maxInputChannels"]
        self.buf = np.zeros(FFT, np.float32)
        self.lock = threading.Lock()
        self.last_data = 0.0
        self.levels = np.zeros(BANDS)
        self.peaks = np.full(BANDS, PEAK_FLOOR)
        edges = np.geomspace(40, min(12000, self.rate / 2 - 1), BANDS + 1)
        freqs = np.fft.rfftfreq(FFT, 1 / self.rate)
        self.masks = [(freqs >= lo) & (freqs < hi) for lo, hi in zip(edges[:-1], edges[1:])]
        self.window = np.hanning(FFT).astype(np.float32)
        # callback mode: WASAPI loopback delivers nothing while the PC is silent,
        # so a blocking read would hang
        self.stream = self.p.open(format=pa.paFloat32, channels=self.channels, rate=self.rate,
                                  input=True, input_device_index=dev["index"],
                                  frames_per_buffer=self.rate // 100, stream_callback=self._cb)
        log.info("music source: %s, %d Hz", self.name, self.rate)

    def _cb(self, in_data, frame_count, time_info, status):
        mono = np.frombuffer(in_data, np.float32).reshape(-1, self.channels).mean(1)
        with self.lock:
            n = min(len(mono), FFT)
            self.buf = np.roll(self.buf, -n)
            self.buf[-n:] = mono[-n:]
        self.last_data = time.perf_counter()
        return (None, pa.paContinue)

    def _analyse(self, dt, sensitivity):
        if time.perf_counter() - self.last_data > 0.15:
            mags = np.zeros(BANDS)  # nothing playing
        else:
            with self.lock:
                x = self.buf * self.window
            spec = np.abs(np.fft.rfft(x))
            mags = np.array([math.sqrt(float(np.mean(spec[m] ** 2))) if m.any() else 0.0
                             for m in self.masks])
        self.peaks = np.maximum(np.maximum(self.peaks * math.exp(-dt / GAIN_DECAY_S), mags), PEAK_FLOOR)
        lvl = np.clip(mags / self.peaks * sensitivity, 0, 1) ** 1.5
        self.levels = np.maximum(lvl, self.levels * math.exp(-dt / RELEASE_S))
        return self.levels

    def colors(self, uv, style, sensitivity, color, t, dt):
        lv = self._analyse(dt, sensitivity)
        n = len(uv)
        if style == "spectrum":
            # bass in the middle, treble towards the sides
            d = np.clip(np.abs(uv[:, 0] - 0.5) * 2, 0, 1)
            level = np.interp(d * (BANDS - 1), np.arange(BANDS), lv)
            return hsv_to_rgb(d * 0.75 + t * 0.02, 1.0, level)
        bass = float(lv[:3].max())
        if style == "color":
            return np.tile(color * bass, (n, 1))
        return np.tile(hsv_to_rgb(t * 0.05, 1.0, bass), (n, 1))

    def close(self):
        try:
            self.stream.stop_stream()
            self.stream.close()
        finally:
            self.p.terminate()
