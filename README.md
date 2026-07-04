# Sismo-LA — a $25 seismograph that learns from real Los Angeles earthquakes

A **low-cost seismic node** built on the **Arduino UNO Q**, made credible by
**continuous self-calibration against the USGS catalog**: every confirmed
earthquake teaches the device its own, site-specific response function.

Entry for the
[Invent the Future with Arduino UNO Q and App Lab](https://www.hackster.io/contests/invent-the-future-with-arduino-uno-q-and-app-lab)
contest — target category: **Best Social Impact**. The submission story draft
lives in [`docs/hackster-story.md`](docs/hackster-story.md).

![Sismo-LA dashboard — device estimates (red) vs USGS ground truth](docs/images/dashboard-replay.png)

*The dashboard in replay mode: USGS earthquakes (colored circles, the ground
truth) vs what the device alone estimates (red circles + error vectors), with
the self-calibration and AI-filter status live in the side panel.*

## The idea in one paragraph

A cheap MEMS sensor is not a seismometer: it feels shakes but cannot tell you
magnitude or distance — it is uncalibrated. In Los Angeles, however, the
ground truth is free and always on: the **USGS catalog** publishes magnitude,
location and depth for dozens of earthquakes around the city every week. So
the device calibrates itself in place: each local detection that matches a
cataloged quake (≥ M2, 160 km radius) becomes one calibration point, and a
regression turns raw accelerations into magnitude estimates. Every earthquake
makes it better. The same loop labels data for an **AI noise filter**
(earthquake vs passing truck) — no offline training set required.

## What the device learns (three models, all persisted)

| Model | Input → output | Learned from |
|---|---|---|
| Amplitude calibration | log10(PGA), log10(distance) → magnitude | USGS-confirmed matches |
| Distance model | duration, dominant frequency → epicentral distance | USGS-confirmed matches |
| AI noise filter | PGA, duration, frequency → P(real earthquake) | matches = quake, unmatched = noise |

With distance + magnitude, a single station produces a full standalone
estimate — the red circles on the map. One station knows distance but not
direction (it draws a ring, not a pin); three neighboring nodes could
triangulate. That is the scalability story.

## Dual-brain architecture

```
                     Arduino UNO Q
 ┌───────────────────────────┬────────────────────────────────┐
 │   STM32U585 (MCU)         │   Dragonwing QRB2210 (MPU)     │
 │   Zephyr RTOS, real time  │   Debian Linux                 │
 ├───────────────────────────┼────────────────────────────────┤
 │ - reads the IMU at 100 Hz │ - WiFi + USGS FDSN feed        │
 │   (LSM6DSOX via Qwiic,    │   (context ≥ M0.5, calibration │
 │    bus Wire1)             │    matches ≥ M2, 160 km)       │
 │ - STA/LTA trigger         │ - temporal correlation         │
 │ - PGA, duration, dominant │ - calibration + distance model │
 │   frequency per event     │ - AI noise filter (online      │
 │ - one JSON event ─────────┼─►  logistic regression)        │
 │   via Bridge Monitor      │ - Leaflet web dashboard        │
 └───────────────────────────┴────────────────────────────────┘
                    USGS: https://earthquake.usgs.gov/fdsnws/event/1/
```

UNO Q gotchas we learned the hard way (details in
[`docs/getting-started.md`](docs/getting-started.md)):

- the Qwiic connector is on **`Wire1`**, not `Wire`;
- the MCU's `Serial` goes to the **D0/D1 pins, not USB** — events must go
  through the **Bridge Monitor** (the USB-C port belongs to the Linux side);
- the MCU↔Linux Bridge requires the board's `arduino-router` and the
  `Arduino_RouterBridge` library to be **version-matched** — update the board
  OS before flashing.

## Hardware

- **Arduino UNO Q** (4 GB) — WiFi on board.
- **Arduino Modulino Movement** (ABX00101, LSM6DSOX) + its bundled Qwiic
  cable. Plug-and-play, zero soldering.
- USB-C data cable (development) or USB-C power supply (standalone).

Bill of materials and wiring: [`docs/hardware.md`](docs/hardware.md).

## Quick start (no hardware needed)

```bash
cd app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml

python server.py --replay    # DEMO: replays the last 24 h of real USGS quakes
                             # as live detections -> http://localhost:8000
python server.py --mock      # synthetic shakes, same pipeline
python main.py --mock        # headless CLI variant
```

`--replay` fills the map within minutes using the real catalog — calibration
converges (RMSE ≈ 0.2 Mw in our validation) and the AI filter starts
separating quakes from injected truck noise, live on screen. On the board,
run `python server.py` (no flag) to consume real sensor events.

## Repository layout

```
sismo-la/
├── README.md
├── app.yaml                   # App Lab manifest (skeleton)
├── docs/
│   ├── getting-started.md     # end-to-end checklist (mock → WiFi → flash → live)
│   ├── architecture.md        # pipeline & design decisions
│   ├── calibration.md         # the core idea: USGS self-calibration
│   ├── hardware.md            # parts + wiring
│   ├── hackster-story.md      # contest submission draft (English)
│   ├── hackster-submission.md # contest rules checklist
│   └── images/                # screenshots for docs & submission
├── firmware/seismo_mcu/
│   └── seismo_mcu.ino         # MCU: STA/LTA + events via Bridge Monitor
└── app/
    ├── server.py              # detection loop + web dashboard (main entrypoint)
    ├── main.py                # headless CLI variant
    ├── usgs.py                # USGS FDSN client (LA-centered)
    ├── calibration.py         # amplitude model + distance model (persisted)
    ├── classifier.py          # online quake-vs-noise logistic regression
    ├── dashboard/index.html   # Leaflet map: USGS vs device, self-calib status
    ├── requirements.txt
    └── config.example.yaml
```

## Status

- [x] Full software chain validated end-to-end (replay mode, live USGS data):
      correlation → calibration (RMSE ≈ 0.2 Mw) → distance model → AI filter.
- [x] Web dashboard: USGS vs device overlay, error vectors, mode badge.
- [x] Firmware compiles and flashes on the UNO Q (`arduino-cli`, FQBN
      `arduino:zephyr:unoq`); sensor connected (Modulino on Qwiic).
- [x] Board on WiFi, USGS reachable from the board.
- [ ] MCU→Linux Bridge link (board OS update in progress to match library
      versions), then first live tap test.
- [ ] Accumulate real M2+ correlations over LA; produce the calibration curve.
- [ ] Optional: Edge Impulse classifier to replace the built-in filter.
- [ ] Hackster submission (deadline **August 30, 2026**) — media checklist in
      [`docs/hackster-story.md`](docs/hackster-story.md).

## Calibration in brief

For each local shake we search the USGS catalog for a confirmed earthquake
within a time window that absorbs wave propagation and publication delay. On
a match we add `(log10(PGA), log10(distance), magnitude)` to the calibration
set and refit `Mw ≈ a·log10(PGA) + b·log10(distance) + c`; the coda duration
and dominant frequency feed the distance model the same way. Details:
[`docs/calibration.md`](docs/calibration.md).
