# Sismo-LA — a home seismograph that learns from the official earthquake list

[English](README.md) · [Français](README.fr.md)

Sismo-LA is one small station in Los Angeles County. It sits in a house, runs
on USB-C power and WiFi, and costs about $80. A MEMS accelerometer (a tiny chip
that measures acceleration, the same class of sensor as in a phone) records
when the ground or the building shakes. The [USGS catalog](https://earthquake.usgs.gov/)
is the official list of earthquakes: within minutes of an event it publishes
**magnitude** (size, written M3.2 for example), place, depth and exact time.

The station’s job is to pair *what this box measured* with *what USGS says
happened*, and from those pairs to fit a **site-specific** model: how *this*
sensor, on *this* shelf, in *this* building, converts a shake into a magnitude
and a distance. After that fit, the model can run with the network unplugged.

Question under test:

> Can a node at that price detect an earthquake and estimate its magnitude,
> unattended, with no one calibrating it by hand?

Live page (the station’s coordinates are not published):
<https://medialoco.github.io/sismo-la/>

![Operator dashboard: USGS circles and device estimates](docs/images/dashboard-replay.png)

*Operator dashboard. Colored circles are USGS events; red marks are the
device’s own estimates; the three models sit on the right. This screenshot is
`--replay` (see [Replay](#replay-a-software-test)): the amplitudes are
synthetic and 38× too large. They test the code, not the sensor.*

## Terms used below

| Term | Meaning here |
|---|---|
| **Station / node** | This one box: Arduino UNO Q + MEMS module + power + WiFi. |
| **MCU** | The real-time microcontroller (STM32). It reads the sensor 100 times per second and decides when a shake starts. |
| **Linux side** | The board’s application processor. It talks to USGS, stores records, fits models, serves the dashboard. |
| **PGA** | Peak ground acceleration: the largest acceleration in a shake, in *g* (1 g ≈ 9.8 m/s²). Footsteps in this house are a few thousandths of a g. |
| **STA/LTA** | Short-term average / long-term average. A classic seismic trigger: energy in the last 0.5 s divided by energy in the last 10 s. When the ratio jumps, the MCU declares an event. There is no fixed “fire at 0.01 g” line; the floor moves with the recent noise. |
| **Blind trigger** | STA/LTA firing on its own, with no help from the catalog. |
| **Envelope** | A 1 Hz trace of how strong the filtered ground motion (0.7–12 Hz) was. One CSV file per UTC day. Lets the station look *back* at a second it did not trigger on. |
| **z** | How many local noise-dispersions the envelope sits above the minutes just before. z = 4.0 is the confirmation threshold. |
| **Calibration** | Fitting `magnitude ≈ a·log10(PGA) + b·log10(distance) + c` on matched examples. Eight matches are required before the amplitude model is treated as usable. Coefficients belong to this installation. |
| **Strong-motion** | Sensitive to nearby, felt-scale shaking. This node does not record distant (teleseismic) earthquakes. |

## Two channels that must stay separate

A MEMS chip does not know an earthquake from a slammed door. USGS does. The
station therefore uses two different ways of looking at the ground, and counts
them apart.

| Channel | What happened | May train the amplitude model? |
|---|---|---|
| **Detection** | The blind STA/LTA trigger fired by itself. If USGS later has an earthquake at that second, the pair (PGA, catalog M and distance) is a calibration example. | yes |
| **Confirmation** | USGS published an origin time. The station computed when the waves should have arrived and read the stored envelope there. If the envelope is elevated (z ≥ 4), the ground moved. The station did not find that second on its own. | no |

Confirmations are excluded because they are *selected* for being a large
excursion next to the noise: their PGA is biased high. Fitting a magnitude law
on that set would bake the bias in (`retro.feed_calibration: false`).

The journal, the dashboard and the public page keep two lists.

## How a cycle runs

1. **Feel.** The MCU runs STA/LTA. On a trigger it sends three numbers over the
   on-board Bridge: PGA, duration, dominant frequency.
2. **Ask.** Linux queries USGS FDSN in a 160 km radius. The map shows events
   down to M0.5; a match used for calibration must be ≥ M2.
3. **Label.** Same second as a catalog earthquake → one training pair. No
   catalog event → a noise example (truck, footsteps).
4. **Fit.** Three models update on every example. Once they have enough points
   they are stored on disk and work offline.

| Model | Input → output | Usable after |
|---|---|---|
| Amplitude calibration | log10(PGA), log10(distance) → magnitude | 8 earthquake matches |
| Distance model | duration, dominant frequency → epicentral distance | 5 matches |
| Noise filter | PGA, duration, frequency → P(this is an earthquake) | 3 earthquake + 3 noise |

Details: [`docs/calibration.md`](docs/calibration.md).

**Retrospective search.** Independently of the trigger, the station records the
envelope all the time. When USGS publishes an origin, the station re-reads the
few seconds when the S-wave should have arrived (a few tens of seconds later,
depending on distance). That is a handful of windows per earthquake, against
about 170 000 blind STA/LTA windows per day, so the test can sit closer to the
noise and average over the wavetrain. On this station’s own noise the extra
reach is a **factor 7–8 in amplitude, one magnitude unit**.

## Status (2 September 2026)

The station is autonomous: own power, WiFi, no attached computer, no shell
required. It publishes a JSON snapshot every 20 minutes. If nothing changed, it
still sends a heartbeat after 4 hours so the public page can tell a quiet night
from a dead publisher. After a real unplug, the dashboard answered in
**4 min 24 s**. A later 5 h 43 min outage showed the MCU restarting from its
own flash.

**Amplitude calibration: 0 of 8.** **Autonomous detections of earthquakes: 0.**
One cataloged earthquake has been **confirmed** in the envelope (next section).

## Confirmation: `ci41540608`

USGS event M3.2, Ontario, California, 2 September 2026, 12:37:12 UTC.

| Quantity | Value | Reading |
|---|---|---|
| Envelope z | 4.34 (threshold 4.0) | the trace sat 4.34 dispersions above the previous minutes |
| Peak / baseline | 0.001095 g / 0.0003816 g | about 3× the quiet level, still a small acceleration |
| Window / lag | 20 s, 24 s after origin | 24 s is a normal S-wave travel time at this distance |
| Blind STA/LTA | needed ~0.0033 g; did not fire | the trigger wanted ~3× the amplitude that arrived |
| Site | at rest | sensor electrical noise; nobody walking above the box |
| Calibration counter | still 0 of 8 | a confirmation is not allowed to increment it |

One event, not a rate. z = 4.34 is a thin margin over 4.0. A false-confirmation
rate of 1 in 1 200 was computed on *pure sensor noise*; this house also produces
its own impulses, so that 1-in-1 200 is optimistic until it is recomputed on
the recorded envelope. The z test does not look at lag: the 24 s delay is
independent evidence.

## How large an earthquake it can catch

The trigger floor is a property of the site (noise + coupling), measured on
163 real triggers: the smallest PGA that ever fired is **0.0034 g** (0.0044 g
in the quietest window). Passed through the ground-motion law below, that floor
becomes a **required magnitude** at a given distance (±0.45 at 1σ). Below M3
the numbers are extrapolations:

| Required magnitude | 10 km | 30 km | 50 km | 100 km | 160 km |
|---|---|---|---|---|---|
| Blind trigger | 3.1 | 3.9 | 4.3 | 4.9 | 5.3 |
| Retrospective search | 2.1 | 2.9 | 3.3 | 3.9 | 4.3 |

Those thresholds, crossed with 2 185 real USGS events (M ≥ 2, 160 km, 5 years)
and the law’s 0.39 log10 scatter, with unknown site amplification ×1 to ×4:

| | earthquakes / year | mean wait | P(at least one before 13 Sep 2026) |
|---|---|---|---|
| Blind trigger only | 2.0 – 9.8 | 37–184 days | 6–28% |
| Trigger + retrospective search | 9.9 – 36.9 | 10–37 days | 28–70% |

The retrospective row assumes the house is at rest (about half the hours here).
In a busy hour the envelope wanders by about ×4; in a quiet hour, ~3%. Envelope
files exist from 1 September 2026; earlier hours cannot be searched.

## Ground-motion law

A **ground-motion law** predicts PGA from magnitude and distance. The station
uses the same algebraic form the other way: given PGA and distance, estimate M.
The coefficients were fitted on **12 324 PGA values** actually recorded by USGS
ShakeMap stations during 40 southern California earthquakes (M3.03–5.51,
3–200 km, 1 006 stations):

`PGA_pred = 0.867·M − 1.740·log10 R − 3.305`  (log10 g)

scatter 0.390 log10, R² = 0.80. An earlier coefficient set over-predicted
amplitude by 37.9× (about two magnitude units).

## Does silence mean “broken” or “nothing happened”?

An empty detection list is ambiguous. For every cataloged earthquake the
station now (1) predicts the PGA the law says should have arrived, and (2)
reads the noise it was actually sitting in at that second. Five classes:

| Class | Meaning |
|---|---|
| Out of reach | expected PGA below what this site can see; normal for ~99% of the catalog |
| Marginal | close to the floor; do not treat as a miss |
| Triggered | blind STA/LTA fired and matched |
| Confirmed | envelope elevated at the predicted arrival |
| Should have been seen | in reach, site quiet enough, nothing in the record → a fault |

30 days to 2 September 2026: **19 cataloged events, 1 confirmed, 0 should-have-
been-seen.** The public audit is those three counts. The list of which events
were in reach would encode distance and is kept on the station’s LAN. Method:
[`docs/expected-vs-observed.md`](docs/expected-vs-observed.md).

## Other measurements

| Observation | Value |
|---|---|
| Trigger rate after moving the box from a desk to a stiffer mount | 22.6 → 3.2 events / h (−86%). Noise floor 0.00087 → 0.00066 g (−24%). Coupling dominates false triggers. |
| Power-on → dashboard answering | 4 min 24 s. A watchdog sidecar restarts the container; App Lab otherwise stops it one second after boot. |
| Dominant frequency (after a sign bug: centered vs uncentered sample) | real taps at 2.6 / 5.0 / 10.6 Hz. The bug had printed ~25 Hz on every signal. |

The only independent “the sensor is alive” signal is the MCU heartbeat (~10 s).
A 200 from the web dashboard means the Linux process is up. `health.stale`
drives the public badge and a `STATION DEGRADED` banner.

## Replay: a software test

`python main.py --replay` pulls the real catalog for the last 24 hours and
*invents* PGA from magnitude and distance using the *old* (pre-refit) law, so
the fake amplitudes are 38× too large. That is on purpose: corrected values
would sit under the trigger and the demo would show nothing. The calibrator
then fits the inverse of that same law. Residuals in replay test the pipeline.
They are circular. They are not physical.

The dashboard RMSE is an **in-sample** residual (the model scored on points it
already fitted) and it is given the *true* catalog distance. Live operation
gets only an *estimated* distance. `python audit.py` walks the journal in time
order and scores each point with the model *as it was before that point*
(out-of-sample, prequential):

| Estimator | run A (11 pts) | run B (27 pts) |
|---|---|---|
| In-sample, true distance (what the panel shows) | 0.20 Mw | 0.18 Mw |
| Out-of-sample, true distance | 0.30 Mw | 0.21 Mw |
| Out-of-sample, estimated distance (live path) | 1.10 Mw | 0.26 Mw |

At 11 points, 1.10 Mw is dominated by the first predictions, when the model had
almost no data. The table documents the scoring method.

## Limits

- The station reports earthquakes that have already occurred. It does not
  forecast.
- Move the box and the coefficients are wrong until they are fitted again.
- One PGA is a noisy stand-in for released energy. ±0.3–0.5 magnitude is the
  realistic ceiling even with a good fit.
- Strong-motion only. No teleseisms.
- The method needs a busy region and a catalog that publishes within minutes.
  Southern California is close to that case.

## Cost (prices 1 September 2026)

| Part | Price | Source |
|---|---|---|
| Arduino UNO Q 2 GB (ABX00162) | $59.00, or $44.00–45.20 | store.arduino.cc; DigiKey, PiShop, Farnell |
| Modulino Movement (ABX00101, LSM6DSOX) | $11.80 | store.arduino.cc |
| USB-C supply, 5 V / 3 A | ~$15 | commodity, estimate |
| **One node** | **$71–86** | ~$90 with tax and shipping |

A $25 figure used earlier in this project was wrong: the UNO Q alone costs more.
Raspberry Shake the same day: $294.99 board, $584.99 turnkey
([raspberryshake.org](https://raspberryshake.org/pricing)). Full list:
[`docs/hardware.md`](docs/hardware.md).

## What three stations would add (geometry, not a result)

![One station yields a ring; three rings intersect](docs/images/network.png)

The firmware stores the *magnitude* of the acceleration vector, so direction is
discarded. The P-wave (the arrival whose polarization points at the source) is
below this trigger. One station therefore yields a **distance**, which is a
ring on the map. Three rings would intersect. Each node would still fit its own
coefficients against the catalog. This has not been built: one station, one
confirmation, zero autonomous detections.

## Run it without hardware

Replay uses the real catalog and synthetic amplitudes (see above).

```bash
cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml

python main.py --replay       # then http://localhost:8000
python audit.py               # out-of-sample residuals from the journal
python audit.py --include-synthetic
```

`python main.py --mock` invents shakes. `python main.py` talks to a real sensor.
On the board this folder *is* an [App Lab](https://docs.arduino.cc/) App:

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
 │   Qwiic on Wire1          │   (map ≥ M0.5, matches ≥ M2,   │
 │ - STA/LTA 0.5 s / 10 s    │    160 km)                     │
 │ - PGA, duration, f0       │ - correlation, models,         │
 │ - event ──────────────────┼─►  envelope, retro, audit      │
 │   over the Bridge         │ - dashboard + publish          │
 └───────────────────────────┴────────────────────────────────┘
                    USGS: https://earthquake.usgs.gov/fdsnws/event/1/
```

On this board the Qwiic connector is **`Wire1`** (not `Wire`). MCU `Serial` is
pins D0/D1, not USB. The MCU↔Linux Bridge needs matching versions of
`arduino-router` and the bridge library.
[`docs/getting-started.md`](docs/getting-started.md),
[`docs/hardware.md`](docs/hardware.md).

## Publish

`python/main.py` writes a JSON snapshot on a timer (`publish:` in
`config.yaml`). [`web-remote/`](web-remote/) draws the map;
[`data.html`](web-remote/data.html) is the tables. The snapshot contains
**no coordinates**. Set `publish.include_location: true` to plot the station.

The journal (`event_log.jsonl`) and the model files live on the host disk, next
to the container, so they survive restarts.

## Layout

```
sismo-la/
├── app.yaml                   # App Lab manifest
├── python/                    # Linux half (Dragonwing)
│   ├── main.py                # loops, dashboard, publisher
│   ├── pipeline.py            # detection / correlation
│   ├── usgs.py                # USGS catalog client
│   ├── calibration.py         # amplitude + distance models
│   ├── classifier.py          # earthquake-vs-noise filter
│   ├── envelope.py            # continuous envelope (one CSV / UTC day)
│   ├── retro.py               # look back at the catalog arrival time
│   ├── expected.py            # expected vs observed
│   ├── audit.py               # out-of-sample score from the journal
│   └── dashboard/index.html   # operator dashboard
├── sketch/                    # MCU half (STM32, Zephyr)
├── deploy/                    # watchdog that restarts the container
├── docs/
└── web-remote/                # public page on GitHub Pages
```

## Checklist

- [x] Autonomous node: detect → match to USGS → learn → publish.
- [x] Recovers from a power cut (4 min 24 s).
- [x] Trigger floor and expected rates measured.
- [x] Ground-motion law refit on 12 324 ShakeMap PGA values.
- [x] Continuous envelope + retrospective search (factor 7–8 in amplitude),
      counted separately from detections.
- [x] First confirmation (`ci41540608`, M3.2, 2 September 2026). Blind trigger
      needed ~3× the arrived amplitude.
- [ ] First autonomous detection: none. Amplitude calibration 0 of 8.
- [x] Catalog audit; 0 should-have-been-seen in the 30 days to 2 September.
- [ ] Calibration curve from real recordings, held-out residuals.
- [ ] Contest video: replay + a live tap on the box.

Entry in
[Invent the Future with Arduino UNO Q and App Lab](https://www.hackster.io/contests/invent-the-future-with-arduino-uno-q-and-app-lab),
**Best Social Impact**, submissions close **13 September 2026**. Longer write-up:
[`docs/hackster-story.md`](docs/hackster-story.md).

## License

MIT — [`LICENSE`](LICENSE).
