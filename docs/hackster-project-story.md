# Hackster Story — mode WYSIWYG

**Je ne peux pas ouvrir** `https://www.hackster.io/projects/545685/edit#story` à ta place : connexion Hackster + Cloudflare, pas d’accès à ta session.

**Le plus proche d’un “coller direct”** : ouvre **`hackster-story-paste.html`** (dans ce dossier) dans Chrome → Cmd+A depuis le premier H2 → Cmd+C → onglet Hackster Story → Cmd+V → remplace les encadrés jaunes par tes uploads d’images.

---

Hackster n’interprète pas le Markdown comme GitHub. Travaille **dans l’éditeur visuel** :

1. Pour chaque bloc ci‑dessous : sélectionne le titre → **Heading 2** (ou H2).
2. Colle le paragraphe → gras / listes avec la barre d’outils.
3. Là où tu vois **➕ IMAGE**, clique **Insert image** dans Hackster et choisis le fichier dans  
   `docs/images/` sur ton Mac (nom entre parenthèses).
4. Les URLs seules : sélectionne → **Link** (ou laisse-les, Hackster les rend souvent cliquables).

Projet : https://www.hackster.io/thepriben/sismo-la-the-seismograph-that-learns-from-real-quakes-545685

**Mise à jour 12 sep 2026 (Inglewood)** — sur Hackster, ne modifier que ce qui diffère de la page live :
1. Section **Two ways…** → paragraphe *Retrospective confirmation* (bloc 5).
2. Section **First results** → les 5 puces + légende figure 6 (bloc 6).
3. Optionnel : bloc 7 → « report v3 » ; figure 5 → légende « first of two ».
4. **Project settings** (hors Story) : raccourcir la tagline si elle promet déjà une calibration apprise.

---

## Bloc 1 — Titre : The question

Los Angeles sits on active faults. Minutes after each earthquake, the USGS publishes magnitude, place, depth, and time in a public catalog. This station treats that list as ground truth it does not edit.

The hardware is an Arduino UNO Q with a $12 MEMS accelerometer (~$80 all in). The goal is practical: record local shaking, compare it to the catalog, and publish a running score — including quiet days when nothing in the list should have been felt here.

➕ IMAGE (how-it-works.png)  
Légende : *Figure 1 — From the Modulino sensor to the USGS catalog check and the published snapshot on GitHub Pages.*

---

## Bloc 2 — Titre : Why I built it

Phone accelerometers already feel vibration; they rarely tell you whether the ground moved at city scale. In Los Angeles we can pair a living-room sensor with USGS ComCat: real-time triggers when energy jumps, a retrospective pass when the catalog supplies an arrival time, and an on-board AI filter trained from labels the correlation loop provides (matched event vs unmatched bump). So far the filter has seen thousands of noise samples and zero earthquake labels — which is itself a result worth publishing.

Built for the Invent the Future with Arduino UNO Q and App Lab contest, Best Social Impact category.

---

## Bloc 3 — Titre : Hardware

• Arduino UNO Q (App Lab: Linux + MCU)  
• Arduino Modulino Movement (LSM6DSOX) on Qwiic — use Wire1 on the UNO Q  
• USB-C power, Wi-Fi  

➕ IMAGE (station-cover-branded.jpg)  
Légende : *Figure 2 — Arduino UNO Q and Modulino Movement, connected over Qwiic and powered by USB-C.*

➕ IMAGE (wiring.png)  
Légende : *Figure 3 — One Qwiic cable; the UNO Q uses the Wire1 bus for this port.*

---

## Bloc 4 — Titre : How it works

The STM32 side samples the IMU near 95 Hz and runs STA/LTA: short-window energy against a longer baseline. When the ratio crosses a threshold it sends peak acceleration, duration, and dominant frequency to Linux over Bridge RPC.

Dragonwing handles Wi-Fi, USGS queries, blind/catalog correlation, a one-hertz envelope stored day by day, retrospective scans at catalog arrival times, GitHub Pages publishing, and a local dashboard.

The AI piece is a small on-board logistic regression on those same MCU features, updated when a trigger aligns with the catalog or stays unmatched. Training stays on the board; no separate cloud ML stack.

➕ CODE SNIPPET (optionnel, C++) :  
// STA/LTA ratio crosses a threshold → report an event (see sketch/)  

➕ IMAGE (dashboard-live.png)  
Légende : *Figure 4 — Operator dashboard on the board: MCU heartbeat, triggers, and station health on live data.*

---

## Bloc 5 — Titre : Two ways the record can mention an earthquake

Vocabulary matters for reading the public page.

Blind trigger (detection): the MCU decided something happened and Linux logged it. A desk tap shows up here; the catalog usually has no event at that second.

Retrospective confirmation: the catalog fixed the origin time first; the software then read the stored envelope in the arrival window. Two cases so far at frozen constants (threshold z = 4.0): Ontario, 2 Sep 2026 (M3.2, ci41540608), z = 4.34 — the real-time trigger stayed quiet because the peak was below its floor. Inglewood, 12 Sep 2026 (M2.6, ci41545920), z = 4.21 — again no blind trigger; the retrospective search only opened a short arrival window in each case.

➕ IMAGE (public-map-confirmed.png)  
Légende : *Figure 5 — Public map with the 20 km reference disc; Ontario (2 Sep 2026) as the first catalog-backed confirmation; Inglewood (12 Sep) appears the same way on the live page.*

Public page: https://medialoco.github.io/sismo-la/  
The site shows a 20 km reference disc instead of a street address.

---

## Bloc 6 — Titre : First results in Los Angeles County

After the first weeks of operation:

• Blind triggers matched to the catalog: 0  
• Retrospective confirmations accepted: 2 — ci41540608 Ontario (2 Sep 2026, z 4.34); ci41545920 Inglewood (12 Sep 2026, z 4.21)  
• Catalog events scanned retrospectively: 19; most below the noise floor at this distance  
• Amplitude calibration points: 0 of 8 (waiting for blind matches)  
• AI filter training set: 0 earthquake labels, 10 789 noise samples so far  

Against five years of M≥2 catalog within 160 km, roughly 97% of events sit below what this chip can resolve at this site — so silence is the normal output, and the station says so on the page.

It also runs a self-audit against incoming catalog entries. In early September it flagged a closer M3.2 as a possible miss and posted that; three days later a USGS revision lowered magnitude and depth and the flag cleared without any change in the local waveform. The retrospective channel once crossed threshold on a distant M2.3 with shaking far below the electrical noise; the written report quotes about one such case per 55 comparable windows when amplitude is included. Model coefficients were frozen on 1 Sep 2026 so these statements stay verifiable.

➕ IMAGE (public-data-confirmed.png)  
Légende : *Figure 6 — Data page (Ontario row); the live table lists both confirmations with the same columns.*

---

## Bloc 7 — Titre : What you can reproduce

• Code (MIT): https://github.com/Medialoco/sismo-la — release v1.0.0  
• Technical report v3 (EN + FR, reproduction archive): https://doi.org/10.5281/zenodo.22679542  
• Live snapshot: https://medialoco.github.io/sismo-la/station.json  

Clone the repo, deploy with App Lab on UNO Q, copy config.example.yaml to config.yaml (keep site coordinates private). Steps: docs/getting-started.md in the repository.

---

## Bloc 8 — Titre : Toward a small network

One node measures distance to the shaking; direction needs geometry. Draw that distance as a circle and the earthquake lies somewhere on the ring. Three nodes at different homes give three circles — their overlap narrows to an epicenter. The same ~$80 boards could vote on real events (coincidence drops footstep noise) and feed a coarse felt map while official networks finish processing.

Today there is one installation. The sketch shows the layout math; the live map still carries a single disc.

➕ IMAGE (network.png)  
Légende : *Figure 7 — One home node defines a distance ring; three nodes narrow the overlap toward an epicenter.*

---

## Ordre des images (checklist)

| # | Fichier | Légende (EN, sous l’image) |
|---|---------|----------------------------|
| 1 | how-it-works.png | Figure 1 — From the Modulino sensor to the USGS catalog check and the published snapshot on GitHub Pages. |
| 2 | station-cover-branded.jpg | Figure 2 — Arduino UNO Q and Modulino Movement, connected over Qwiic and powered by USB-C. |
| 3 | wiring.png | Figure 3 — One Qwiic cable; the UNO Q uses the Wire1 bus for this port. |
| 4 | dashboard-live.png | Figure 4 — Operator dashboard on the board: MCU heartbeat, triggers, and station health on live data. |
| 5 | public-map-confirmed.png | Figure 5 — Public map; Ontario (2 Sep) shown; Inglewood (12 Sep) on the live page. |
| 6 | public-data-confirmed.png | Figure 6 — Data page (Ontario row); live table lists both confirmations. |
| 7 | network.png | Figure 7 — One home node defines a distance ring; three nodes narrow the overlap toward an epicenter. |
