"""Small vectorised colour helpers."""
import numpy as np


def hsv_to_rgb(h, s, v):
    """h, s, v: arrays (or scalars) in 0..1 -> (..., 3) float array in 0..255."""
    h, s, v = np.broadcast_arrays(np.asarray(h, float) % 1.0, np.asarray(s, float), np.asarray(v, float))
    i = np.floor(h * 6).astype(int) % 6
    f = h * 6 - np.floor(h * 6)
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    choices = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)]
    out = np.zeros(h.shape + (3,))
    for k, (r, g, b) in enumerate(choices):
        m = i == k
        out[m] = np.stack([r[m], g[m], b[m]], -1)
    return out * 255.0


def hex_to_rgb(value):
    value = value.lstrip("#")
    return np.array([int(value[i:i + 2], 16) for i in (0, 2, 4)], float)


def apply_black_level(cols, level):
    """Colours whose brightest channel is at or below `level` become exactly
    off; above it, brightness is rescaled so it still fades smoothly to off
    (hue is kept)."""
    if level <= 0:
        return cols
    peak = cols.max(1, keepdims=True)
    scaled = np.clip(peak - level, 0, None) * 255.0 / (255.0 - level)
    return cols * (scaled / np.maximum(peak, 1e-6))
