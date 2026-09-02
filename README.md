# Sismo-LA — can a neighborhood run its own seismic network?

Nearly ten million people live in Los Angeles County, on some of the most
active faults in the world. The region is already densely instrumented — hundreds of
professional stations, and a USGS catalog that publishes magnitude, location and
depth within minutes of every event. Almost none of that hardware sits in
anybody's home. The instruments that matter belong to institutions, are sited by
institutions, and are calibrated by institutions.

Suppose one node cost $80. The rest of a neighborhood network is easy — hosts,
WiFi, a map. The hard part is the prerequisite:

> **Can a node that cheap detect an earthquake and put a number on it, running
> unattended, with nobody ever calibrating it?**

This repository is one node answering that question in Los Angeles: continuous
operation on real hardware, and an honest account of how far it gets. Stating
the question instead of asserting the answer is deliberate. It makes the project
falsifiable, and the partial result is part of the result.

**Where it stands, 1 September 2026.** The autonomous half is done: the station
runs on its own power with no shell and no attached computer, detects shakes,
correlates them against USGS, publishes a snapshot every 20 minutes, and came
back by itself after a real power cut. The measuring half is not: **it has yet
to recognize a single genuine earthquake — 0 of the 8 matches** its amplitude
model needs. What changed this week is that the gap stopped being a mystery:
the detection threshold is now measured, and measuring it showed that what held
the station back was not the sensor but the cost of watching blindly. Asking the
catalog *when* to look instead is worth a full magnitude unit, and it took the
odds of feeling a real earthquake before the deadline from 6–28% to 28–70%.

![Sismo-LA dashboard — device estimates in red vs USGS ground truth](docs/images/dashboard-replay.png)

*The operator dashboard. Left, USGS events as colored circles — the answer key;
the device's own estimates in red. Right, the three models learning. Figures in
this screenshot come from replay mode, whose amplitudes are synthetic and 38×
too large by design; they measure the software, not the sensor;
[see below](#what-is-established-and-what-is-not).*

## What a node costs

Prices checked 1 September 2026.

| Part | Price | Source |
|---|---|---|
| Arduino UNO Q 2 GB (ABX00162) | $59.00, or $44.00–45.20 | store.arduino.cc; DigiKey, PiShop, Farnell |
| Modulino Movement (ABX00101, LSM6DSOX) | $11.80 | store.arduino.cc |
| USB-C supply, 5 V / 3 A | ~$15 | commodity, estimate |
| **One node** | **$71–86** | ~$90 with tax and shipping |

So: **$75–90 a node, not $25.** Any earlier claim of $25 in this project was
unsubstantiated and is retracted; the UNO Q alone costs more than that.

The argument survives the correction easily. A research-grade station is a
five-figure item once sited, installed and maintained — two orders of magnitude
above this. The cheapest citizen instrument with a public price tag is a
Raspberry Shake, $294.99 for the board and $584.99 turnkey
([raspberryshake.org](https://raspberryshake.org/pricing), same date). And the
part that actually measures the ground here — the MEMS module — is $11.80. Most
of a node's cost is the computer that learns, not the sensor that feels.

Full bill of materials in [`docs/hardware.md`](docs/hardware.md).

## Why a cheap node can be calibrated at all

A MEMS accelerometer feels the ground move but has no idea how big the
earthquake was. It is uncalibrated, and calibrating a seismic instrument
normally takes a shake table or a professional station standing next to it.

In Los Angeles it takes neither, because the answer key is free and arrives in
minutes.

![How Sismo-LA calibrates itself: the sensor measures a shake, the USGS catalog says what it really was, matching the two in time produces a labelled example, and fitting those examples lets the station estimate magnitude and distance on its own](docs/images/how-it-works.png)

1. The sensor feels a shake, reduced to three numbers: peak acceleration,
   duration, dominant frequency.
2. The Linux side asks the USGS catalog whether a real earthquake just happened
   nearby.
3. **Match** → that pair (what I measured ↔ what it really was) is one training
   example. **No match** → it was a truck, which is a training example too.
4. Three models refit on every example. Nobody labels anything by hand.
5. Once converged, the models live on disk and run with the network unplugged.

| Model | Input → output | Usable after |
|---|---|---|
| Amplitude calibration | log10(PGA), log10(distance) → magnitude | 8 matches |
| Distance model | duration, dominant frequency → epicentral distance | 5 matches |
| Noise filter | PGA, duration, frequency → P(real earthquake) | 3 of each class |

The amplitude model is a ground-motion equation fitted backwards,
`M ≈ a·log10(PGA) + b·log10(R) + c`. Its coefficients are not universal
constants: they absorb this sensor, this mount, this building, this soil. That
is the point — no laboratory could have calibrated *this* installation, and a
network of these would need no laboratory either. Details in
[`docs/calibration.md`](docs/calibration.md).

## What actually happened when we ran it

Five episodes from the log, chosen because they say something about deploying
these in people's homes.

**Moving the box cut false triggers by 86%, with no code change.** Off the desk
and onto a better mount, the trigger rate went from 22.6 to 3.2 per hour while
the noise floor barely moved (0.00087 → 0.00066 g, −24%). Coupling, not
firmware, is what decides whether a home node is usable — and the observable to
give an owner is the trigger rate on the dashboard, which responds by nearly an
order of magnitude, not the noise floor, which does not.

**A power cut, and the station came back alone.** Docker starts the container at
boot, then App Lab's daemon stops it one second later because it has no notion
of an app that should still be running — which also marks the stop as
deliberate, so the next boot does not even try. A watchdog sidecar recovers it:
**4 min 24 s from power-on to a serving dashboard**, verified on a real
unplug. A later 5 h 43 min outage confirmed the microcontroller reboots into its
own flash unaided.

**The station went blind, and nothing said so.** The MCU stopped; the USGS
refresh lived inside the event loop, so the pipeline froze while the web server
kept serving an hours-old snapshot as if it were live. Every liveness signal we
had was derived from the thing that had died. There is now a `health` block
built on the one independent signal — the MCU heartbeat — shown as a red badge
on the public page and a `STATION DEGRADED` banner on the dashboard.

**A feature was fake for weeks.** The dominant-frequency estimate compared the
sign of a *centered* sample against an *uncentered* one, on a vector magnitude
that is never negative, so it reported ~25 Hz whatever the ground did. Replay
hid it, because replay synthesizes that field analytically. Real taps now give
2.6 / 5.0 / 10.6 Hz.

**Our attenuation law was wrong by a factor of 38.** Checked against **12,324
PGA values actually recorded by USGS ShakeMap stations** during 40 southern
California earthquakes (M3.03–5.51, 3–200 km, 1,006 stations), the law this
repository used over-predicted ground motion 37.9×, uniformly across magnitude
and distance. Refitting the same form gives `0.867·M − 1.740·log10 R − 3.305`,
scatter 0.390 log10, R² = 0.80. Every "what could it feel" statement made before
that check was optimistic by about two magnitude units.

## What is established, and what is not

**Established.** The station is autonomous: WiFi, its own power, no shell, no
attached computer; it detects, correlates, learns, serves a dashboard, publishes
to GitHub Pages every 20 minutes, and recovers from a power cut. The full
learning chain runs end to end and converges. Every detection is journalled with
what each model predicted *before* it learned that point, so the project can
score itself out-of-sample instead of quoting training residuals.

**Not established: that this sensor can measure a real earthquake.** Zero
matches so far, and that is not a correlation bug — it is the threshold.

*Replay figures measure the software, not the instrument.* In `--replay` the
readings are synthesized from cataloged magnitude and distance through the
pre-refit law above, so its amplitudes are 38× too large — kept deliberately,
since corrected ones would sit under the trigger floor and the demo would show
nothing — and the calibration then fits the inverse of that same law. It proves
the pipeline is correct and stable; it is circular by construction and its
amplitudes are not physical. The
dashboard's RMSE is worse than that: an in-sample training residual computed
with the *true* catalog distance, while live operation feeds it an *estimated*
one. `python audit.py` replays the journal for genuine out-of-sample residuals:

| Estimator | run A (11 pts) | run B (27 pts) |
|---|---|---|
| In-sample, true distance — *what the panel shows* | 0.20 Mw | 0.18 Mw |
| Out-of-sample, true distance | 0.30 Mw | 0.21 Mw |
| Out-of-sample, **estimated** distance — the operational path | 1.10 Mw | 0.26 Mw |

Out-of-sample is consistently worse than the panel, which is the expected
direction. But 1.10 against 0.26 for the same code is not a measurement: at ten
points, prequential scoring is dominated by predictions made with a model that
had barely learned anything. **The instability is the finding.** These numbers
show the method, not an accuracy.

**The detection threshold, measured.** There is no absolute g threshold in the
firmware — only an STA/LTA ratio — so the floor is a property of the site, and
had to be measured rather than looked up. Over 163 events the smallest peak
acceleration that has ever triggered is **0.0034 g**, 0.0044 g in the quietest
window. Through the refit law, that floor becomes a required magnitude, ±0.45
(1σ); below M3 it is extrapolation:

| | 10 km | 30 km | 50 km | 100 km | 160 km |
|---|---|---|---|---|---|
| Blind trigger needs | 3.1 | 3.9 | 4.3 | 4.9 | 5.3 |
| Retrospective search needs | 2.1 | 2.9 | 3.3 | 3.9 | 4.3 |

Crossed with the real catalog — 2,185 events of M ≥ 2 within 160 km over five
years — and converting the 0.39 log10 scatter into a per-event probability, the
blind trigger alone should see **2.0 to 9.8 genuine earthquakes a year** (the
range is unknown site amplification, ×1 to ×4). That is a mean wait of 37 to 184
days for **one** of the 8 points it needs, and a **6 to 28%** chance of a first
one before 13 September. The station is not waiting for "an earthquake"; it is
waiting for one of a handful of specific ones.

**Which is why the trigger stopped being the only way in.** A blind detector has
to be right about roughly 170,000 windows a day, and that is what forces its
threshold so far above the noise — not the sensor. But the USGS publishes the
origin time of every earthquake, so the station now also records a continuous
envelope of the ground motion and goes back to look at the instant the waves must
have arrived. A handful of windows per earthquake instead of 170,000 a day buys
the same confidence much closer to the noise, and the test can average over the
whole wavetrain instead of reacting inside half a second. Measured on this
station's own noise: **a factor 7 to 8 in amplitude, one full magnitude unit** —
five times what the seismic band-pass was worth, for no hardware and no money.

| | earthquakes felt per year | mean wait | before 13 September |
|---|---|---|---|
| Blind trigger only | 2.0 – 9.8 | 37–184 days | 6–28% |
| **Plus retrospective search** | **9.9 – 36.9** | **10–37 days** | **28–70%** |

**And the two are not the same claim, so this repository never merges them.**
A shake the station triggered on by itself is a detection. A shake found because
the catalog said which second to examine is a *confirmation* — real evidence that
the ground moved, but the station did not find it unaided. The journal tags every
record, the dashboard and the public page show two categories, and the 0-of-8
calibration count admits only the first kind. The distinction is what makes the
approach defensible; erasing it would make the numbers a lie.

Two limits travel with those figures. The retrospective threshold is only
reachable when the site is at rest — measured, the envelope wanders by a factor
4 during a busy hour and by 3% during a quiet one — and this site is at rest
about half the time, which is what the table above assumes. And the search cannot
reach back before it was installed: the station kept no continuous record until
1 September, only the shakes that crossed the trigger, which are precisely the
wrong ones.

**A station that knows what it misses.** Zero detections is an ambiguous
result: it can mean a quiet catalog or a station that stopped working, and
until now nothing here could tell those apart. The station now audits itself
against the catalog. For every cataloged earthquake it computes what the refit
law says should have arrived here — that is a *prediction* — and reads the noise
it was actually sitting in at that instant out of its own continuous recording —
that is a *measurement*, and it is what keeps the audit honest, because an
earthquake that arrived while somebody walked past the sensor was not detectable
and the tool has to say so instead of reporting a fault. Each event then lands in
one of five categories, and only one of them is a problem: **out of reach**
(normal, 99% of this catalog), **marginal**, **triggered**, **confirmed**, or
**should have been seen and was not**. Over the 30 days to 2 September: 20
cataloged events, **0 in the last category**, 12 out of reach for both channels,
and 8 within the retrospective search's reach but earlier than the recording.
Those 8 are the argument for the second channel written out as specific events
rather than as a rate. Method, validation against the published figures, and
why none of the per-event detail is published, in
[`docs/expected-vs-observed.md`](docs/expected-vs-observed.md).

Other limits, briefly: it **detects, it does not predict** — it says nothing
about earthquakes that have not happened. Calibration belongs to one spot;
move the box and it must reconverge. A single PGA is a noisy proxy for released
energy, so ±0.3–0.5 magnitude is the realistic ceiling. It is a neighborhood
strong-motion node, not a broadband observatory: no teleseisms. And the method
needs a busy region with a promptly published catalog — southern California is
close to the ideal case.

## What three of these would add

![One station measures a distance but no bearing, so it can only place the epicenter somewhere on a ring; three stations produce three rings that cross at a single point](docs/images/network.png)

One station recovers a distance and no bearing. The firmware reduces every
sample to the magnitude of the acceleration vector, which throws direction away,
and the P wave — the only arrival whose polarization points back to the source —
is far below the hundredths of a g it takes to trip this sensor. So the honest
output of one station is a ring. Three rings cross in one place, the way GPS
locates a receiver that no satellite knows the direction of.

What would make such a network installable is not the price of the sensor, it is
that nobody has to calibrate it: each node fits its own coefficients against the
catalog and adapts to its own soil, building and mount. **This is an argument
from geometry, not a demonstration.** There is one station, it has recognized
zero earthquakes, and nothing in that figure was measured or simulated.

## Run it in two minutes

No hardware needed. Replay mode pulls the genuine catalog for the last 24 hours
and drives the full pipeline with it, on synthetic amplitudes that are not
physical.

```bash
cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml

python main.py --replay       # then open http://localhost:8000
```

Watch the panel: the amplitude model flips to *calibrated*, the distance model
to *ready*, the noise filter starts telling earthquakes from trucks.

![Calibration converging: the panel goes from learning 1/8 to calibrated while red device estimates fill the map](docs/video/calibration-timelapse.gif)

Then grade it honestly, on the journal rather than on the panel:

```bash
python audit.py                      # out-of-sample residuals
python audit.py --include-synthetic  # also score --replay events (circular)
```

Other modes: `python main.py --mock` (synthetic shakes), `python pipeline.py
--mock` (headless), `python main.py` (real sensor). On the board it is one
command, because the repository *is* an App Lab App:

```bash
arduino-app-cli app start ~/ArduinoApps/sismo-la    # builds, flashes, runs both
arduino-app-cli app logs  ~/ArduinoApps/sismo-la    # both halves, interleaved
```

## Inside the node

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
 │   frequency per event     │ - noise filter (online         │
 │ - one event ──────────────┼─►  logistic regression)        │
 │   over the Bridge         │ - Leaflet dashboard + publish  │
 └───────────────────────────┴────────────────────────────────┘
                    USGS: https://earthquake.usgs.gov/fdsnws/event/1/
```

The MCU runs STA/LTA, the trigger seismic networks have used for decades: a
0.5 s average of signal energy against a 10 s average, with the long-term
average frozen during an event so the earthquake cannot contaminate its own
noise floor. Hardware: an UNO Q, a Modulino Movement on the Qwiic connector, and
a 5 V / 3 A supply — no breadboard, no soldering. Mounting matters more than the
sensor; see [`docs/hardware.md`](docs/hardware.md).

UNO Q gotchas that cost us days, written up in
[`docs/getting-started.md`](docs/getting-started.md): the Qwiic connector is on
**`Wire1`**, the MCU's `Serial` goes to the D0/D1 pins rather than USB, and the
MCU↔Linux Bridge needs the board's `arduino-router` and the bridge library to be
version-matched.

## Autonomous operation

The station needs WiFi and USB-C power, nothing else. `python/main.py` pushes a
JSON snapshot on a timer (`publish:` block in `config.yaml`: HTTP POST, file
write, or any upload command), and [`web-remote/`](web-remote/) reads it — a
map, and [`data.html`](web-remote/data.html) for the numbers behind it including
every shake that was only a passing truck. Published at
**<https://medialoco.github.io/sismo-la/>**: no backend, no build step, nothing
to pay for.

**The published snapshot carries no coordinates.** The page outlines the
catalogued events the station recognized and plots the magnitude it read against
the magnitude USGS published; none of that needs to know where the box is. It
also removed a dishonesty — the old red epicenter marker only landed somewhere
because it borrowed the bearing from the event it was supposed to be estimating.
Set `publish.include_location: true` to put the station back on the map.

Nothing lives only in memory: every shake is appended to `event_log.jsonl` next
to the three model state files, on the host filesystem rather than the
container's, so the record survives restarts, reboots and reinstalls.

## Repository layout

```
sismo-la/
├── app.yaml                   # App Lab manifest (name, ports, bricks)
├── python/                    # runs on the Dragonwing MPU (Debian)
│   ├── main.py                # entry point: loops + dashboard + publisher
│   ├── pipeline.py            # detection/correlation helpers + headless CLI
│   ├── usgs.py                # USGS FDSN client
│   ├── calibration.py         # amplitude model + distance model (persisted)
│   ├── classifier.py          # online quake-vs-noise logistic regression
│   ├── envelope.py            # continuous envelope, one CSV per UTC day
│   ├── retro.py               # search at the arrival time the catalog implies
│   ├── expected.py            # what should have been felt, vs what was
│   ├── audit.py               # out-of-sample scoring from the journal
│   └── dashboard/index.html   # operator dashboard
├── sketch/                    # runs on the STM32U585 MCU (Zephyr)
├── deploy/                    # root-free autostart: watchdog sidecar
├── docs/                      # architecture, calibration, hardware, story
└── web-remote/                # published on GitHub Pages
```

## Status

- [x] Node autonomous on real hardware: detect → correlate → learn → publish.
- [x] Survives a power cut without a human (4 min 24 s to a serving dashboard).
- [x] Detection threshold measured, and the expected detection rate with it.
- [x] Attenuation law refitted on 12,324 real ShakeMap amplitudes.
- [x] Continuous envelope recorded, and searched retrospectively at the arrival
      time the catalog implies — a factor 7 to 8 in amplitude, kept strictly
      apart from what the station triggers on by itself.
- [ ] **First genuine earthquake recognized — 0 of 8.** Everything else waits
      on this.
- [ ] First retrospective confirmation — 0 so far, the search went live on
      1 September and has no earlier envelope to read.
- [x] Self-audit against the catalog: every cataloged event classified as out of
      reach, marginal, seen, or **should have been seen and was not**. Currently
      0 in the last category, so the silence is the catalog and not a fault.
- [ ] Calibration curve from real recordings, with held-out residuals.
- [ ] Contest video: replay mode plus a live tap.

Entry for the
[Invent the Future with Arduino UNO Q and App Lab](https://www.hackster.io/contests/invent-the-future-with-arduino-uno-q-and-app-lab)
contest — category **Best Social Impact**, submissions close
**September 13, 2026**. Story in
[`docs/hackster-story.md`](docs/hackster-story.md).

## License

MIT — see [`LICENSE`](LICENSE).
