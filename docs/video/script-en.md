# Sismo-LA — narration, English

Read this aloud. Every number here was checked against `web-remote/station.json`
and the report on **9 September 2026**. Target length **3 minutes**.

Each shot is marked **SHOOT** (point the camera at a real object or a live
screen) or **SLIDE** (display `slides.html` fullscreen and film the screen).
Slide numbers refer to that deck.

Two rules that override everything else. The station's coordinates are never on
screen and never spoken. And the word for what happened on 2 September is
**confirmation**, never detection — the catalog named the second, the station did
not find it unaided.

---

## Cold open — 35 s — SLIDE 1

This is the piece to protect. If the edit runs long, cut anywhere else.

> I built a seismograph for about eighty dollars. The part that actually feels
> the ground costs twelve — the same kind of chip that knows when you turn your
> phone sideways.
>
> In eight weeks, it has not found a single earthquake on its own.
>
> I am telling you that because the box told me first. Every few minutes it
> checks the official earthquake list, asks whether it should have felt
> something, and publishes the answer — including every time the answer is no.
>
> A cheap sensor that reports a number is worth nothing. A cheap sensor that can
> be caught being wrong is an instrument.

---

## Shot 1 — the chip — 14 s — SHOOT

Macro of the Modulino on its Qwiic cable, then a wide of the UNO Q on its mount.
Put a fingertip or a coin in the macro frame: without a scale, "twelve dollars"
is just a word. No dashboard yet.

> Los Angeles County sits on active faults. Over five years the official
> catalog lists about two thousand earthquakes of magnitude two or more within a
> hundred and sixty kilometres of a station like this.
>
> This motion chip can feel the stronger ones. But a raw acceleration number is
> not a magnitude. The chip has no idea what it felt.

---

## Shot 2 — the answer key — 22 s — SLIDE 2, then 3

> The official list is public. Minutes after every earthquake, the United States
> Geological Survey publishes magnitude, place, depth and time. That list is the
> catalog, and this station does not control it.
>
> So the station records a shake, then asks the catalog whether an earthquake
> happened at that second. A match is one labelled example: what this box
> measured, against what the catalog says it was. Enough matches and it fits a
> model for this installation — this sensor, this shelf, this building.
>
> And here is the number that sets the whole problem. Crossed with five years of
> catalog, ninety-seven per cent of those earthquakes are beyond what this
> sensor can feel. A station in perfect working order spends almost all of its
> time reporting nothing.

---

## Shot 3 — two computers, one board — 14 s — SHOOT

The board, then a split of `sketch/` beside `python/main.py`. One heartbeat line
in the log is enough (`sta/lta=… fs=95Hz`). Terminal in a large font, browser at
100 %, never zoomed.

> The board is two computers. The microcontroller reads the chip ninety-five
> times a second and watches the energy in the last half-second against the
> energy in the last ten. When that ratio jumps, it declares an event and sends
> three numbers: peak acceleration, duration, dominant frequency.
>
> The Linux side does the network, queries the catalog, keeps the record and
> serves the dashboard.

---

## Shot 4 — a detection that is not an earthquake — 22 s — SHOOT

Shoot this last; it needs retakes. Let a heartbeat print **before** you tap the
box — that heartbeat is the only independent proof the sensor is alive. Then
hold on peak acceleration, duration, frequency, and `match: none`.

> This is the station running on its own. Every ten seconds the microcontroller
> reports that it is alive.
>
> I tap the box. Peak acceleration, duration, frequency, measured live. Then the
> station asks the catalog, and there is no match. A tap is not an earthquake.
> It says so, and it files it as noise.

---

## Shot 5 — confirmation, not detection — 40 s — SLIDE 4, 5, 6, 7

Slide 4 defines the two words before either is used. Then the event, then the
two published pages.

> Two words, and they must not be mixed. A **detection** is the trigger firing
> on its own. A **confirmation** is the station being told which second to
> examine, and finding the ground was moving there. One is discovery. The other
> is evidence.
>
> On the second of September the catalog published a magnitude three point two
> near Ontario, California.
>
> The blind trigger never fired. It needed about three times the shaking that
> arrived. But the station keeps a continuous envelope — a trace, once a second,
> of how strong the filtered ground motion was. It computed when the waves
> should have arrived, went back, and read that second.
>
> The envelope sat four point three four standard deviations above the previous
> minutes, against a threshold of four. That is a confirmation. Without the
> catalog there was nothing to look at.
>
> The obvious objection is that if you are told which second to examine, you
> will always find something. So watch what it does when there is nothing to
> find. It has examined six cataloged earthquakes. Four times it was handed the
> exact second, it had the recording, and it returned nothing — the shaking
> those four could deliver here was smaller than the sensor's own electrical
> noise.

---

## Shot 6 — the freeze — 14 s — SLIDE 8

New in this cut, and it is the single most checkable claim in the project.

> One more objection: it is easy to predict an earthquake after it happens. So
> the law that made that prediction was published to a public repository on the
> first of September at thirteen fifty-six, universal time — twenty-two hours
> before the earthquake. The commit history timestamps it. You do not have to
> take my word for any of this.

---

## Shot 7 — the replay, labelled as such — 12 s — `calibration-timelapse.mp4`

The first line of voice-over must land **before** the map fills.

> This part is a replay, not a live recording. Real catalog times, synthetic
> shaking, amplitudes deliberately about thirty-eight times too large so the
> demo still crosses the trigger. It shows the software working. It does not
> show what the sensor can feel.

---

## Shot 8 — what it still cannot do, and what it admitted — 45 s — SLIDE 9, 10, 11

The operator dashboard on the local network prints these; neither public page
draws them, because a bare `0 missed` reads as a broken device. Say what
`missed` means before showing it.

> The amplitude model needs eight matched detections before it is allowed to
> print a magnitude. The counter is still at zero, and confirmations are not
> allowed into that fit: they are selected for being a large wiggle next to the
> noise, so their amplitude is biased high by construction.
>
> The station also audits every cataloged earthquake against the noise it was
> sitting in, and publishes how many it should have caught and did not.
>
> On the sixth of September that number left zero. The catalog published another
> magnitude three point two, this one closer in. The law said the shaking should
> have cleared the threshold, so the station raised the flag itself: an
> earthquake it should have seen, and did not. It published that against itself
> thirty-two minutes later, with nobody asking.
>
> Reading the recording afterwards, nothing had arrived. The trace after the
> earthquake looks like the trace before it. The nearer earthquake was invisible
> and the further one was found, which is what tells you the first result was
> luck as much as skill.
>
> Three days later the catalog revised that earthquake down and moved it deeper,
> and the flag came back down with it. Nothing the station measured had changed.
> That is the price of using a referee you do not control: it can take back what
> it gave you.

---

## Shot 9 — the false alarm — 25 s — SLIDE 12

> And then the second channel crossed its threshold on an earthquake far too
> small and too distant to have reached this sensor at all. The shaking it could
> deliver here was thirty-three times below the chip's own noise. There was
> nothing to hear.
>
> It arrived one day after I finished measuring how often to expect exactly
> that: about one time in fifty-five.
>
> So the counter on the public page says two confirmations, and only one of them
> is real. You are hearing that from me, not from the page. I could have deleted
> the row. I did not, because that count is what the frozen threshold actually
> produced — and a threshold you retune every time it embarrasses you has no
> error rate left to quote.

---

## Shot 10 — what the measurement makes possible — 30 s — SLIDE 13

Do not let the video end on what one box cannot do. Eight weeks of measuring
produced a number, and the number is what makes a network designable instead of
imaginable. Every figure here is from §12 of the report; none of it is built, and
the voice-over must say so.

> One station was never the point. What eight weeks of measuring bought me is a
> number: exactly what this hardware can and cannot hear. And that number is what
> lets you size a network.
>
> Fifty of these is about four thousand dollars. Fifty also changes the physics of
> the problem, because the thing drowning the signal is household noise, and
> household noise is local — a footstep happens in one room, an earthquake reaches
> every neighbour within seconds. Require two nodes to agree and most of that
> noise disappears, which means the threshold can come down instead of up.
>
> Coverage changes too. One node is deaf across almost all of its own territory.
> In a network, every point on the map gets the sensitivity of its nearest sensor
> instead of the average one — that gain costs nothing but geometry.
>
> And with synchronised clocks, arrival times cross: an epicentre instead of a
> ring, and hundreds of amplitude readings giving a map of what was actually
> felt, which is the only thing anyone needs in the first minutes.

*Say the reservation, in one line.* None of it is built, the microcontroller's
clock drifts by eleven hundred parts per million, and at fifty sites the hardware
stops being the expensive part.

---

## Shot 11 — close — 14 s — SHOOT, then SLIDE 14

The board in the room, dashboard behind it. Last four seconds on slide 14.

> It detects events that have already happened. It does not predict.
>
> A twelve-dollar sensor and an official public list. The box learns how the
> ground feels here, it keeps that model when the network is unplugged, and it
> tells you when it was wrong. The code, the data and the report are all public.

---

## Before the final cut

Re-check these against `web-remote/station.json`, because one busy day moves the
last two by half:

| Claim | Value on 9 September |
|---|---|
| autonomous detections | 0 |
| amplitude calibration | 0 of 8 |
| cataloged events scanned | 6 |
| threshold crossings | 2, of which **one** is real |
| audit `missed` | 0, after the 6 September withdrawal |
| journal | 10 756 lines / 10 141 triggered |
| noise filter | 0 earthquakes / 10 789 noise |

`narration.srt` in this folder is **stale — it dates from 3 September** and
predates the miss, the withdrawal and the false alarm. Do not cut against it;
regenerate it once the picture is locked.
