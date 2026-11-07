"""Screen-following source: DXGI desktop capture (dxcam) and per-LED
Gaussian-weighted sampling, so moving content glides between LEDs."""
import logging
import math
import threading

import numpy as np

log = logging.getLogger(__name__)

STEP = 8           # pixel stride when sampling
CAPTURE_FPS = 50   # matches the LEDs' 50 fps; more only adds GPU load in games

# dxcam cameras wrap COM objects that crash the process if they are released
# from another thread, so each one is created once and kept for the lifetime
# of the process; sources only start and stop it, from their own thread.
_cameras = {}


def _camera(output):
    import dxcam
    if output not in _cameras:
        # native BGRA: no full-frame colour conversion, we only touch sampled pixels
        _cameras[output] = dxcam.create(output_idx=output, output_color="BGRA")
    return _cameras[output]


def build_weights(uv, h, w, spread):
    """(lamps, h*w) float32 weights: a Gaussian around each LED's position,
    sigma = spread * screen size."""
    ys = (np.arange(h) + 0.5) / h
    xs = (np.arange(w) + 0.5) / w
    weights = np.empty((len(uv), h * w), dtype=np.float32)
    for i, (u, v) in enumerate(uv):
        g = np.outer(np.exp(-0.5 * ((ys - v) / spread) ** 2),
                     np.exp(-0.5 * ((xs - u) / spread) ** 2)).ravel()
        weights[i] = g / g.sum()
    return weights


class ScreenSource:
    def __init__(self, output, uv, spread):
        self.output, self.uv, self.spread = output, uv, spread
        self.lock = threading.Lock()
        self.target = np.zeros((len(uv), 3))
        self.weights = None
        self._quit = threading.Event()
        self._ready = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self._run, daemon=True, name="screen")
        self.thread.start()
        self._ready.wait(5)
        if self.error:
            raise self.error

    def set_spread(self, spread):
        if spread != self.spread and self.weights is not None:
            self.spread = spread
            self.weights = build_weights(self.uv, *self.shape, spread)

    def _run(self):
        try:
            cam = _camera(self.output)
            cam.start(target_fps=CAPTURE_FPS, video_mode=True)
        except Exception as e:  # noqa: BLE001 - e.g. no such display
            self.error = e
            self._ready.set()
            return
        try:
            self.shape = (math.ceil(cam.height / STEP), math.ceil(cam.width / STEP))
            self.weights = build_weights(self.uv, *self.shape, self.spread)
            self._ready.set()
            while not self._quit.is_set():
                frame = cam.get_latest_frame()  # video_mode: returns at least every 20 ms
                if frame is None:
                    continue
                px = frame[::STEP, ::STEP, 2::-1].reshape(-1, 3).astype(np.float32)
                cols = (self.weights @ px).astype(np.float64)
                with self.lock:
                    self.target = cols
        except Exception:
            log.exception("screen capture failed")
        finally:
            cam.stop()

    def colors(self, saturation):
        with self.lock:
            cols = self.target
        if saturation != 1:
            grey = cols.mean(1, keepdims=True)
            cols = grey + (cols - grey) * saturation
        return np.clip(cols, 0, 255)

    def close(self):
        self._quit.set()
        self.thread.join(timeout=2)
