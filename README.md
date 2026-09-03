# Sismo-LA — neighborhood seismic node, self-calibrated against USGS

[English](README.md) · [Français](README.fr.md)

Los Angeles County (~10 million people) sits on highly active faults and already
has a dense professional network. The USGS catalog publishes magnitude, location
and depth within minutes of each event. This repository is one node in that
setting, built on an Arduino UNO Q, at about $80.

Question under test:

> Can a node in that price range detect an earthquake and estimate its
> magnitude, unattended, without manual calibration?

Live page (no station coordinates): <https://medialoco.github.io/sismo-la/>

![Operator dashboard: USGS circles and device estimates](docs/images/dashboard-replay.png)

*Operator dashboard. USGS events as colored circles; device estimates in red;
three models on the right. Screenshot from `--replay`: amplitudes are
synthetic, 38× too large, and measure the software
([replay residuals](#replay-and-out-of-sample-residuals)).*

## Status (2 September 2026)

The station runs on its own power and WiFi, with no attached computer. It
detects shakes, correlates them with USGS, writes a journal, and publishes a
JSON snapshot every 20 minutes (a heartbeat is forced after 4 h if the file is
unchanged). After a real unplug it reached a serving dashboard in **4 min 24 s**.
A later 5 h 43 min outage showed the MCU rebooting into its own flash.

On 2 September 2026 it recorded a cataloged earthquake in its continuous
envelope: **`ci41540608`**, M3.2, Ontario, CA, 12:37:12 UTC. Envelope z = 4.34
(threshold 4.0), peak 0.001095 g, baseline 0.0003816 g, 20 s window, lag 24 s.

The blind STA/LTA trigger did not fire (required amplitude ~0.0033 g). Amplitude
calibration is **0 of 8**. Confirmations are excluded from that fit
(`retro.feed_calibration: false`).

## Detection and confirmation

| Channel | Definition | Feeds amplitude calibration |
|---|---|---|
| Detection | STA/LTA fired without catalog timing | yes, once USGS matches |
| Confirmation | catalog origin time selected the window; recorded envelope elevated there | no |

The journal, dashboard and public page keep the two lists separate.

## Method

1. The IMU reduces each trigger to PGA, duration and dominant frequency.
2. The Linux side queries USGS FDSN (map context ≥ M0.5, calibration matches
   ≥ M2, radius 160 km).
3. A time match is a labelled (measurement, catalog) pair. An unmatched trigger
   is a noise example.
4. Three models refit online. After convergence they run from disk offline.

| Model | Input → output | Usable after |
|---|---|---|
| Amplitude calibration | log10(PGA), log10(distance) → magnitude | 8 matches |
| Distance model | duration, dominant frequency → epicentral distance | 5 matches |
| Noise filter | PGA, duration, frequency → P(earthquake) | 3 of each class |

Amplitude model: `M ≈ a·log10(PGA) + b·log10(R) + c`. Coefficients absorb this
sensor, mount, building and soil. See [`docs/calibration.md`](docs/calibration.md).

A continuous envelope (peak and RMS, 0.7–12 Hz, 1 Hz samples) is searched at the
arrival time implied by each catalog origin. That search uses a handful of
windows per event instead of ~170 000 blind STA/LTA windows per day, so it can
sit closer to the noise and average over the wavetrain. On this station’s noise
the gain is a **factor 7–8 in amplitude (one magnitude unit)**.

## Ground-motion law

The form used here was checked against **12 324 ShakeMap PGA values** from 40
southern California earthquakes (M3.03–5.51, 3–200 km, 1 006 stations). The
previous coefficients over-predicted amplitude by 37.9×. The refit is

`0.867·M − 1.740·log10 R − 3.305`

scatter 0.390 log10, R² = 0.80. Statements made with the old law were high by
about two magnitude units.

## Detection threshold

Firmware has an STA/LTA ratio, not a fixed g threshold. The floor is a site
property. Over 163 triggers the smallest peak that fired is **0.0034 g**
(0.0044 g in the quietest window). Through the refit law that becomes a required
magnitude, ±0.45 (1σ); below M3 the values are extrapolations:

| | 10 km | 30 km | 50 km | 100 km | 160 km |
|---|---|---|---|---|---|
| Blind trigger | 3.1 | 3.9 | 4.3 | 4.9 | 5.3 |
| Retrospective search | 2.1 | 2.9 | 3.3 | 3.9 | 4.3 |

Convolution with 2 185 catalog events (M ≥ 2, 160 km, 5 years) and the 0.39
log10 scatter, with site amplification ×1 to ×4:

| | events / year | mean wait | P(≥1 before 13 Sep 2026) |
|---|---|---|---|
| Blind trigger | 2.0 – 9.8 | 37–184 days | 6–28% |
| Trigger + retrospective search | 9.9 – 36.9 | 10–37 days | 28–70% |

The retrospective row assumes the site is at rest (~50% of hours here). During
a busy hour the envelope wander is about ×4; during a quiet hour, ~3%. Envelope
recording started 1 September 2026; earlier hours cannot be searched.

## Confirmation `ci41540608`

| | |
|---|---|
| Origin | 2026-09-02 12:37:12 UTC, M3.2, Ontario, CA |
| Envelope | z = 4.34 (threshold 4.0), peak 0.001095 g, baseline 0.0003816 g |
| Window | 20 s, lag 24 s after origin (ordinary S-wave travel time) |
| Blind STA/LTA | required ~0.0033 g; did not fire |
| Site | at rest (sensor electrical noise) |
| Calibration | unchanged (0 of 8), by design |

One event. z = 4.34 is a modest margin. The 1-in-1 200 false-confirmation rate
was computed on pure sensor noise; this site also produces local impulses, so
that rate is an upper bound until it is recomputed on the recorded envelope. The
significance test does not use lag; the 24 s delay is independent of the z cut.

## Other measured results

| Observation | Value |
|---|---|
| Trigger rate after remount (desk → better coupling) | 22.6 → 3.2 / h (−86%); noise floor 0.00087 → 0.00066 g (−24%) |
| Power-on to serving dashboard | 4 min 24 s (watchdog sidecar; App Lab otherwise stops the container at boot) |
| Dominant frequency (after sign-of-centered vs uncentered fix) | taps at 2.6 / 5.0 / 10.6 Hz; the bug had reported ~25 Hz on any signal |

Liveness is the MCU heartbeat (~10 s). HTTP 200 from the dashboard is not used
as proof the sensor is up. `health.stale` drives the public badge and a
`STATION DEGRADED` banner.

## Catalog audit

For each cataloged event the station computes expected amplitude from the refit
law and reads the recorded noise at that instant. Classes: **out of reach**,
**marginal**, **triggered**, **confirmed**, **should have been seen**. Only the
last is a fault.

30 days to 2 September 2026: **19 cataloged events, 1 confirmed, 0 should-have-
been-seen**. The published audit is those three counts. Which events were in
reach encodes distance and is not published. Method:
[`docs/expected-vs-observed.md`](docs/expected-vs-observed.md).

## Replay and out-of-sample residuals

`--replay` synthesizes amplitudes from catalog M and R through the *pre-refit*
law, so they are 38× too large (kept so the demo still crosses the trigger).
The calibrator then fits the inverse of that law. Residuals there test the
pipeline.

The dashboard RMSE is an in-sample residual with *true* catalog distance. Live
operation uses *estimated* distance. `python audit.py` scores the journal
prequentially:

| Estimator | run A (11 pts) | run B (27 pts) |
|---|---|---|
| In-sample, true distance (panel) | 0.20 Mw | 0.18 Mw |
| Out-of-sample, true distance | 0.30 Mw | 0.21 Mw |
| Out-of-sample, estimated distance (operational) | 1.10 Mw | 0.26 Mw |

At 11 points the 1.10 Mw figure is dominated by early, untrained predictions.
These numbers document the scoring method.

## Limits

- Detects events that have occurred; no forecast.
- Calibration is site-specific; moving the box requires reconvergence.
- A single PGA is a noisy energy proxy; ±0.3–0.5 magnitude is the realistic
  ceiling.
- Strong-motion neighborhood node. No teleseisms.
- Requires a busy region and a promptly published catalog.

## Cost (1 September 2026)

| Part | Price | Source |
|---|---|---|
| Arduino UNO Q 2 GB (ABX00162) | $59.00, or $44.00–45.20 | store.arduino.cc; DigiKey, PiShop, Farnell |
| Modulino Movement (ABX00101, LSM6DSOX) | $11.80 | store.arduino.cc |
| USB-C supply, 5 V / 3 A | ~$15 | commodity, estimate |
| **One node** | **$71–86** | ~$90 with tax and shipping |

A $25 figure used earlier in this project was wrong (the UNO Q alone exceeds
it). Raspberry Shake list price the same day: $294.99 board, $584.99 turnkey
([raspberryshake.org](https://raspberryshake.org/pricing)). Full BOM:
[`docs/hardware.md`](docs/hardware.md).

## Multi-station geometry

![One station yields a ring; three rings intersect](docs/images/network.png)

The firmware keeps the acceleration-vector magnitude, so one station yields a
distance and no bearing. P-wave polarization is below the trigger floor. Three
stations would intersect. Each node would fit its own coefficients against the
catalog. This is a geometric argument. It has not been measured: there is one
station, one confirmation, zero autonomous detections.

## Run (no hardware)

```bash
cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml

python main.py --replay       # http://localhost:8000
python audit.py               # out-of-sample residuals
python audit.py --include-synthetic
```

Other modes: `python main.py --mock`, `python pipeline.py --mock`,
`python main.py` (sensor). On the board the repo is an App Lab App:

```bash
arduino-app-cli app start ~/ArduinoApps/sismo-la
arduino-app-cli app logs  ~/ArduinoApps/sismo-la
```

## Architecture

```
                     Arduino UNO Q
 ┌───────────────────────────┬────────────────────────────────┐
 │   STM32U585 (MCU)         │   Dragonwing QRB2210 (MPU)     │
 │   Zephyr RTOS, real time  │   Debian Linux                 │
 ├───────────────────────────┼────────────────────────────────┤
 │ - IMU 100 Hz, LSM6DSOX    │ - WiFi + USGS FDSN             │
 │   Qwiic on Wire1          │   (context ≥ M0.5, matches ≥   │
 │ - STA/LTA 0.5 s / 10 s    │    M2, 160 km)                 │
 │ - PGA, duration, f0       │ - correlation, models,         │
 │ - event ──────────────────┼─►  envelope, retro, audit      │
 │   over the Bridge         │ - dashboard + publish          │
 └───────────────────────────┴────────────────────────────────┘
                    USGS: https://earthquake.usgs.gov/fdsnws/event/1/
```

Qwiic is **`Wire1`**. MCU `Serial` is D0/D1, not USB. Bridge requires matching
`arduino-router` and bridge-library versions. Notes:
[`docs/getting-started.md`](docs/getting-started.md),
[`docs/hardware.md`](docs/hardware.md).

## Publish

`python/main.py` writes a JSON snapshot (`publish:` in `config.yaml`).
[`web-remote/`](web-remote/) renders it. Numbers:
[`data.html`](web-remote/data.html). The snapshot has **no coordinates**.
`publish.include_location: true` adds the station to the map.

Journal and model state live on the host filesystem (`event_log.jsonl`), outside
the container.

## Layout

```
sismo-la/
├── app.yaml                   # App Lab manifest
├── python/                    # Dragonwing MPU (Debian)
│   ├── main.py                # loops, dashboard, publisher
│   ├── pipeline.py            # detection / correlation, headless CLI
│   ├── usgs.py                # FDSN client
│   ├── calibration.py         # amplitude + distance models
│   ├── classifier.py          # online logistic regression
│   ├── envelope.py            # continuous envelope, one CSV / UTC day
│   ├── retro.py               # search at catalog arrival time
│   ├── expected.py            # expected vs observed
│   ├── audit.py               # out-of-sample journal score
│   └── dashboard/index.html   # operator dashboard
├── sketch/                    # STM32U585 (Zephyr)
├── deploy/                    # watchdog sidecar
├── docs/
└── web-remote/                # GitHub Pages
```

## Checklist

- [x] Autonomous node: detect → correlate → learn → publish.
- [x] Power-cut recovery (4 min 24 s).
- [x] Detection threshold and expected rates measured.
- [x] Attenuation law refit on 12 324 ShakeMap PGA values.
- [x] Continuous envelope + retrospective search (factor 7–8 in amplitude),
      counted separately from detections.
- [x] First confirmation (`ci41540608`, M3.2, 2 September 2026). Blind trigger
      required ~3× the arrived amplitude.
- [ ] First autonomous detection: none. Amplitude calibration 0 of 8.
- [x] Catalog audit; 0 should-have-been-seen in the 30 days to 2 September.
- [ ] Calibration curve from real recordings, held-out residuals.
- [ ] Contest video: replay + live tap.

[Hackster contest](https://www.hackster.io/contests/invent-the-future-with-arduino-uno-q-and-app-lab),
**Best Social Impact**, submissions close **13 September 2026**. Write-up:
[`docs/hackster-story.md`](docs/hackster-story.md).

## License

MIT — [`LICENSE`](LICENSE).
