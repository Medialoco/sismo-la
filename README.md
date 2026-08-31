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
the self-calibration and AI-filter status live in the side panel. Replay figures
measure the **software pipeline**, not the sensor — see
[What this is, and what it is not](#what-this-is-and-what-it-is-not).*

## What this is, and what it is not

Read this before the numbers, so none of them are misread.

**It detects, it does not predict.** The device characterizes earthquakes *while
they happen* — how strong, how far. It says nothing about earthquakes that have
not occurred yet. Earthquake prediction is not a solved problem and this project
does not attempt it.

**It works disconnected, once calibrated.** The three learned models are
persisted to disk, and inference is arithmetic on stored coefficients. Cut the
network and the station keeps estimating magnitude and distance for the shakes
it feels; reconnecting lets you check those estimates against the catalog after
the fact. One capability degrades offline: with no matched catalog event to
borrow an azimuth from, the output becomes a distance *ring*, not a located
point. Offline it knows how big and how far, not in which direction.

**It is calibrated for one spot.** The learned transfer function absorbs this
sensor, this mount, this building and this soil. Move the device and it must
reconverge. That is the method working as designed, not a defect.

**Replay figures validate the software, not the sensor.** In `--replay` mode the
sensor readings are *synthesized* from cataloged magnitude and distance through
an attenuation law, and the calibration then fits the inverse of that same law.
The exercise proves the pipeline is correct and numerically stable; it is
partly circular by construction and measures no physical accuracy. Real accuracy
requires genuine recordings of genuine earthquakes — that campaign is ongoing.

**Expect ±0.3–0.5 magnitude, honestly.** Magnitude inferred from a single
peak-acceleration sample is approximate by nature. A MEMS accelerometer is a
strong-motion instrument: it senses appreciable local shaking, roughly M2.5+ at
short range, and records no teleseisms. This is a neighborhood node, not an
observatory.

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

`--replay` fills the map within minutes: it pulls the real catalog, then
*synthesizes* a plausible sensor reading for each cataloged quake and feeds the
unmodified pipeline. Calibration converges and the AI filter starts separating
quakes from injected truck noise, live on screen — a demonstration that the
software works, not a measurement of sensor accuracy (see
[What this is, and what it is not](#what-this-is-and-what-it-is-not)). On the
board, run `python server.py` (no flag) to consume real sensor events.

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
├── web-remote/
│   └── sismo.html             # static public page for any web host: reads the
│                              #   station.json the device uploads + live USGS
└── app/
    ├── server.py              # detection loop + web dashboard + publisher
    ├── main.py                # headless CLI variant
    ├── usgs.py                # USGS FDSN client (LA-centered)
    ├── calibration.py         # amplitude model + distance model (persisted)
    ├── classifier.py          # online quake-vs-noise logistic regression
    ├── dashboard/index.html   # Leaflet map: USGS vs device, self-calib status
    ├── requirements.txt
    └── config.example.yaml
```

## Autonomous operation

The station needs only **WiFi and USB-C power** — no attached computer. Beyond
serving its local dashboard, `server.py` can push a JSON snapshot of the
station (detections, estimates, calibration state) to a remote site every
minute (`publish:` block in `config.yaml`: HTTP POST, file write, or any
upload command such as `scp`/`curl -T`). The static page
[`web-remote/sismo.html`](web-remote/sismo.html) — hostable anywhere, no
backend — overlays that snapshot on the live USGS map, so anyone can watch
the device's red estimates against the official record from the open web.

## Status

- [x] Full software chain validated end-to-end on replayed catalog data:
      correlation → calibration → distance model → AI filter. Validates the
      pipeline, not the sensor.
- [ ] **Physical validation on real recordings** — the number that would
      actually measure this instrument. Not yet available.
- [x] Web dashboard: USGS vs device overlay, error vectors, mode badge.
- [x] Firmware compiles and flashes on the UNO Q (`arduino-cli`, FQBN
      `arduino:zephyr:unoq`); sensor connected (Modulino on Qwiic).
- [x] Board on WiFi, USGS reachable from the board.
- [x] Autonomous publishing: snapshot upload to a remote site + static public
      page (`web-remote/sismo.html`), verified locally end-to-end.
- [x] MCU→Linux Bridge link working: the app consumes the Monitor stream and
      skips the firmware heartbeats.
- [ ] Live tap test, then move the whole app onto the board for true autonomy.
- [ ] Accumulate real M2+ correlations over LA; produce the calibration curve.
- [ ] Optional: Edge Impulse classifier to replace the built-in filter.
- [ ] Hackster submission (deadline **September 13, 2026**) — media checklist in
      [`docs/hackster-submission.md`](docs/hackster-submission.md).

## Calibration in brief

For each local shake we search the USGS catalog for a confirmed earthquake
within a time window that absorbs wave propagation and publication delay. On
a match we add `(log10(PGA), log10(distance), magnitude)` to the calibration
set and refit `Mw ≈ a·log10(PGA) + b·log10(distance) + c`; the coda duration
and dominant frequency feed the distance model the same way. Details:
[`docs/calibration.md`](docs/calibration.md).

## License

Released under the MIT License — see [`LICENSE`](LICENSE).
