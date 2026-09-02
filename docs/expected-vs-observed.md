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

Over the **30 days to 2026-09-02**, 20 cataloged events of M ≥ 2 within 160 km:

| | |
|---|---|
| should have been seen and were not | **0** |
| out of reach for both channels | 12 |
| within the retrospective channel's reach but before the recording began | 8 |

So there is no fault to chase, and the eight events in the third row are the
concrete form of the argument for the retrospective search: they are the ones
the station would now have a real chance at, having had none a fortnight ago.
Their predicted probabilities run up to 0.75 at the optimistic end of the site
range and stay under 0.06 for the blind trigger — which is the whole point of
the second channel, stated for the first time as specific events rather than as
a rate.

Two things about that table. It slides: it is a rolling window over a catalog
that gains an event every day or two, so the split moves and only the first row
is worth watching. And it is the **remote** audit, which assumes the at-rest
floor everywhere; once the tool runs on the station itself the noise column
becomes measured for everything after the recording began, and an event that
arrived during a busy hour can move from marginal to out of reach on that
alone.

Over five years, the same arithmetic says how that rate is actually made up:

| | events | share |
|---|---|---|
| in reach at the blind trigger, site ×1 (p ≥ 0.5) | 7 | 0.3% |
| marginal (0.1 ≤ p < 0.5) | 14 | 0.6% |
| out of reach (p < 0.1) | 2165 | 99.0% |

That is the sentence "1.98 detections a year" written out: the station is not
waiting for *an* earthquake, it is waiting for one of about twenty specific ones
in five years.

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
- **On the public page**, as one line of three integers, and a red badge if the
  third is not zero.
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
