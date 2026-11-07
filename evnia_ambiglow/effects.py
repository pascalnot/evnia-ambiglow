"""Built-in animations. Each returns (lamps, 3) colours in 0..255.

uv: (lamps, 2) LED positions normalised to 0..1 (x left->right, y top->bottom).
"""
import math

import numpy as np

from .colors import hsv_to_rgb

EFFECTS = {
    "rainbow": "Rainbow",
    "breathing": "Breathing",
    "cycle": "Color cycle",
    "wave": "Wave",
}


def render(name, uv, t, speed, color):
    n = len(uv)
    if name == "breathing":
        level = 0.5 - 0.5 * math.cos(2 * math.pi * t * 0.25 * speed)
        return np.tile(color * level, (n, 1))
    if name == "cycle":
        return np.tile(hsv_to_rgb(t * 0.05 * speed, 1.0, 1.0), (n, 1))
    if name == "wave":
        level = 0.5 + 0.5 * np.sin(2 * math.pi * (uv[:, 0] * 1.5 - t * 0.5 * speed))
        return color[None, :] * level[:, None]
    # rainbow
    return hsv_to_rgb(uv[:, 0] * 0.8 + uv[:, 1] * 0.2 + t * 0.15 * speed, 1.0, 1.0)
