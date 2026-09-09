# Hackster submission checklist (to stay within the rules)

Summary of the rules to follow, based on the
[Content Guidelines](https://www.hackster.io/guidelines) and
[How to Create a High-Quality Project Tutorial](https://www.hackster.io/AlexWulff/how-to-create-a-high-quality-project-tutorial-e25feb).
We fill this page in as the project progresses.

## Contest requirements (reminder)

- Must use the **Arduino UNO Q** and **App Lab**.
- Target category: **Best Social Impact** (alt. Industrial IoT).
- Submission deadline: **September 13, 2026, 11:59 PM PDT**.
- Appreciated bonuses: sustainability, user experience, scalability, edge AI
  (Edge Impulse), cloud integration (Arduino Cloud / AWS).
- Two of those bonuses we do **not** have, and must not imply: there is no Edge
  Impulse model (the noise filter is an online logistic regression in
  `python/classifier.py`, still silent for want of a single labelled earthquake)
  and no Arduino Cloud or AWS integration (publishing goes straight to the
  GitHub contents API). Claiming either would be the one mistake this project
  cannot afford.

## Quality checklist (Content Guidelines)

- [x] **Name**: a complete sentence, describing *what it does*, catchy, no URL.
      (Not "Arduino UNO Q project" but e.g. "A neighborhood seismograph that
      learns from real Los Angeles earthquakes".) → drafted in
      `hackster-story.md` (name / pitch at the top of the video storyboard).
- [x] **Pitch**: a single sentence, does not duplicate the name, no URL.
      → drafted; shares no significant word with the name.
- [ ] **Cover image**: high resolution, good lighting, **no text**, shows the end
      result (not a tangle of breadboard wires). 4:3 format.
- [ ] **Difficulty**: accurate.
- [ ] **Categories**: max 3, describing what it *achieves* — avoid "Arduino",
      use e.g. "Monitoring", "Data collection", "Social impact".
- [ ] **Things**: list ALL components actually used (UNO Q, IMU…), with a store
      link when possible. Software/tools go in their own sections.
- [ ] **Story**: structured in steps with headings (not a wall of text),
      clickable URLs, embedded videos, **code as snippets** (not plain text),
      crisp images.
- [ ] **Schematics**: section reserved for schematics (Fritzing or other).
- [ ] **Code**: files in the Code section, correct language selected. No
      placeholders to inflate the checklist.
- [ ] **Language**: correct English, careful spelling/punctuation.

## Recommended Story structure (steps)

1. **The question** — ten million people on active faults, instrumentation that
   exists but is institutional, and the feasibility question that follows: can a
   $75–90 node detect a quake and size it, unattended? (cf. MyShake, Raspberry
   Shake, whose cheapest board is $294.99.)
2. **The key idea: USGS calibration** — why a cheap sensor becomes useful when you
   have a free ground truth.
3. **Hardware & wiring** — UNO Q + IMU (photo + Fritzing schematic).
4. **The real-time MCU** — STA/LTA explained simply (snippet from the `.ino`).
5. **The Linux side (Dragonwing)** — WiFi, USGS feed, correlation (Python
   snippets).
6. **Detection vs confirmation** — the distinction the whole project rests on. A
   shake the trigger found by itself is a detection; a shake found because the
   catalog named the second is a confirmation. Say it before showing any result,
   because every result below is one or the other.
7. **The second channel: record first, search later** — the continuous envelope,
   and why knowing the second to examine is worth about one magnitude.
8. **The App Lab dashboard** — screenshots. Use the live one
   (`docs/images/dashboard-live.png`), not a replay still.
9. **Results in LA** — what there is, stated as it is:
   - one confirmation, `ci41540608`, M3.2 near Ontario, 2 September 2026,
     envelope 4.34 dispersions above the preceding minutes;
   - the negative control: of three cataloged earthquakes examined, two were
     refused although the catalog had named their exact second, because the
     shaking they could deliver here was below the sensor's own noise;
   - zero autonomous detections, amplitude calibration 0 of 8, noise filter
     0 earthquakes against 10 789 noise samples. These zeros are published as
     they stand and are part of the result.
   There is **no calibration curve** to show. Do not promise one.
10. **How we would know it is broken** — the audit: every cataloged event
    classified out-of-reach, marginal, triggered, confirmed or
    should-have-been-seen. On **6 September 2026** that last count left zero: the
    station flagged an M3.2 as one it should have seen and did not, and published
    it against itself half an hour later. Reading the record shows nothing
    arrived; the prediction was on the optimistic side of a law that scatters by
    a factor of two. Lead with this. An instrument that reports its own failure
    unprompted is worth more than one that only ever reports successes, and it is
    the part of this build a judge cannot get from a datasheet.
    Tell the rest of the story, because it is the same argument twice over. On
    **9 September** USGS revised that earthquake to M3.07, which dropped the
    predicted shaking and **withdrew the miss** — a referee you do not control can
    take back what it gave you. The same week the retrospective channel crossed
    its threshold on an M2.33 whose expected shaking was **33x below the sensor's
    own noise**, i.e. a false confirmation, one day after we finished measuring
    that such crossings happen about **once in 55** on this station's own
    recordings. The public counter therefore reads 2 confirmed while only one is
    real, and the page says so under the number. Nothing was retuned to hide
    either: the thresholds have been frozen since 1 September, and being able to
    state the error rate is the result.
11. **Limits & next steps** — a neighborhood strong-motion node, not a
    teleseismic instrument. 96.9 % of the local catalog is out of reach of both
    channels. One station gives a ring, not a pin.

## Writing & photo tips (Wulff tutorial)

- Lots of **photos** (close-ups, plenty of light, consistent angle).
- Take **more photos than you think you need** during the build.
- Schematics via **Fritzing / CAD**, no napkin sketch.
- **Commented** code, named values (no magic numbers), consistent whitespace.
- **Short, varied** sentences; mix technical / accessible; zero typos.
- A GIF works as a cover (motion = clicks), but at reduced resolution.

## Media to produce (to check)

- [ ] **Cover photo** (final result, polished). Needs the camera, and the rules
      say **no text** on it — so no dashboard export can serve as the cover,
      it has to be the physical station. `docs/images/cover-concept.png` is a
      *rendered concept*, not this station: the board is lit, the screen behind
      shows a map with concentric rings the project cannot produce, and it is
      1536x1024 (3:2) where the guidelines ask 4:3. A project whose whole claim
      is that its numbers are real should not open on a render. Shoot the actual
      station — `docs/images/station.png` (1024x576, 4 September) is the framing
      to beat, taken in better light and cropped to 4:3.
- [ ] Macro photo of the UNO Q + IMU assembly.
- [x] Schematic — `docs/images/wiring.png` (and `.jpg`), source `wiring.svg`.
      Not Fritzing: there is nothing to breadboard, so it shows the single
      Qwiic link and the signal path instead, and prints the one trap worth
      printing (the Qwiic port is `Wire1`, not `Wire`).
- [ ] GIF/video of a detection (tap the desk -> trigger).
- [x] Dashboard screenshot — `docs/images/dashboard-live.png`, the operator
      dashboard on live data (light theme, station coordinates replaced by a
      placeholder). `dashboard-1920x1080.jpg` fills a 16:9 slot (padded, nothing
      cropped).
- [x] Screenshot of the real confirmation — `docs/images/public-map-confirmed.png`
      and `public-data-confirmed.png`, taken from the live published pages while
      `ci41540608` was still inside `publish.window_days`. Caption it
      **confirmed**, never *detected*.
- [x] Diagram of the principle — `docs/images/how-it-works.png` (and `.jpg`).
      Source is `how-it-works.svg`: plain text, edit it rather than the raster.
- [x] Diagram of the network geometry — `docs/images/network.png` (and `.jpg`),
      source `network.svg`. It says on its face that it is a geometric argument
      and not a measurement; do not caption it as a result.
- [x] Calibration sequence — four stills cut from the timelapse,
      `timelapse-1-learning` to `timelapse-4-calibrated`, usable as a
      before/after pair in the Story. **These are replay, not measurement**:
      real catalog times, synthetic amplitudes about 38 times too large so the
      demo crosses the trigger. The caption has to say so in the same frame, and
      `timelapse-4-calibrated` in particular shows a calibrated state the station
      has never reached. It illustrates the software; it is not evidence.
