# Hackster story draft (English) — ready to paste

Draft for the project page on hackster.io, following the structure in
`hackster-submission.md`. Numbers are current as of 1 September 2026; refresh
the calibration count and the detection status before submitting.

---

## Name

**Can a neighborhood run its own seismic network? Testing the $80 node that
would make it possible**

> The rules ask for a sentence that says *what it does*. This one says what it
> tests, which is stronger here: the project's result is an answer to a
> question, including where the answer is "not yet". Alternates:
> - *An $80 Arduino node that learns to measure earthquakes from the USGS catalog*
> - *The cheap seismograph that grades itself against every quake it feels*

## Pitch

A neighborhood seismic network needs one thing to be possible: a node cheap
enough to give away that can still detect an earthquake and put a number on it.
This Arduino UNO Q station tests that condition in Los Angeles — it checks every
shake it feels against the USGS catalog, works out its own calibration from the
matches, and reports honestly how far it gets.

## Categories (max 3)

Monitoring · Data collection · Social impact

## Difficulty

Intermediate

## Things

- Arduino UNO Q 2 GB (ABX00162)
- Arduino Modulino Movement (ABX00101, LSM6DSOX IMU) + bundled Qwiic cable
- USB-C power supply, 5 V / 3 A (3 A is a requirement, not a suggestion)

---

## Story

### 1. Who does not have an instrument, and why it matters

Nearly ten million people live in Los Angeles County, on top of one of the
most active fault systems in the world. The county is not under-instrumented: hundreds of
professional stations record it, and the USGS publishes magnitude, location and
depth minutes after every event. Over five years, 2,184 earthquakes of M ≥ 2
occurred within 160 km of this station.

What almost nobody has is an instrument of their own. Seismic hardware is
institutional — sited, calibrated and maintained by organizations. A
research-grade station is a five-figure item once installed. The cheapest
citizen instrument with a public price is a Raspberry Shake: $294.99 for the
board, $584.99 turnkey (raspberryshake.org, 1 September 2026). That is a real
price for a school; it is not a price at which a street covers itself.

That gap is what this project is about. Not "here is a seismograph", but:

> **Could a neighborhood run its own network? The prerequisite is a node cheap
> enough to hand out that still detects an earthquake and estimates its size,
> unattended, with nobody there to calibrate it. Is that possible?**

I built one node and ran it continuously to find out. Below is what it costs,
how it teaches itself, what happened when it actually ran, and exactly how far
it got — including the part it has not reached.

### 2. What a node costs

Prices checked 1 September 2026.

| Part | Price |
|---|---|
| Arduino UNO Q 2 GB (ABX00162) | $59.00 at store.arduino.cc, $44.00–45.20 at DigiKey / PiShop / Farnell |
| Modulino Movement (ABX00101) | $11.80 at store.arduino.cc |
| USB-C supply, 5 V / 3 A | about $15 |
| **Total** | **$71–86**, call it $75–90 delivered |

I want to be precise about this because I got it wrong first: an early draft of
this project said "$25 a node". That figure was never substantiated — the UNO Q
alone costs more than that — so it is gone. **A node is $75–90.**

The argument does not need the exaggeration. $80 against a five-figure
professional station is two orders of magnitude; $80 against the cheapest
citizen alternative is roughly seven times cheaper. And the component that
actually senses the ground is $11.80. Nearly all of a node's cost is the
computer that learns — which is exactly the part the next paragraph is about.

### 3. The idea: the answer key is free

![How Sismo-LA calibrates itself](images/how-it-works.png)

A MEMS accelerometer feels the ground move but has no idea how big the
earthquake was. It is uncalibrated, and calibrating a seismic instrument
normally takes a shake table or a professional station standing next to it —
which is precisely the cost that keeps these things institutional.

In Los Angeles it takes neither, because the reference already exists, is free,
and arrives within minutes:

1. The sensor detects a shake and reduces it to amplitude (PGA), duration and
   dominant frequency.
2. The Linux side asks the USGS API: was there a real earthquake near me just
   now?
3. If yes, that pair — my measurement against the official magnitude and
   distance — is one calibration point.
4. A regression over those points becomes this station's own transfer function,
   `M ≈ a·log10(PGA) + b·log10(R) + c`.

The coefficients are not universal constants. They absorb this sensor, this
mount, this building, this soil — which is the whole point: a network of these
would need no laboratory and no site survey, because every node works out its
own coefficients where it stands. The same loop labels training data for a
noise filter at no extra cost: matched shakes are earthquakes, unmatched ones
are trucks.

### 4. How it is built

The Arduino UNO Q is two computers on one board, and this application needs
exactly that split:

- the **STM32U585 MCU** (Zephyr) samples the IMU at 100 Hz and runs **STA/LTA**,
  the trigger real seismic networks have used for decades — a 0.5 s energy
  average against a 10 s one, with the long-term average frozen during an event
  so the earthquake cannot contaminate its own noise floor. It emits one compact
  message per event: peak acceleration, duration, dominant frequency.
- the **Qualcomm Dragonwing QRB2210 MPU** (Debian) does WiFi, the USGS feed, the
  correlation, the three models, the dashboard, and the publishing.

The only wiring is the Modulino Movement plugged into the Qwiic connector with
the 5 cm cable in the box. No breadboard, no soldering.

> Gotchas worth knowing on the UNO Q: the Qwiic connector is on `Wire1`, not
> `Wire`; the MCU's `Serial` goes to the D0/D1 header pins rather than USB, so
> events travel over the Bridge; and the board's `arduino-router` must be
> version-matched with the bridge library or nothing arrives at all.

### 5. What happened when it actually ran

This is the part I would want to read. Five episodes from the logs, picked
because each says something about putting these in people's homes.

**Moving the box cut false detections by 86%, without touching the code.** On a
desk the station triggered 22.6 times an hour. Moved to a better mount, 3.2 —
while the noise floor barely moved, 0.00087 g to 0.00066 g. Coupling decides
whether a home node is usable, not firmware. It also gives a criterion an owner
can act on: the trigger rate on the dashboard responds to placement by nearly an
order of magnitude, so "put it somewhere quieter" is an instruction with visible
feedback.

**It came back from a power cut on its own.** Getting there took an actual
diagnosis rather than a guess: at boot, Docker starts the container, and one
second later App Lab's daemon stops it — App Lab has no notion of an app that
should still be running — and Docker records that as a *deliberate* stop, so
from the following boot it does not even try. Systemd would fix it but needs
root; cron would fix it except that the board account's password is expired, so
PAM silently refuses every job and no log is written at all. What works is a
watchdog sidecar container, because the Docker daemon runs as root from boot and
never consults PAM. Verified on a real unplug: **4 min 24 s from power-on to a
serving dashboard**. A later 5 h 43 min outage confirmed the microcontroller
reboots straight into its own flash unaided.

**The station went blind and nothing said so.** The MCU stopped; the USGS
refresh lived inside the event loop, so with no shakes arriving the pipeline
froze — while the web server happily kept serving a snapshot from hours earlier
as though it were live. Every liveness signal in the system was derived from the
thing that had died. There is now a health block built on the one independent
signal, the MCU heartbeat, shown as a red badge on the public page and a
`STATION DEGRADED` banner on the operator dashboard. For an unattended device,
"is it lying to me?" turned out to be a more important question than "is it
up?".

**A feature was fake for weeks.** The dominant-frequency estimate compared the
sign of a *centered* sample against an *uncentered* one — on a vector magnitude,
which is never negative — so it reported ~25 Hz regardless of the signal. Replay
mode never caught it, because replay synthesizes that field analytically. Real
taps now give 2.6, 5.0, 10.6 Hz.

**Our attenuation law over-predicted ground motion by a factor of 38.** I
checked it against 12,324 peak accelerations actually recorded by USGS ShakeMap
stations during 40 southern California earthquakes (M3.03–5.51, 3–200 km, 1,006
distinct stations). The bias was uniform across every magnitude and distance
bin. Refitting the same form on that dataset gives
`0.867·M − 1.740·log10 R − 3.305`, scatter 0.390 log10, R² = 0.80. Consequence:
every "what could this feel" estimate I had made before that check was
optimistic by about two magnitude units. The corrected law is what section 6
uses. The demo replay still runs on the old one, on purpose — see the caveat
below.

### 6. Results: half the condition is met, and the other half is measured

**What is established.** The station runs unattended in Los Angeles on its own
power — no shell access, no attached computer. It detects, correlates against
USGS, keeps a journal, serves a dashboard, publishes a snapshot to GitHub Pages
every 20 minutes, and recovers from a power cut. The learning chain runs end to
end. Every detection is recorded together with what each model predicted
*before* it learned that point, so the project can score itself out-of-sample
rather than quote its own training residuals.

**What is not established: that this sensor can measure a real earthquake.**
The calibration record stands at **0 of the 8 matches** the amplitude model
needs. Every shake so far has been correctly identified as local noise.

That is not a correlation bug — it is the threshold, and this week it stopped
being a mystery. There is no absolute g threshold in the firmware, only an
STA/LTA ratio, so the floor is a property of the site and has to be measured.
Over 163 events, the smallest peak acceleration that has ever triggered is
**0.0034 g** (0.0044 g in the quietest window). Through the refit law, that
becomes a required magnitude, ±0.45 at 1σ, extrapolated below M3:

| | 10 km | 30 km | 50 km | 100 km | 160 km |
|---|---|---|---|---|---|
| M needed | 3.1 | 3.9 | 4.3 | 4.9 | 5.3 |

Crossed with the real catalog — 2,185 events of M ≥ 2 within 160 km over five
years — and converting the fit's 0.39 log10 scatter into a per-event
probability, this station should feel **2.0 to 9.8 genuine earthquakes a year**
(the range is unknown site amplification, ×1 to ×4). That is a mean wait of 37
to 184 days for *one* of the 8 points, and a 6 to 28% chance of a first one
before 13 September. The station is not waiting for "an earthquake", it is
waiting for one of a handful of specific ones.

### Then measuring it showed what was actually in the way

Chasing that threshold, I kept assuming the obstacle was the sensor. It is not,
or not only. A detector that watches blindly has to be right about roughly
**170,000 windows a day**, and every one of them is a chance to cry wolf. That
false-alarm budget — not the noise — is what forces the threshold so far above
the floor.

But the USGS publishes the origin time of every earthquake within minutes. So
the station stopped only *waiting* to be shaken. It now records a continuous
envelope of the ground motion, a peak and an rms every second, and when the
catalog announces an event it computes when the waves must have arrived and goes
back to read that instant. A handful of windows per earthquake instead of
170,000 a day buys the same statistical confidence far closer to the noise, and
the test can average over the whole wavetrain instead of having to react inside
half a second.

Measured on this station's own noise, both detectors simulated on the same
signals: **a factor 7 to 8 in amplitude, a full magnitude unit** — five times
what the band-pass filter was worth, for no hardware and no money.

| | earthquakes felt per year | mean wait | before 13 September |
|---|---|---|---|
| Blind trigger only | 2.0 – 9.8 | 37–184 days | 6–28% |
| **Plus retrospective search** | **9.9 – 36.9** | **10–37 days** | **28–70%** |

**And these are two different claims, so this project never merges them.** A
shake the station triggered on by itself is a detection. A shake found because
the catalog said which second to examine is a **confirmation** — real evidence
that the ground moved under the box, but the station did not find it unaided.
The journal tags every record, the dashboard and the public page keep two
separate lists, and the 0-of-8 counter admits only the first kind. Blurring that
line would make the whole write-up worthless, and it would be easy to do
accidentally, which is why the separation is enforced in the data structures
rather than in the prose.

Two limits travel with those figures. The low threshold is only reachable when
the site is at rest — measured, the envelope wanders by a factor 4 during a busy
hour and by 3% during a quiet one — and this site is at rest about half the time,
which is what the table assumes. And the search cannot reach backwards: the
station kept no continuous record before 1 September, only the shakes that
crossed the trigger, which are exactly the wrong ones.

The honest summary of the feasibility question is therefore: **the difficult
half of the condition is already met** — autonomy, self-calibration, continuous
correction against a ground truth, on a $80 node that nobody calibrated —
**and the missing half is measured rather than glossed over**. We now know which
magnitude is needed at which distance, which tells us exactly what to improve:
coupling first (86% of false triggers came off the table with a better mount),
then the trigger, then the site.

One more caveat I will state myself. The `--replay` mode, used for the demo
video, synthesizes sensor readings from cataloged magnitude and distance through
the *uncorrected* law — the one that over-predicts by 38× — and the calibration
then fits the inverse of that same law. Its amplitudes are therefore not
physical, and that is deliberate: at corrected amplitudes almost every cataloged
quake falls under the trigger floor and the demo shows an empty screen. Replay
proves the *software* is correct — matching, fitting, persistence, inference.
It measures nothing about the instrument.

### 7. What three of these would add

![One station draws a ring, three rings cross at a point](images/network.png)

One station measures a distance, never a direction. The firmware reduces each
sample to the magnitude of the acceleration vector, which throws direction away,
and the one arrival whose polarization would recover it — the P wave — is far
below the hundredths of a g needed to trip this sensor; what fires the trigger
are the S and surface waves behind it. So the honest output of a single station
is a ring, not a pin. Three rings cross in one place, the way GPS locates a
receiver that no satellite knows the direction of.

The part that would make such a network real is not the price of the sensor. A
conventional array needs chosen sites, instruments calibrated against a
reference, and people who know how to keep them honest. Here each node learns
its own coefficients from a public catalog and adapts to its own soil, its own
building, its own mount — so coverage could grow street by street instead of
budget by budget.

**Said plainly: this is an argument, not a demonstration.** There is one
station, and it has not yet recognized a single real earthquake. I did not
simulate a network to draw that figure; it is the geometry three stations would
use, and nothing more.

### 8. Why this pattern matters beyond earthquakes

**Cheap sensor + free authoritative feed = an instrument that calibrates
itself.** Nothing in that loop is specific to seismology. Air quality has
OpenAQ, weather has NOAA, and the same structure applies wherever an open,
promptly published reference exists: the device measures, the feed says what was
true, and the difference is training data nobody had to label.

Earthquakes are simply the case where the answer key is richest — and Los
Angeles the place where the question of who owns an instrument is least
abstract.

---

## Media checklist (per submission rules)

- [ ] Cover photo: the assembled device, clean background, 4:3, no text.
- [ ] Macro photo: Modulino on Qwiic.
- [ ] Fritzing schematic.
- [ ] Video: tap the desk → detection appears on the dashboard (live mode).
- [x] Video: replay mode filling the map — `video/calibration-timelapse.mp4`
      (and `.gif`), narration in `video-script.md` + `video/narration.srt`.
- [x] Screenshot: a USGS-correlated event in the side panel —
      `images/timelapse-4-calibrated.jpg`. Replayed catalog data, and the
      badge in the corner says so; do not present it as a live recording.
- [x] Diagram of the principle — `images/how-it-works.png`.
- [x] Diagram of the network geometry — `images/network.png`. A drawn argument,
      not a measurement: one station, one ring; three stations, one point.
