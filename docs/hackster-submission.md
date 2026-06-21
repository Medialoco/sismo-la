# Hackster submission checklist (to stay within the rules)

Summary of the rules to follow, based on the
[Content Guidelines](https://www.hackster.io/guidelines) and
[How to Create a High-Quality Project Tutorial](https://www.hackster.io/AlexWulff/how-to-create-a-high-quality-project-tutorial-e25feb).
We fill this page in as the project progresses.

## Contest requirements (reminder)

- Must use the **Arduino UNO Q** and **App Lab**.
- Target category: **Best Social Impact** (alt. Industrial IoT).
- Submission deadline: **August 30, 2026**.
- Appreciated bonuses: sustainability, user experience, scalability, edge AI
  (Edge Impulse), cloud integration (Arduino Cloud / AWS).

## Quality checklist (Content Guidelines)

- [ ] **Name**: a complete sentence, describing *what it does*, catchy, no URL.
      (Not "Arduino UNO Q project" but e.g. "A neighborhood seismograph that
      learns from real Los Angeles earthquakes".)
- [ ] **Pitch**: a single sentence, does not duplicate the name, no URL.
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

1. **The problem** — LA is seismic; real seismographs are expensive; idea of a
   low-cost citizen node (cf. MyShake, Raspberry Shake).
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

- [ ] Cover photo (final result, polished).
- [ ] Macro photo of the UNO Q + IMU assembly.
- [ ] Fritzing schematic.
- [ ] GIF/video of a detection (tap the desk -> trigger).
- [ ] Dashboard screenshot.
- [ ] Screenshot of a successful USGS correlation.
