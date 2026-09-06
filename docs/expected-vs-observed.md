# What the station should have felt

Built **2026-09-02**. Answers the question an empty detection list cannot.

A station that has felt nothing is telling you almost nothing. The silence
covers two situations that call for opposite responses:

- the shaking never came close to the trigger, which is the normal outcome for
  99% of this catalog and says nothing about the station;
- the shaking *should* have reached it and did not, which is a fault — a dead
  sensor link, a threshold set wrong, a correlation gate that threw away a
  genuine pairing.

Until now nothing in the station could tell those apart, and the difference is
the difference between "wait" and "go and fix it". `python/expected.py`
computes, for every cataloged earthquake, what it should have delivered here and
what noise the station was actually sitting in when it arrived, and puts both
next to what the journal says happened.

## 1. Two kinds of number, and they are never mixed

Every figure this produces is tagged, in the code and in the output, because
they are not the same kind of claim.

| | | |
|---|---|---|
| **PREDICTED** | expected amplitude | `REF_GMPE`, the law refit to 12324 USGS ShakeMap PGA values (`python/pipeline.py`). Carries **0.39 log10** of scatter. |
| | detection probability | that scatter integrated over the threshold, with site amplification carried as a **×1 to ×4** range. |
| **MEASURED** | the noise at that instant | the median of the station's own recorded envelope over the three minutes before the arrival. |
| | `z` | how far the envelope actually stood above that noise when the waves should have landed. |
| | what happened | the journal: a trigger, a retrospective confirmation, or nothing. |

An expected amplitude is not an observation, and nothing derived from one is
ever counted as a detection.

**The measured noise is the point.** An earthquake that arrived while somebody
was walking above the sensor was not detectable, and a tool that ignored that
would report a fault where there was only a footstep. This site's ambient level
moves by a factor of four between a quiet night and a busy afternoon, so the
threshold has to move with it.

## 2. The threshold follows the measured noise

The blind trigger is STA/LTA, so the amplitude needed to fire it is proportional
to the level the long average is tracking. Two measurements fix the constant of
proportionality, and it is the only free parameter here:

- the smallest peak that has ever triggered this station is 0.0044 g before the
  band-pass, i.e. **0.00308 g** after it (the band-pass lowered the at-rest floor
  by a measured 1.43×, and a ratio detector's floor follows);
- the at-rest floor itself is **0.00036 g**, shown to be the sensor's own
  electrical noise in two independent bands.

Their quotient is **8.55**. So at any instant:

```
trigger floor  =  8.55 x (the envelope level measured at that instant)
retro floor    =  trigger floor / 7.4
```

The 7.4 is the amplitude gain of the retrospective search over the blind
trigger, simulated by `tools/retro-gain.py` with the estimator that runs on the
board. Feed the reference at-rest floor back in and the trigger floor comes out
at 0.00308 g, so this **reproduces** the station's published sensitivity rather
than competing with it.

## 3. It reproduces the published figures before producing new ones

```
python3 tools/expected-report.py --verify --station-from http://board:8000/api/state
```

Over the same five years and the same catalog as every published rate:

| | this tool | published | drift |
|---|---|---|---|
| blind trigger | 1.98 – 9.79 /yr | 1.98 – 9.79 | 0.1% |
| both channels, quiet fraction 0.47 | 9.84 – 36.85 /yr | 9.85 – 36.89 | 0.1% |

The magnitude table reproduces exactly (blind 3.1 / 3.9 / 4.3 / 4.9 / 5.3 at
10 / 30 / 50 / 100 / 160 km; retro one full unit below). `--verify` exits
non-zero on a mismatch, because a per-event probability computed by arithmetic
that no longer agrees with the station's own published sensitivity is worse than
no number at all.

## 4. Five categories, and only one of them is a problem

| verdict | what it means |
|---|---|
| `triggered` | the station fired on its own and paired the event. |
| `confirmed` | the catalog supplied the instant and the recording was found elevated there. Real ground motion, **not** an autonomous detection. |
| `out-of-reach` | too small or too far for either channel. Normal, and 99% of the catalog. |
| `marginal` | at the limit. The instructive category: this is where the station's sensitivity is actually decided. |
| **`missed`** | within reach and nothing happened. **This is a fault, not seismology.** |
| `no-coverage` | the recording did not cover the arrival instant. Neither a success nor a failure, and it must not be counted as either. |

The cuts are deliberately asymmetric. An event is only called `missed` when even
the **pessimistic** end of the site range (×1) makes detection more likely than
not, so the alarm can never be raised by the optimistic assumption alone; and it
is only called out of reach when even the **optimistic** end (×4) puts it under
10%. The middle is called marginal and left as such.

`no-coverage` exists because the continuous envelope only began on
2026-09-01. Almost the whole past is out of coverage and saying so is the honest
answer — counting it as a miss would manufacture faults, and counting it as a
success would manufacture competence.

One extra signal, reported and never counted: a shake in the journal at the
right instant, with a plausible amplitude, that carries no stored pairing. That
is a *pairing* gap rather than a missed detection — the catalog is polled on a
timer, so an event the USGS publishes after the shake was handled can never be
matched — and the two want different repairs.

## 5. What it says today

Over the **30 days to 2026-09-02**, 19 cataloged events of M ≥ 2 within 160 km:

| | |
|---|---|
| examined | 19 |
| confirmed by the retrospective channel | 1 |
| should have been seen and were not | **0** |

No fault to chase in that window, and the one confirmation — `ci41540608`, M3.2,
2026-09-02 — is the first event this tool ever had to classify as anything other
than out of reach or out of coverage. The audit had given it a real chance on the
retrospective channel and next to none on the blind trigger, and that is how it
turned out. Four days later the same arithmetic produced the opposite verdict on
another M3.2, which is the subject of the subsection below.

That table is a dated write-up. The public snapshot carries a different triple on
a rolling 336 hours, under `expected.summary` in
[`station.json`](https://medialoco.github.io/sismo-la/station.json): *examined /
recorded / missed*. Recorded is envelope coverage at that second, not a
confirmation. The window is shorter, so *examined* follows the last two weeks of
the catalog.

**Neither public page draws these three numbers.** Skimmed, `7 · 2 · 0` reads as a
score of 2 out of 7, which inverts their meaning — the middle count says how many
of the seven the station could check at all. They are published complete in
[`station.json`](https://medialoco.github.io/sismo-la/station.json) under
`expected.summary`, which the pages read, and defined in prose here and in the
paper.

Presentation took three attempts and the first two are recorded here so they are
not retried. **The status badge** went first, on the reasoning that the worst
number belongs in the loudest place; the 6 September miss disproved it within
hours, because a filled red badge reads as *this device is broken* and made a
correctly working audit indistinguishable from a sensor dying in silence — of the
two, only the second is a fault. **A captioned line** went second, then all three
counts defined one by one on the data page; both still required a visitor to read
a paragraph before a number stopped misleading them, which is the wrong trade for
a page that is skimmed.

None of this hides the failure, and the distinction is the medium rather than the
publication. The counts sit in a public file, unabridged, rewritten every
20 minutes, at the same address as everything else; anyone can read them, archive
them or watch them move, and that is what makes the claim refutable. What was
dropped is the graphic staging of a figure that does not survive separation from
its definition.

### The first miss, 2026-09-06

`ci41542024`, M3.2, 07:13:11 UTC, close in. Predicted shaking above the
**0.438 mg** retrospective floor of that second, and P(retro) clearing the 0.5 bar
at the pessimistic end of the site range: verdict *should have been seen*,
published 32 minutes after the event without anyone asking.

The predicted amplitude and the probability are **not** printed here, and must not
be added. The law inverts: either number beside the catalog magnitude yields the
hypocentral distance to the kilometre, and a second ring next to `ci41540608`'s
would locate the station — section 6. Recomputed from the public city-scale pin
the same event gives 0.304 mg, *under* the floor and therefore no alarm at all,
because the pin sits farther from the epicentre than the site does. Everything
measured, below, is reproducible from the published envelope.

What the record shows is that nothing arrived. The envelope covers the whole
arrival window with no gap; the median rms over the minute after the origin is
**0.5%** above the minute before, against **6.4%** for the confirmed event;
the strongest single second of the two-minute span sits *before* the earliest
possible P arrival; and `retro.significance` returned **z = 2.90** against `z_min`
4.0. Scanning window lengths from 1 s to 30 s keeps z between 1.95 and 3.05 — only
a 1 s window reaches 4.01, by picking one ordinary second of jitter, which is
precisely why `WINDOWS_S` starts at 5 s and why `Z_MIN` was calibrated against the
measured null with that multiplicity inside it. **Do not lower either to convert
this into a confirmation.**

So the miss is a statement about the *prediction*, not about the instrument. The
law gives a median and this site landed below it, which the 0.390 log10 scatter
allows freely. Read against `ci41540608` — same magnitude, nearly twice the
distance, **7.8×** its predicted amplitude, confirmed — the two events bracket
the site-to-site scatter from both ends and place the single confirmation on the
favourable tail. One event is not a rate; two events with opposite signs are
still not a rate, but they are a bound.

The write-up above is a **remote** audit: it assumes the at-rest floor
everywhere. On the station the noise column is measured after the recording
began, and an event that arrived during a busy hour can move from marginal to
out of reach on that alone. The reach breakdown is not published — section 6;
"in reach" and "out of reach" are distance bands. Earlier revisions of this
file and of the README printed that split.

Over five years the same arithmetic says how the rate is made up, and the shape
is what matters rather than the counts: a **fraction of a percent** of the
catalog is in reach at the blind trigger and the pessimistic end of the site
range, about as much again is marginal, and **99%** is out of reach. That is the
sentence "1.98 detections a year" written out — the station is not waiting for
*an* earthquake, it is waiting for one of a couple of dozen specific ones in
five years.

## 6. Why none of this is published

**A per-event detection probability is an epicentral distance in disguise.**
Given the magnitude, which the USGS publishes, the probability computed here is
a monotone function of hypocentral distance. A dozen of these rows trilaterate
the station exactly as the raw `distance_km` field did before `strip_location`
removed it from the published snapshot.

So the watchlist is an operator artefact. It appears on the local dashboard, on
the operator's own network, and `strip_watchlist` in `python/main.py` reduces it
on the way out — **unconditionally, not behind `include_location`**, because it
leaks a position whatever anyone thinks about publishing coordinates.

What is published is three integers: how many cataloged events were examined,
how many the recording covered, and how many should have been seen and were not.
The first two are properties of the catalog rate and of recording uptime,
neither of which is a distance. The third is the alarm, it is zero in normal
operation, and a count carries no geometry.

The reach counts are withheld too, and that is not excess caution: with a
handful of cataloged events in the window, knowing how many were "in reach"
narrows down which ones they were, and that is a distance band each.

## 7. Where it runs

- **On the station**, in the same thread as the retrospective search, which
  already holds the two things it needs — the envelope and the journal. Its
  catalog window is wider, `retro.audit_hours`, defaulting to the envelope
  retention: the search only revisits what the USGS may still revise, while the
  audit wants everything the recording can still be asked about.
- **On the local dashboard**, as one card. Counts, then a row for each `missed`
  and `marginal` event; the out-of-reach majority is counted and never listed,
  because listing it would bury the two verdicts that mean something.
- **In the public snapshot**, as `expected.summary`, three integers refreshed
  every 20 minutes. Neither public page draws any of them; see the note in
  section 5 for the three presentations that were tried and dropped.
- **From a laptop**, `tools/expected-report.py`, in four modes:

```bash
S=--station-from=http://board:8000/api/state
python3 tools/expected-report.py --verify $S            # trust check
python3 tools/expected-report.py --years 5 $S           # retrospective
python3 tools/expected-report.py --live --hours 336     # on the board
python3 tools/expected-report.py --from-api http://board:8000/api/state
```

Every one of those numbers is an epicentral distance under the skin, so the
station's position is not a nicety: a centre in the wrong place does not give an
approximate answer, it gives a different station's. The position is deliberately
absent from this repository, and the config kept here is a neutral placeholder,
so the first two modes take it from the running station over the local network
(or from `--lat/--lon`) and **refuse to run on the placeholder** rather than
print a plausible wrong table. This project already lost weeks to a centre
15.5 km off the real one; the refusal is the scar tissue.

The last mode exists because the board has no shell once it leaves USB, so the
dashboard port is the only thing left to ask. It is a weaker audit and says so:
no envelope travels over HTTP, so the noise is assumed rather than measured, and
the pairings come from a snapshot list rather than from the journal. A `missed`
found that way is a lead, not a finding.

## 8. Limits, stated rather than glossed

- **The retrospective column is optimistic in a busy period.** Its real test is
  significance against the local *dispersion*, and dispersion grows faster than
  the median when the site is active. Scaling its floor by the measured median
  therefore flatters it exactly when the site is noisy. Read `p_retro` as an
  upper bound whenever the measured noise is well above the at-rest floor.
- **The ×1 to ×4 site range dominates everything.** It is not a rounding error:
  station-to-station scatter is 0.347 of the fit's 0.390 log10, so site response
  dominates, and an unknown indoor mount makes it unknowable. This is why the
  output is a probability range and never a verdict of "would have been felt".
- **Below M3 the ground-motion law is extrapolation.** The smallest earthquake
  in the 12324-record fit is M3.03, and the magnitude slope is itself unsettled
  — it moves from 0.87 to 1.00 when the fit is restricted to M < 4.5, which is
  precisely this station's range.
- **The constant 8.55 rests on a single measurement** of the smallest peak that
  ever triggered, over 163 events. It will move as more of the catalog is
  crossed, and the whole scale moves with it.
- **A `missed` verdict is a hypothesis about the station, not a proof.** It says
  the ground motion was probably above the floor; the floor itself is a model of
  a detector, and 0.39 log10 is a wide distribution. Two in a row mean more than
  one.
- **The catalog is not a fixed reference.** A revision can move the origin time,
  the distance or the depth — which together place the arrival window — or the
  magnitude, which sets the amplitude veto. `ci41540608` went from M3.36 to
  M3.20 at 78.5 h. So the retrospective search re-scans every catalog event for
  as long as its envelope survives, 14 days, in full rather than patching the
  stored magnitude: a verdict can flip in either direction, and a confirmation
  does not outlive a revision that would have refused it. This also covers an
  event first announced under `usgs.min_magnitude` and revised above it, which
  would otherwise never have been scanned at all — and would then have been
  counted `missed` here, since this audit computes its own significance but
  takes `confirmed` from the search's findings.
