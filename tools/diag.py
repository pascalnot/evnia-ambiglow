"""Visual diagnostic: a fullscreen window says what the LEDs should show while
each HID command path is exercised. Watch the monitor's Ambiglow."""
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
label = tk.Label(root, fg="white", bg="black", font=("Segoe UI", 44, "bold"), justify="center")
label.pack(expand=True)


def stage(num, text, action, secs=5):
    label.configure(text=f"Step {num} of 6\n\n{text}")
    root.update()
    action()
    end = time.time() + secs
    while time.time() < end:
        root.update()
        time.sleep(0.05)


try:
    stage(1, "Ambiglow should now be RED\n(autonomous off + multi-update)",
          lambda: (dev.set_autonomous(False), dev.set_colors([(255, 0, 0)] * n)))
    stage(2, "Ambiglow should now be GREEN\n(range update)",
          lambda: dev.set_range(0, n - 1, (0, 255, 0)))
    stage(3, "Ambiglow should now be BLUE\n(multi-update, re-sent continuously)",
          lambda: None, secs=0)
    end = time.time() + 5
    while time.time() < end:
        dev.set_colors([(0, 0, 255)] * n)
        root.update()
    stage(4, "Only SOME LEDs WHITE, the rest OFF\n(lamps 0-7 only)",
          lambda: dev.set_colors([(255, 255, 255)] * 8 + [(0, 0, 0)] * (n - 8)))
    stage(5, "Ambiglow should now be OFF / dark",
          lambda: dev.set_colors([(0, 0, 0)] * n))
    stage(6, "Monitor's OWN Ambiglow back\n(autonomous on)",
          lambda: dev.set_autonomous(True))
finally:
    dev.set_autonomous(True)
    dev.close()
    root.destroy()
print("done")
