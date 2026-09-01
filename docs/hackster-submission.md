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

## Quality checklist (Content Guidelines)

- [x] **Name**: a complete sentence, describing *what it does*, catchy, no URL.
      (Not "Arduino UNO Q project" but e.g. "A neighborhood seismograph that
      learns from real Los Angeles earthquakes".) → drafted in
      `hackster-story.md`, with two alternates.
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
6. **Edge AI (Edge Impulse)** — earthquake vs noise, how the data was collected
   and the model trained.
7. **The App Lab dashboard** — screenshots.
8. **Results & validation in LA** — calibration curve, examples of real
   earthquakes correctly correlated (evidence).
9. **Limits & next steps** — honesty: local detector, not teleseismic.

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
      it has to be the physical station.
- [ ] Macro photo of the UNO Q + IMU assembly.
- [x] Schematic — `docs/images/wiring.png` (and `.jpg`), source `wiring.svg`.
      Not Fritzing: there is nothing to breadboard, so it shows the single
      Qwiic link and the signal path instead, and prints the one trap worth
      printing (the Qwiic port is `Wire1`, not `Wire`).
- [ ] GIF/video of a detection (tap the desk -> trigger).
- [x] Dashboard screenshot — `docs/images/timelapse-4-calibrated.jpg`, and
      `dashboard-1920x1080.jpg` for a 16:9 slot (padded, nothing cropped).
- [x] Screenshot of a successful USGS correlation — same still: the right-hand
      panel lists "Earthquake — confirmed by USGS" with what the device said
      next to what USGS said.
- [x] Diagram of the principle — `docs/images/how-it-works.png` (and `.jpg`).
      Source is `how-it-works.svg`: plain text, edit it rather than the raster.
- [x] Diagram of the network geometry — `docs/images/network.png` (and `.jpg`),
      source `network.svg`. It says on its face that it is a geometric argument
      and not a measurement; do not caption it as a result.
- [x] Calibration sequence — four stills cut from the timelapse,
      `timelapse-1-learning` to `timelapse-4-calibrated`, usable as a
      before/after pair in the Story.
