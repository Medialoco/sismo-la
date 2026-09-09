# Shoot package — contest video

Three things live here, plus the assets already produced.

| File | What it is |
|---|---|
| [`script-en.md`](script-en.md) | The narration, English, shot by shot. Read it aloud. |
| [`slides.html`](slides.html) | 14 slides to display fullscreen and film off the screen. |
| `calibration-timelapse.mp4` | The replay. The voice-over must say "replay" **before** the map fills. |
| `narration.srt` | **Stale, 3 September.** Predates the miss, the withdrawal and the false alarm. Do not cut against it. |

The storyboard with the shot durations and the vocabulary rules stays in
[`../hackster-story.md`](../hackster-story.md). This folder is the working
material cut from it.

## Order of operations

1. **Shoot the physical shots first**, while daylight lasts: the sensor macro
   (shot 1), the board and the code (shot 3), the board in the room (shot 10).
   Leave shot 4, the live tap, for last — it needs retakes.
2. **Record the voice** over those, or separately and lay it under. The cold open
   is the piece to protect; if the edit runs long, cut anywhere else.
3. **Film the slides** for everything that is not a physical object: open
   `slides.html`, press `f` for fullscreen, `c` to hide the slide counter, then
   walk through with the right arrow, the space bar, or a click.

## Filming the slides

The deck is deliberately dark: a white background blooms when you film a screen,
and the numbers stop reading. Two things to check before rolling.

Kill every reflection you can — a lit window behind you lands in the middle of
the slide. And match the shutter to the display refresh, or the frame will roll:
at 60 Hz, shoot 1/60 or 1/120.

Do not zoom the browser. The type is sized in viewport units, so it already fills
the frame at 100 %, and zooming only reflows it.

## Which slide goes with which shot

| Slide | Shot in `script-en.md` |
|---|---|
| 1 | Cold open |
| 2, 3 | Shot 2 — the answer key |
| 4, 5, 6, 7 | Shot 5 — confirmation, not detection |
| 8 | Shot 6 — the freeze |
| 9, 10, 11 | Shot 8 — what it cannot do, and what it admitted |
| 12 | Shot 9 — the false alarm |
| 13 | Shot 10 — what the measurement makes possible |
| 14 | Shot 11 — close |

## Do not end on what one box cannot do

Shot 10 exists because the earlier cut finished on the station's limits, and that
is the wrong last taste. The framing to hold throughout: measuring that 96.9 % of
the catalog is out of reach is **not a negative result**, it is the first
sensitivity figure for this hardware class — and it is exactly the number a
network has to be sized on. Slide 13 turns it into fifty nodes, about $4,000, and
three named gains from §12 of the report.

That does not soften the self-incrimination in shots 8 and 9. It is the reason to
trust the sensitivity figure at all, and the two belong together.

**Time budget.** The perspectives beat costs 24 s over the old close, so the cut
runs about 3:24. The cheapest 12 s to recover is shot 7, the replay: it shows a
calibrated state the station has never reached, with amplitudes 38 times too
large, and it needs a spoken disclaimer before the map fills just to be honest.
Dropping it removes a liability as well as the seconds.

## Two things that must not slip

The station's coordinates are never on screen and never spoken. Slide 6 shows the
20 km disc, which is the whole point of drawing it that way.

The word for 2 September is **confirmation**, never detection. The catalog named
the second; the station did not find it unaided. Slide 4 defines both words before
either is used, and it exists for that reason.

## Before the final cut

Re-check the counts against `web-remote/station.json`. One busy day moves the
journal figures by half, and slides 9 and 12 quote numbers that can move:
autonomous detections, calibration points, events scanned, threshold crossings,
and the audit's `missed`. The table at the end of `script-en.md` holds the values
as of 9 September.
