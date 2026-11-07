"""Finds how fast the Ambiglow LEDs really change: blinks red/blue at rising
rates (no screen capture involved) with the rate shown fullscreen."""
import time
import tkinter as tk

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evnia_ambiglow.hidlamp import LampArray

dev = LampArray.find(0x0CF2, 0xB207)
n = dev.attributes()["lamp_count"]

root = tk.Tk()
root.attributes("-fullscreen", True)
root.attributes("-topmost", True)
root.configure(bg="black", cursor="none")
label = tk.Label(root, fg="white", bg="black", font=("Segoe UI", 54, "bold"), justify="center")
label.pack(expand=True)

try:
    dev.set_autonomous(False)
    for hz in (2, 5, 10, 20):
        label.configure(text=f"LEDs blinking red/blue\n{hz}x per second")
        root.update()
        half = 0.5 / hz
        end = time.perf_counter() + 5
        k = 0
        while time.perf_counter() < end:
            t = time.perf_counter()
            dev.set_colors([(255, 0, 0) if k % 2 == 0 else (0, 0, 255)] * n)
            k += 1
            root.update()
            while time.perf_counter() - t < half:
                time.sleep(0.001)
        dev.set_colors([(0, 0, 0)] * n)
        label.configure(text="(pause)")
        root.update()
        time.sleep(1.2)
finally:
    dev.set_autonomous(True)
    dev.close()
    root.destroy()
print("done")
