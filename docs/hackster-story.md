# Contest video — storyboard

This file is the shot list. Cut the video from it. The Hackster project page
can reuse the same beats, in the same order.

Target length: **about 3 minutes**. Language: English. The station’s coordinates
are never on screen and never spoken.

Numbers as of 9 September 2026. Before the final cut, re-check against
`web-remote/station.json`: autonomous detections still 0, amplitude calibration
still 0 of 8, retrospective search now **6 cataloged events scanned, 2 threshold
crossings** of which only `ci41540608` is real, and the audit back to **0 missed**.

Two things moved on 9 September and shot 7 depends on both. The 6 September miss
(`ci41542024`) was **withdrawn** when USGS revised it to M3.07 and relocated it
deeper, which dropped the pessimistic detection probability under 0.5. And the
retrospective threshold was crossed a second time, on an M2.33 whose expected
shaking was 33x below the sensor's own noise: a **false confirmation**, the first
real instance of the 1-in-55 rate. Do not narrate either as a second success.

Shot 7 grew to hold that miss, which is the best material here, and the four
seconds each came out of shots 1, 2, 3 and 6 to keep the total at three minutes.

Existing assets that drop in without a reshoot:

| File | Shot |
|---|---|
| `docs/images/how-it-works.png` | 2 |
| `docs/images/public-map-confirmed.png` | 5 |
| `docs/images/public-data-confirmed.png` | 5 |
| `docs/video/calibration-timelapse.mp4` | 6 |
| `docs/images/dashboard-live.png` | 6 hold |
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
> two thousand earthquakes of magnitude two or more within a hundred and sixty
> kilometres of a station like this.
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
>
> The obvious objection is that if you are told which second to examine, you
> will always find something. So watch what it does when there is nothing to
> find. It has examined six cataloged earthquakes. Four times it was handed the
> exact second, it had the recording, and it returned nothing: the shaking those
> four could deliver here was smaller than the sensor's own electrical noise.

*One event, one point.* Do not say “the station detected its first earthquake.”

*Protect the last paragraph.* It answers the first question a sceptic asks. If
the cut runs long, take the seconds out of shot 6, not out of this.

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

*On screen.* The operator dashboard on the LAN, which prints calibration **0 / 8**
and the audit counts in full. Neither public page draws them: `9 · 6 · 0` reads as
a score of six out of nine, and a lone `1 missed` reads as a broken device, so
they stay machine-readable in `station.json`. The 6 September miss is **no longer
in the live counts** — shoot it from `retro_state.json` or from the git history of
`station.json`, and say it was withdrawn. For the false confirmation, shoot the
bare count on the front page and the two rows on `data.html`: **as of 9 September
neither page carries any caveat** — the wording was removed that morning, so
nothing on the site marks which of the two crossings is false. The voice-over is
now the only place the distinction is made, which is why the lines below say it
in the first person.

The voiceover carries the meaning here, because the number has no caption to lean
on. Say what `missed` is before showing it.

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
> noise it was sitting in. Over the thirty days to the second of September:
> nineteen events examined, one confirmed, none that should have been seen and
> were not.
>
> Then, on the sixth of September, that last number left zero. The catalog
> published another magnitude three point two, this one closer in. The law said
> the shaking should have cleared the threshold, so the station raised the flag
> itself: an earthquake it should have seen, and did not. It published that
> against itself half an hour later, with nobody asking.
>
> Reading the recording afterwards, nothing had arrived. The trace after the
> earthquake looks like the trace before it. The prediction sat on the optimistic
> side of a law that scatters by a factor of two either way, and this ground moved
> less than average. The nearer earthquake was invisible and the further one was
> found — which is what tells you the first result was luck, not skill.
>
> Three days later the catalog revised that earthquake down, and the flag came
> back down with it. Nothing the station measured had changed. That is the price
> of using a referee you do not control: it can take back what it gave you.
>
> And the same week, the second channel crossed its threshold on an earthquake
> far too small and too distant to have reached this sensor at all. A false
> alarm, the first one, and it arrived a day after we finished measuring how
> often to expect them: about one time in fifty.
>
> So the counter on the public page says two confirmations, and only one of them
> is real. You are hearing that from me, not from the page. I could have deleted
> the row. I did not, because that count is what the frozen threshold actually
> produced, and a threshold you retune every time it embarrasses you has no
> error rate left to quote.

*This is the strongest thing in the project.* An instrument that reports its own
failure, unprompted, in public, is the whole argument of the build. The withdrawal
and the false alarm strengthen it rather than weaken it: both were found by the
station's own published numbers, and neither was hidden. If one shot survives a
re-cut, keep this one.

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
| 1 | 14 s | Macro Modulino + wide UNO Q | to shoot |
| 2 | 18 s | USGS + `how-it-works.png` | diagram ready |
| 3 | 14 s | Board + code split + one heartbeat line | to shoot |
| 4 | 22 s | Live tap, logs or dashboard | to shoot last |
| 5 | 44 s | USGS `ci41540608` + public map + `data.html` | stills ready |
| 6 | 12 s | `calibration-timelapse.mp4` | ready; VO must say “replay” first |
| 7 | 38 s | `station.json` / dashboard, 0 of 8, the withdrawn miss & the false confirmation | to capture |
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

Prices 1 September 2026. Node **$71–86**, about **$90** delivered: UNO Q $44–59,
Modulino $11.80, USB-C 5 V / 3 A ~$15. Same figures as the report's §4.1 — the
$11.80 is the sensor alone, and the station is never the twelve dollars.
