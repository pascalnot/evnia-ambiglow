# Evnia Ambiglow

Fast, PC-driven Ambiglow for the **Philips Evnia 27M2N8500** monitor.

The monitor's built-in "follow video" Ambiglow updates at roughly 5 fps and
feels laggy. This app drives the 30 Ambiglow LEDs directly over USB at
**50 fps**, the most the monitor's firmware accepts, from a small tray app:

- **Follow screen**: the LEDs mirror the colours at the edges of your screen
- **Music**: reacts to whatever your PC is playing (spectrum or pulse)
- **Static color** and **effects** (rainbow, breathing, color cycle, wave)
- **Monitor default** hands the LEDs back to the monitor's own Ambiglow
- Brightness, saturation, smoothing, black level, effect speed, music sensitivity
- Black scenes turn the LEDs fully off
- Start with Windows (in the tray)

No drivers and no firmware changes: the monitor exposes its Ambiglow as a
standard Windows HID LampArray device, and the app just talks to it.

> Not affiliated with or endorsed by Philips or MMD. Use at your own risk.

## Requirements

- Windows 10 or 11
- Philips Evnia 27M2N8500, connected with its **USB upstream cable** to the PC
- [Python](https://www.python.org/downloads/) 3.10 or newer (tested with 3.13)

Other Evnia models with Ambiglow may work if they expose the same LampArray
interface (USB `0CF2:B207`); they are untested.

## Install and run

1. Download this repository (Code → Download ZIP) and unzip it anywhere.
2. Double-click **`start.bat`**. The first start sets up a Python environment
   (about a minute); later starts are instant.
3. The settings window opens, and the app keeps running in the tray. Closing the
   window hides it; use **Quit** in the window or the tray menu to exit.

Tick **Start with Windows** in the app to have it start in the tray at login.

### Before you start

- Turn on Ambiglow in the monitor's on-screen menu.
- Turn off Windows Dynamic Lighting for the monitor, or both will fight over the
  LEDs: Settings → Personalization → Dynamic Lighting → the monitor.
- Games in exclusive fullscreen may not be capturable; borderless windowed always
  works.

Settings and `log.txt` live in `%USERPROFILE%\.evnia-ambiglow\`.

## How it works

The Ambiglow is a HID LampArray (usage page `0x59`) on USB interface 1 of the
monitor. `evnia_ambiglow/hidlamp.py` talks to it with raw HID feature reports
through `hid.dll`:

| Report | Purpose |
|---|---|
| 1 | LampArray attributes: 30 lamps, MinUpdateInterval 20 ms |
| 2 / 3 | per-lamp attribute request / response (positions in µm) |
| 4 | LampMultiUpdate: 8 lamps per report, 51 bytes |
| 5 | LampRangeUpdate |
| 6 | Autonomous mode: 0 = PC control, 1 = monitor's own effects |

Firmware quirks found while building this, each of which silently breaks a
straightforward implementation:

1. **Intensity must be 1.** Every lamp reports `IntensityLevelCount = 1`, and
   multi-update reports with a higher intensity byte (such as 255) are ignored.
   Range updates tolerate 255, which makes this confusing to debug. Found by
   tracing Windows Dynamic Lighting's USB traffic (`tools/capture.ps1`).
2. **6 ms per report.** The firmware takes 6.0 ms to process each report, range
   or multi.
3. **Frames faster than 20 ms are dropped.** A frame (a report with the
   UpdateComplete flag) latched sooner than MinUpdateInterval after the previous
   one is discarded, and so are packets arriving right after a frame was
   latched. The engine therefore sends one frame every 20 ms with at most 2
   reports (the 16 LEDs that changed most). Sending 4 reports back to back
   looks choppy.

The LEDs themselves switch instantly; there is no fading in the firmware.

Screen capture uses DXGI desktop duplication ([dxcam](https://github.com/ra1nty/DXcam))
at 50 fps, and each LED samples a Gaussian-weighted area around its physical
position, so moving content glides between LEDs. Music mode captures the
default output device with WASAPI loopback ([PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch)).
The process runs at high CPU and GPU priority, so it keeps up while a game
uses the GPU.

## Project layout

```
EvniaAmbiglow.pyw        launcher (no console window)
start.bat                first-run setup + launch
evnia_ambiglow/
  hidlamp.py             raw HID LampArray driver (ctypes, no dependencies)
  engine.py              modes, easing and frame pacing
  screen.py              screen capture and per-LED sampling
  audio.py               music analysis
  effects.py             animations
  app.py                 tray icon and settings window
  settings.py, autostart.py, colors.py
tools/
  diag.py                shows solid colours through each HID command
  blinktest.py           red/blue blinking at 2-20 Hz
  ratetest.py            raw throughput
  capture.ps1            (admin) USB ETW trace of what Windows sends
```

Run a tool with `.venv\Scripts\python.exe tools\diag.py` while the app is closed.

## License

[MIT](LICENSE)
