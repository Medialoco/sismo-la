# Contest video — shot list and narration

Target: **2 min 50 s**. Hackster judges skim, so the idea has to land in the
first fifteen seconds and the honesty has to land before the end.

Narration is in English (contest language). Subtitles live in
`docs/video/narration.srt`; the timings below match it exactly, so you can drop
both into any editor and they line up.

Two assets are already generated and can be dropped straight in:

| File | What it is | How it was made |
|---|---|---|
| `docs/images/dashboard-replay.png` | Dashboard, calibration converged | headless capture at 1440x900 |
| `docs/video/calibration-timelapse.mp4` | Calibration converging from zero | 75 frames, one every ~4 s, replayed at 8 fps |

## Golden rule for this video

Never say or imply prediction. The device **detects**. Anything that sounds
like forecasting an earthquake that has not happened yet is both false and, in
front of a seismology-literate judge, fatal.

Equally: when the replay timelapse is on screen, the narration must already
have said it is a replay. Showing a converging calibration without that word is
the one thing that would make the whole project look dishonest.

Two words, not one: **"a replay, and its shaking levels are synthetic and
deliberately too large"**. The replay generator keeps an attenuation law
measured to over-predict by 38×, because at real amplitudes almost nothing in
the catalog would trigger. So any shot cut from replay shows the software
working and must never be offered as evidence of what the sensor can feel.

And one more word that is not negotiable: the real earthquake in shot 5 was
**confirmed**, never *detected*. The station noticed nothing at the time; the
USGS supplied the second to examine and the station went back into its own
recording. Say "detected" there and the whole video becomes a claim the code
itself refuses to make. The narration below says it out loud, twice.

---

## Shot 1 — Hook (0:00–0:15)

*On screen:* macro shot of the Modulino sensor on the desk, then a wide shot of
the UNO Q wired up.

> Los Angeles gets more than two thousand earthquakes in three months. This
> twelve-dollar motion chip can feel the bigger ones. It just has no idea what
> it is feeling. A raw acceleration number means nothing on its own.

## Shot 2 — The idea (0:15–0:40)

*On screen:* split — the sensor on one side, the USGS website on the other.

> But in Los Angeles the ground truth is public. Minutes after every quake, the
> USGS publishes its magnitude and its location. So the device waits, feels a
> shake, then asks the catalog what that shake actually was. Match enough of
> them and it learns its own site-specific response. It calibrates itself,
> against real earthquakes, for free.

## Shot 3 — The two brains (0:40–1:00)

*On screen:* the board, then a quick cut to `sketch/sketch.ino` and
`python/main.py` side by side.

> The UNO Q is two computers. The microcontroller watches the accelerometer a
> hundred times a second and runs the classic seismology trigger, short-term
> over long-term average. The Linux side handles WiFi, queries the USGS,
> correlates, and serves the dashboard. They talk over the Arduino Bridge.

## Shot 4 — Live detection (1:00–1:25)

*On screen:* the terminal running `arduino-app-cli app logs`, then you tap the
desk. Wait for the heartbeat line first so the noise floor is visible.

> Here it is running on the board, on its own. Every ten seconds it reports its
> noise floor. Now watch when I tap the desk.
>
> Peak acceleration, duration, dominant frequency. It measured all three in
> real time, and correctly reports no match in the catalog, because a tap on a
> desk is not an earthquake.

## Shot 5 — The first real earthquake (1:25–2:02)

*On screen:* the USGS event page for `ci41540608`, then the public page — the
map circle with its dashed red outline — then the row in `data.html` under
"Earthquakes found afterwards". Hold on the `z` and the peak.

> On the second of September, this happened for the first time. The USGS
> published a magnitude three point two near Ontario, California.
>
> The station's trigger never fired. But it keeps a continuous recording, so it
> worked out when the waves must have arrived, went back, and looked. The
> shaking was there.
>
> Confirmed, not detected: without the catalogue there was nothing to look at.
> And the trigger itself would have needed three times the amplitude.

This is the only shot in the video made of live data, so let the screen do the
talking: no annotation, no arrows. Do **not** put the calibration counter in
frame here — it still reads zero of eight, correctly, because a confirmation is
not allowed to feed the magnitude model, and a viewer who sees the two together
without that explanation will read it as a bug.

## Shot 6 — Calibration converging (2:02–2:22)

*On screen:* `docs/video/calibration-timelapse.mp4`.

> This next part is a replay, not a live recording — the last day of real
> cataloged quakes fed through the pipeline as synthetic shakes, so twenty
> seconds stand in for weeks.
>
> Their amplitudes are deliberately unrealistic: this shows the software
> working, not what the sensor can feel.
>
> Red is what the device thinks. Colour is what really happened. The dashed
> line between them is its error, and it shrinks as the calibration learns.

## Shot 7 — The honest part (2:22–2:42)

*On screen:* the terminal, running `python audit.py`.

> Now the part most demos skip. The dashboard's residual is measured on the
> very points the model was fitted on, and it is handed the true distance. That
> flatters it.
>
> Every detection is journalled with what the model predicted *before* it
> learned that point. Replaying that journal gives the out-of-sample error, and
> it is several times worse. The tool that tells you that is in the repository.

## Shot 8 — Close (2:42–2:52)

*On screen:* the board on the desk, dashboard glowing in the background.

> It detects, it does not predict. One station cannot triangulate. But the
> pattern — a cheap sensor plus open public data — turns a toy accelerometer
> into something that improves every time the ground moves.

---

## Recording notes

- Shoot the tap shot **last**: it is the only one that needs luck and retakes.
- Shot 5 is live data on a station that keeps running, so grab the screenshots
  before anything else: the confirmed list is a rolling window and the row
  leaves it after `publish.window_days`.
- Let the heartbeat line appear on camera before you tap. It is what proves the
  sensor is live rather than a screen recording of nothing.
- Do not zoom the browser past 100 %: the map labels break up.
- If you re-record the timelapse, restart the app first so calibration starts
  from zero, otherwise the convergence is invisible.
