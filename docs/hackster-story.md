# Contest video — storyboard

This file is the shot list. Cut the video from it. The Hackster project page
can reuse the same beats, in the same order.

Target length: **about 3 minutes**. Language: English. The station’s coordinates
are never on screen and never spoken.

Numbers as of 2 September 2026. Before the final cut, re-check: autonomous
detections still 0, amplitude calibration still 0 of 8, confirmations still 1
(`ci41540608`).

Existing assets that drop in without a reshoot:

| File | Shot |
|---|---|
| `docs/images/how-it-works.png` | 2 |
| `docs/images/public-map-confirmed.png` | 5 |
| `docs/images/public-data-confirmed.png` | 5 |
| `docs/video/calibration-timelapse.mp4` | 6 |
| `docs/images/dashboard-replay.png` | 6 hold |
| `docs/images/network.png` | 8 |

`docs/video/narration.srt` follows the **Say** lines below. Nudge timings
after picture lock.

---

## Name / pitch (Hackster fields, also the first title card)

**Name.** A home seismograph on Arduino UNO Q that learns magnitude from the
USGS catalog.

**Pitch.** A MEMS chip records shakes; the official earthquake list says which
ones were earthquakes; from those pairs the station fits a magnitude and
distance model for this installation.

**Categories.** Monitoring · Data collection · Social impact

**Difficulty.** Intermediate

**Things.** Arduino UNO Q 2 GB (ABX00162) · Modulino Movement ABX00101
(LSM6DSOX) + Qwiic cable · USB-C 5 V / 3 A.

---

## Rules on the soundtrack

1. The device **detects**. It does not forecast.
2. A shake the STA/LTA trigger found by itself is a **detection**. A shake
   found because the catalog named the second is a **confirmation**. Shot 5
   is a confirmation. Say the word.
3. When the replay timelapse is on screen, say first that it is a replay and
   that the amplitudes are synthetic and deliberately too large.
4. Do not show the calibration counter (0 of 8) in the same frame as the
   Ontario confirmation without saying why it stayed at zero.

---

## Terms the voice-over must have defined before using

Introduce each word the first time it appears, then use it.

| Word | One-line definition (say this, or a close paraphrase) |
|---|---|
| MEMS | A tiny accelerometer chip. It measures acceleration, like a phone. |
| USGS catalog | The official list of earthquakes: magnitude, place, depth, time, within minutes. |
| Magnitude | The published size of an earthquake, written M3.2. |
| PGA | Peak ground acceleration: the largest acceleration in a shake, in *g*. |
| STA/LTA | Short-term energy over long-term energy. When the ratio jumps, the microcontroller declares an event. |
| Blind trigger | STA/LTA firing with no help from the catalog. |
| Envelope | A once-per-second trace of how strong the filtered ground motion was. The station can look back. |
| Confirmation | Envelope elevated at the arrival time the catalog implies. The trigger did not have to fire. |
| Detection | The blind trigger fired on its own. |
| Calibration | Fitting magnitude from PGA and distance on matched examples. Eight matches before the amplitude model is treated as usable. |

---

## Shot 1 — The chip does not know what it felt (0:00–0:18)

*On screen.* Macro of the Modulino on the Qwiic cable, then a wide of the UNO Q
on its mount. No dashboard yet.

*Say.*

> Los Angeles County sits on active faults. In five years the USGS listed about
> two thousand two hundred earthquakes of magnitude two or more within a
> hundred and sixty kilometres of a station like this.
>
> This twelve-dollar motion chip can feel the stronger ones. A raw acceleration
> number is not a magnitude. The chip has no idea what it felt.

*Do not say.* “Two thousand earthquakes in three months.” That number is wrong.

---

## Shot 2 — The official list is the answer key (0:18–0:42)

*On screen.* Split: sensor left, USGS event page right. Cut to
`docs/images/how-it-works.png`.

*Say.*

> The official list is public. Minutes after every earthquake, the USGS
> publishes magnitude, place and time. That list is the catalog.
>
> So the station records a shake, then asks the catalog whether an earthquake
> happened at that second. A match is one labelled example: what this box
> measured, against what USGS says it was.
>
> Enough matches and it fits a model for this installation — this sensor, this
> shelf, this building. After that, the model can run with the network
> unplugged. That fit is what we call calibration.

---

## Shot 3 — Two computers, one board (0:42–1:00)

*On screen.* The UNO Q, then a brief cut of `sketch/` next to `python/main.py`.
Optional: one heartbeat line in the logs (`sta/lta=… fs=95Hz`).

*Say.*

> The UNO Q is two computers. The microcontroller reads the chip a hundred
> times a second and runs STA/LTA: energy in the last half-second over energy
> in the last ten. When that ratio jumps, it sends three numbers: peak
> acceleration, duration, dominant frequency.
>
> The Linux side does WiFi, queries the catalog, stores the record, and serves
> the dashboard. They talk over the Arduino Bridge.

---

## Shot 4 — A detection that is not an earthquake (1:00–1:22)

*On screen.* Live dashboard or `arduino-app-cli app logs`. Wait for one MCU
heartbeat so the noise floor is visible. Tap the box. Hold on PGA, duration,
frequency, and `match: none`.

*Say.*

> This is the station running on its own. Every ten seconds the microcontroller
> reports that it is alive. That heartbeat is the only independent proof the
> sensor is up.
>
> I tap the box. Peak acceleration, duration, frequency — measured live. No
> match in the catalog: a tap is not an earthquake. That is a detection of
> noise, and the station says so.

*Shoot last.* Needs retakes. Do not zoom the browser past 100%.

---

## Shot 5 — Confirmation, not detection (1:22–2:00)

*On screen, in this order.*

1. USGS page for **`ci41540608`**, M3.2, Ontario, California, 2 September 2026,
   12:37:12 UTC.
2. Public map: dashed red outline — `docs/images/public-map-confirmed.png`.
3. `data.html` row under “Earthquakes found afterwards” —
   `docs/images/public-data-confirmed.png`. Hold z = 4.34 and peak 0.001095 g.

No arrows. No calibration counter in frame.

*Say.*

> On the second of September the catalog published a magnitude three point two
> near Ontario.
>
> The blind trigger never fired. It needed about three times the amplitude that
> arrived. But the station keeps a continuous envelope: a trace, once a second,
> of how strong the ground was. It computed when the waves should have arrived,
> went back, and read that second.
>
> The envelope sat four point three four dispersions above the previous
> minutes. We call that a confirmation: the ground moved, and the catalog
> named the second. Without the catalog there was nothing to look at. It is
> not a detection.

*One event, one point.* Do not say “the station detected its first earthquake.”

---

## Shot 6 — Replay: the software, labelled as such (2:00–2:22)

*On screen.* `docs/video/calibration-timelapse.mp4`. Badge or first line of VO
must land before the map fills.

*Say.*

> This part is a replay, not a live recording. Real catalog times, synthetic
> shaking, amplitudes deliberately about thirty-eight times too large, so the
> demo still crosses the trigger. It shows the software: matching, fitting,
> the dashboard. It does not show what the sensor can feel.
>
> Red is the device’s estimate. Colour is the catalog. The gap between them
> shrinks as the amplitude model takes points.

---

## Shot 7 — What the station still cannot do (2:22–2:42)

*On screen.* Public header or dashboard: **0 triggered · 1 confirmed**,
calibration **0 / 8**. Then, optional, `python audit.py` in a terminal.

*Say.*

> The amplitude model needs eight matched detections. The counter is still
> zero. Confirmations are not allowed into that fit: they are chosen for being
> a large wiggle next to the noise, so their amplitude is biased high.
>
> Over five years, a station like this should catch about two to ten genuine
> earthquakes a year on the blind trigger, more if it is also allowed to look
> back in the envelope. The first autonomous catch has not happened yet.
>
> The station also audits every cataloged event: expected amplitude versus the
> noise it was sitting in. In thirty days: nineteen events examined, one
> confirmed, none that should have been seen and were not.

---

## Shot 8 — Close (2:42–3:00)

*On screen.* Board in the room, dashboard in the background. Last two seconds:
`docs/images/network.png` (caption on the drawing already says it is geometry,
not a measurement).

*Say.*

> It detects events that have already happened. It does not predict. One
> station gives a distance, a ring on a map, not a pin. Three rings would
> cross. That has not been built.
>
> A cheap sensor plus an official public list: the box learns how the ground
> feels *here*, and it keeps that model when the internet is unplugged.

---

## Cut list (picture)

| # | Duration | Picture | Status |
|---|---|---|---|
| 1 | 18 s | Macro Modulino + wide UNO Q | to shoot |
| 2 | 24 s | USGS + `how-it-works.png` | diagram ready |
| 3 | 18 s | Board + code split + one heartbeat line | to shoot |
| 4 | 22 s | Live tap, logs or dashboard | to shoot last |
| 5 | 38 s | USGS `ci41540608` + public map + `data.html` | stills ready |
| 6 | 22 s | `calibration-timelapse.mp4` | ready; VO must say “replay” first |
| 7 | 20 s | 0 triggered · 1 confirmed, 0 / 8 | to capture |
| 8 | 18 s | Board + `network.png` | diagram ready |

## Recording notes

- Shot 5 stills are live published pages. The confirmed row leaves the public
  list after `publish.window_days`. The files above were taken while it was
  still there.
- Let the heartbeat print before the tap. That is what proves the IMU is live.
- Restart the app before any new timelapse so calibration starts at 0 of 8.
- Cover photo for Hackster is the physical station, 4:3, no text. It is not a
  dashboard screenshot.

## Cost card (optional lower-third, shot 1 or 8)

Prices 1 September 2026. Node **$75–90** delivered: UNO Q $44–59, Modulino
$11.80, USB-C 5 V / 3 A ~$15. A $25 figure used earlier was wrong.
