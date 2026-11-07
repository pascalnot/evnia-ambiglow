"""Static colour check + raw throughput test for the Ambiglow LampArray."""
import colorsys
import sys
import time

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evnia_ambiglow.hidlamp import LampArray

dev = LampArray.find(0x0CF2, 0xB207)
n = dev.attributes()["lamp_count"]
dev.set_autonomous(False)

for name, rgb in (("red", (255, 0, 0)), ("green", (0, 255, 0)), ("blue", (0, 0, 255))):
    print("static", name)
    dev.set_colors([rgb] * n)
    time.sleep(0.8)

# Rainbow chase as fast as the USB control pipe allows.
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 4
frames, t0, worst = 0, time.perf_counter(), 0.0
while (now := time.perf_counter()) - t0 < secs:
    hue = (now - t0) * 0.5
    cols = [tuple(int(c * 255) for c in colorsys.hsv_to_rgb((hue + i / n) % 1, 1, 1)) for i in range(n)]
    f0 = time.perf_counter()
    dev.set_colors(cols)
    worst = max(worst, time.perf_counter() - f0)
    frames += 1
el = time.perf_counter() - t0
print(f"unthrottled: {frames} frames in {el:.2f}s = {frames / el:.1f} fps, worst frame {worst * 1000:.1f} ms")

dev.set_colors([(0, 0, 0)] * n)
time.sleep(0.2)
dev.set_autonomous(True)
dev.close()
