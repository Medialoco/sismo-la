# Sensor upgrade: what is actually pluggable into an UNO Q

Surveyed **2026-09-01**. Every price, stock figure and datasheet number below
carries the date it was read, because all three move.

The station's at-rest noise floor was measured that morning to be the
LSM6DSOX's own electrical noise, in two independent bands, to within 4-10% of
the datasheet white-noise line (see `AGENTS.md`, "The seismic band-pass"). The
software has run out of room. This document answers the only question left:
**which quieter accelerometer can be plugged into this board, at what cost in
hand-work, and what does it buy in detections per year.**

Scope note: the question asked was specifically about *pluggable* boards, not a
soldering-and-PCB-design project. That constraint is respected below, and it
does most of the work of narrowing the field.

## 1. What the UNO Q really offers (verified against the datasheet)

From the official UNO Q datasheet (ABX00162, revision dated 17/06/2026) and the
board schematic, both read 2026-09-01:

| Interface | What it is | Voltage |
|---|---|---|
| **Qwiic (QWIIC1)** | 4-pin JST, I2C4: `PD13` = SDA, `PD12` = SCL, `+3V3 OUT` | **3.3 V only** |
| Classic UNO headers | I2C2 on SDA/SCL, exposed as the `Wire` object | 3.3 V logic |
| **JSPI (JSPI1)** | 6-pin: MISO `PC2`, SCK `PD1`, MOSI `PC3`, RESET, GND, **+5V** | 3.3 V logic |
| JDIGITAL / JANALOG | GPIO, ADC, `+3V3 OUT` and `+5V` power pins | 3.3 V, VREF+ 3.3 V |

Four consequences that shape everything below.

- **The Qwiic connector is `Wire1`; the classic SDA/SCL header pins are `Wire`.**
  Both are I2C, on different peripherals. This matters more than it looks: an
  Arduino library that hardcodes the global `Wire` works unmodified on the
  *header* pins and not at all on the Qwiic connector.
- **The board carries its own I2C pull-ups.** The schematic shows R2613 and
  R2614, 2.2 kΩ to `PWR_3P3V`, on the Qwiic I2C4 lines, behind 0 Ω series
  jumpers R2615/R2616, and the same arrangement on the header bus. A bare
  breakout with no pull-ups of its own therefore works — which is not obvious
  and is exactly the trap that stops a naked evaluation board from talking.
  (Read from the schematic's text layer; the designator-to-net attribution is
  inferred from placement, the *presence* of 2.2 kΩ pull-ups on both buses is
  unambiguous.)
- **3.3 V is not a suggestion.** Most digital GPIOs are 5 V-tolerant as inputs,
  but A0/A1 and ~D3 are not, and analog functions never are. Every candidate
  below is a 3.3 V part, so this is a hazard only if someone reaches for a 5 V
  logic-level module.
- **JSPI has no 3.3 V pin.** Its only power pin is `+5V` (`5V_USB_VBUS`). An
  SPI sensor therefore needs its 3.3 V from JANALOG or IOREF, i.e. wires to two
  different headers, plus a chip-select from a GPIO on JDIGITAL, because JSPI
  carries no CS. That is six wires minimum before anything works.

The reference for "simple" is the current sensor: **Modulino Movement
(ABX00101, LSM6DSOX)**, one Qwiic cable, zero soldering, zero wires.

## 2. How the gain figures were computed

`tools/sensor-gain.py` does it, and it reproduces the published station figures
bit-for-bit before being trusted with a new one. Method:

1. The trigger is STA/LTA, so the amplitude a shake needs in order to fire is
   proportional to the noise floor the LTA tracks. The measured trigger floor is
   **0.00308 g** (0.0044 g before the band-pass, divided by the measured 1.43x).
2. The at-rest floor was measured to be the sensor's white noise. Swapping the
   sensor therefore scales the trigger floor by the ratio of noise densities.
3. That floor is converted to a required magnitude with `REF_GMPE`
   (`python/pipeline.py`), the law refitted to 12324 USGS ShakeMap PGA values.
4. The 0.390 log10 scatter of that fit becomes a per-event detection
   probability, summed over **2185 real events** (M>=2 within 160 km of the station's site,
   2021-09-01 to 2026-09-01, USGS FDSN, fetched 2026-09-01).

Validation: at 0.0044 g the script returns **1.31-6.56** detections/year against
the 1.31-6.57 in `AGENTS.md`, and at 0.00308 g it returns **1.98-9.79** against
1.98-9.80. The magnitude table reproduces exactly. The method is the same one,
re-runnable.

The `x1 .. x4` spread in every rate below is unknown site amplification, and it
is not a rounding error — station-to-station scatter is 0.347 of the fit's 0.390
log10, i.e. site response dominates and an indoor mount makes it unknowable.

### The numbers

Noise densities are from manufacturer datasheets at the stated full scale, which
is not optional: the density moves with the range.

| Sensor | µg/√Hz | floor (g) | M@10km | M@30 | M@50 | M@100 | M@160 | det/year (x1..x4) | mean wait | P(one in 12 d) |
|---|---|---|---|---|---|---|---|---|---|---|
| KX134-1211 (±8 g) | 130 | 0.00364 | 3.2 | 4.0 | 4.4 | 5.0 | 5.4 | 1.6 - 8.1 | 45-224 d | 5-23% |
| **LSM6DSOX, current (±4 g)** | **110** | **0.00308** | 3.1 | 3.9 | 4.3 | 4.9 | 5.3 | **2.0 - 9.8** | 37-184 d | 6-28% |
| ADXL357 (±10.24 g) | 80 | 0.00224 | 3.0 | 3.8 | 4.2 | 4.8 | 5.2 | 2.9 - 13.8 | 26-127 d | 9-36% |
| SCA3300-D01 (±3 g) | 37 | 0.00103 | 2.6 | 3.4 | 3.8 | 4.4 | 4.8 | 7.0 - 29.8 | 12-52 d | 21-62% |
| **ADXL355 (±2 g)** | **22.5** | **0.00063** | 2.3 | 3.1 | 3.5 | 4.1 | 4.5 | **12.2 - 47.0** | 8-30 d | 33-79% |

Read every magnitude as **±0.45 Mw (1σ)**, and below M3 as extrapolation: the
smallest earthquake in the fit is M3.03.

Two honest limits on the bottom two rows. The floor-scaling assumption was only
*measured* at 0.00036 g; below roughly 1e-4 g, where an ADXL355 would sit, the
site's own contribution has never been shown to be negligible, because it could
not be separated from zero at the current floor. Expect the first factor of 2-3
to be certain and the rest to be probable. And `AGENTS.md` quotes 10.9-42.8/year
for the ADXL355 — that figure was computed with 25 µg/√Hz, the value in Rev. 0
of the datasheet. Rev. D says 22.5, which gives 12.2-47.0. The difference is
0.05 Mw and changes nothing.

## 3. The candidates, one by one

### ADXL355 — the only one that changes the answer

**Noise: 22.5 µg/√Hz at ±2 g** (25 µg/√Hz at ±8 g), all three axes, ADXL354/355
datasheet Rev. D, verified 2026-09-01. 20-bit ADC, programmable high-pass and
low-pass filters, ODR up to 4 kHz. **4.9x quieter than the LSM6DSOX.**

**Interface: both SPI and I2C, verified from the pin table**, not from a product
name. I2C is enabled purely in hardware — pin 2 (`SCLK/VSSIO`) tied to pin 6
(`VSSIO`) — and the chip auto-detects the interface with no software selection.
Address is `0x1D` with `MISO/ASEL` low, `0x53` with it high. I2C runs at
standard, fast, fast-plus and high-speed rates, so the station's ~100 Hz is not
remotely a constraint.

**One I2C caveat straight from the datasheet, and it is a real one**: the
ADXL355 is a *point-to-point* I2C device. Even when it is not addressed, it
acknowledges and pulls SDA low whenever the bytes `0x3A`/`0x3B` (at address
`0x1D`) appear on the bus, which can break communication with other devices.
Consequence for us: whichever bus it goes on must carry nothing else. That is
fine — the Modulino comes off — but do not daisy-chain.

**Boards, and this is where it gets less pleasant. There is no Qwiic board for
the ADXL355.** Not from SparkFun, not from Adafruit, not from ADI. Checked
2026-09-01.

- **EVAL-ADXL355Z** (~$45-55): a breakout with the accelerometer already
  soldered to the PCB. **The pin headers are not fitted.** ADI's own product
  page describes "2 sets of spaced vias for populating 6-pin headers", and the
  user guide's bill of materials lists P1/P2 as "Headers, male, nonshrouded,
  2 × 3, 0.1" spacing, through hole, **do not insert**". So this board needs
  header soldering — 12 pins — before a single Dupont wire can be attached.
  That is the honest answer to the question the user asked not to be guessed at.
- **EVAL-ADXL355-PMDZ**: Pmod form factor, and ADI documents it as using the
  **extended SPI** Pmod interface. So although the chip can do I2C, this board
  is wired for SPI. It ships with a 12-pin Pmod header, which on this board is
  a right-angle male header — usable with female Dupont jumpers, but confirm
  before ordering (see the uncertainty list).
- **Generic "ADXL355 module" listings** on marketplaces do exist, some with
  headers already fitted. None of the ones surfaced were from a vendor whose
  stock, authenticity or delivery date could be verified, and several pages
  were plainly auto-generated. Not recommended on a 12-day clock.

**Price and availability, 2026-09-01, and treat these with suspicion.** An
aggregator (`electronicsdatasheets.com`) reported for EVAL-ADXL355Z: Mouser 337
in stock at **$46.74**, Analog Devices direct **$44.94**, Newark 629 at $53.16,
Verical 132 at $41.22, DigiKey 0 in stock at a nonsensical $243.98. A second
aggregator served figures timestamped **2020**. The plausible band is
**$41-55**, from a US distributor, with Mouser and ADI the two to check
directly — both ship next-day domestically, which is what matters here.
**These figures were not confirmed on the vendors' own pages** and must be
before ordering.

**Software: better than expected, and this was tested rather than assumed.**

- The Arduino library index carries exactly one ADXL355 library: **`PL ADXL355`
  v1.4.2**, `github.com/plasmapper/adxl355-arduino`, released **2026-08-27**,
  last commit 2026-08-28. Actively maintained, five days old at survey time.
  It covers range, ODR, both filters, FIFO, activity detection and self-test.
- **It compiles for `arduino:zephyr:unoq`.** Verified locally on 2026-09-01
  with the installed core (`arduino:zephyr 0.56.0`): 72556 bytes of flash (9%),
  27648 bytes of RAM (10%), no errors. This matters because the library uses
  `std::shared_ptr` and `<algorithm>`, and because this platform has a history
  of link failures on innocuous-looking calls (`expf`, see `AGENTS.md`). It
  links.
- Dependencies are only `SPI` and `Wire`, both core-provided, so the hermetic
  profile build needs exactly one new line in `sketch/sketch.yaml`.
- **The catch: `beginI2C(address, frequency)` takes no `TwoWire&`.** The I2C
  path hardcodes the global `Wire` at 13 call sites, while it *does* accept a
  custom `SPIClass`. So over Qwiic (`Wire1`) the library does not work as
  shipped. Two ways out, both cheap:
  1. **Wire the sensor to the classic SDA/SCL header pins** instead of the
     Qwiic connector. Those are `Wire`, so the library works untouched. Same
     3.3 V, same 2.2 kΩ pull-ups.
  2. **Patch the library.** Substituting `Wire1` for `Wire` at those 13 sites
     compiles with identical flash and RAM usage — verified 2026-09-01. A
     proper `TwoWire&` parameter is the same edit done politely, and worth
     upstreaming.

**Hand-work verdict: bucket (c), soldering.** Twelve header pins on an
EVAL-ADXL355Z, then six to seven Dupont wires (VSUPPLY, VDDIO, GND, SDA, SCL,
`SCLK`→GND to select I2C, `ASEL`→GND for address 0x1D). Not a plug-in cable.
This is the single biggest gap between this option and the current setup.

### SCA3300-D01 — disqualified, and for a different reason than expected

**Noise: 37 µg/√Hz** (Mode 1, ±3 g, 70 Hz), integrated 0.44 mg rms, from the
Murata SCA3300-D01 datasheet, verified 2026-09-01. Ranges ±1.5/±3/±6 g, 3.0-3.6
V supply, 3.3 V logic. 3.0x quieter than the LSM6DSOX — a real gain, 7.0-29.8
detections/year.

**Interface: SPI only, and confirmed from the pin table rather than the
marketing text.** The twelve pins are AVSS, A_EXTC, RESERVED, VDD, **CSB, MISO,
MOSI, SCK**, DVIO, D_EXTC, DVSS, EMC_GND. There is no SDA, no SCL, no I2C
anywhere in the part. The datasheet goes further: "3-wire SPI connection is not
supported", and frames are 32-bit 4-wire. **So a Qwiic connector on any
SCA3300 board can carry power and nothing else** — the user's suspicion is
correct, and it is a property of the silicon, not of the board.

**And there is a worse problem, which is why this is disqualified rather than
merely inconvenient.** The datasheet states the ODR is fixed at 2000 Hz and
that "registers are updated in every 0.5 ms and **if all data is not read the
full noise performance of sensor is not met**", recommending that all three axes
be read every cycle at sensor ODR. Getting the 37 µg/√Hz therefore means 6000
32-bit SPI frames per second. The station's loop runs at a measured 95.3 Hz. The
firmware would have to be restructured around a 2 kHz DMA'd SPI cadence to
obtain a gain that is still 1.6x worse than the ADXL355's. There is also no
SCA3300 library in the Arduino library index at all.

**Verdict: no.** More firmware work than the ADXL355, for less gain, over a bus
that needs more wires.

### ADXL357 — quieter on paper, not where it counts

**Noise: 80 µg/√Hz** at ±10.24 g. Only 1.4x better than the LSM6DSOX, because
the ADXL357's whole point is a ±10/±20/±40 g range, and noise density scales
with full scale. 2.9-13.8 detections/year, a mean wait of 26-127 days. Same
board problem as the ADXL355 (EVAL-ADXL357Z, headers not fitted), same wiring,
for a quarter of the benefit. **No.**
*(This density is from the ADXL356/357 datasheet as cited by ADI's product
literature; it was not read out of the PDF directly during this survey — see
the uncertainty list.)*

### KX134-1211 — the trap of a convenient connector

The one candidate with a genuinely plug-and-play board: **SparkFun Triple Axis
Accelerometer Breakout - KX134 (Qwiic), SEN-17589**, ~$27-36, real Qwiic
connectors, I2C *and* SPI, and a maintained library (`SparkFun KX13X` v2.0.4)
which does accept an alternate `TwoWire`. Everything the current setup has.

**And it is louder than what is already on the board: 130 µg/√Hz** at ±8 g
(SparkFun's own specification, 2026-09-01). Fitting it would move the station
from 2.0-9.8 detections a year to **1.6-8.1**. The sister part KX132-1211 goes
down to ±2 g and may be quieter at that range, but no figure was confirmed from
the ROHM/Kionix datasheet during this survey.

This entry is kept precisely because it is the shape of mistake this exercise
exists to avoid: the easiest board to plug in is the one that makes the
instrument worse.

### Geophones and a Qwiic ADC — the Raspberry Shake route

A 4.5 Hz geophone with a 24-bit ADC is what Raspberry Shake does, and it is
quieter in 1-10 Hz than any MEMS part here. It is also the wrong answer to the
question that was asked, for reasons that are structural rather than
incidental:

- **A geophone measures velocity, not acceleration.** The station's entire
  chain — `pga_g`, the band-pass normalisation to g, `REF_GMPE`, the amplitude
  law the station learns, the plausibility veto — is built on PGA. Using a
  geophone means either differentiating a noisy signal or switching to a PGV
  ground-motion law and refitting everything the project has measured.
- **It rolls off below its own corner**, and local energy at 20-50 km sits
  partly below 4.5 Hz.
- **It needs an analog front end**: tens of µV to mV differential, so a gain
  stage, a virtual ground on a single supply, and anti-alias filtering — a
  circuit to design and solder, which is explicitly what the user ruled out.
- The ADC side is the easy half. Qwiic 24-bit boards exist (SparkFun ADS1219,
  NAU7802) with maintained Arduino libraries. The amplifier is the hard half.

**Verdict: real potential, wrong shape, and out of the question in 12 days.**
Worth revisiting only after the MEMS step has been made and measured. A
detailed sub-survey of specific geophone parts, ADC noise budgets and turnkey
modules is deliberately not reproduced here, because the disqualifying argument
is the velocity-vs-acceleration rewrite, not the parts list.

### Ready-made seismic modules

- **Raspberry Shake RS1D**: $294.99 for the board, $584.99 turnkey (checked
  2026-09-01 for `docs/hardware.md`). It is a Raspberry Pi appliance with its
  own software stack, not an Arduino peripheral. Buying one would replace the
  project, not improve it.
- **Grillo OpenEEW**: ADXL355-based and open-source, which is a useful
  confirmation that the ADXL355 is the right class of part for earthquake
  detection. Whether a board can be bought and delivered was not established.
- The `SW-420` / `801S` "earthquake sensor modules" sold for Arduino are
  **vibration switches, not seismometers**. They have no calibrated
  sensitivity and would be a large step backwards. Not candidates.

## 4. Recommendation

**The ADXL355 is the only candidate worth any effort, and it should not be
attempted before 2026-09-13.**

Why it is the right part: it is the only option that changes the station's
character rather than nudging it. 4.9x lower noise, 6x the detection rate, the
required magnitude at 30 km falling from M3.9 to M3.1, and the probability of a
first genuine detection in a 12-day window going from 6-28% to 33-79%.
Everything else on the list is either louder than what is fitted, or a smaller
gain for more work, or a different project.

Why not now, stated plainly:

1. **Two contest deliverables are still missing** — the cover photo, which must
   be a text-free shot of the physical station, and the video. Both need the
   station assembled and running. A sensor swap puts the hardware on the bench.
2. **The board needs soldering.** Twelve header pins on an EVAL-ADXL355Z, then
   six or seven wires, then an I2C-mode strap. Nothing here is a Qwiic cable.
   If the soldering iron slips, the project has no sensor at all.
3. **The Qwiic library path needs a patch.** Small, mechanical, tested — but a
   patched library must go into the hermetic profile build, be flashed, and be
   verified over the Bridge before it can be trusted.
4. **A sensor arriving on 10 September is a liability, not an asset.** Even
   with next-day US shipping the realistic sequence is order, receive, solder,
   wire, patch, flash, verify, re-measure the two-channel noise floor. That is
   not a two-day job on a station whose only remote surface is a read-only
   dashboard and which cannot be rebooted remotely.
5. **The upgrade would not rescue the calibration anyway.** At 12.2-47.0
   detections a year the mean wait is still 8-30 days, and the calibration needs
   eight points. The ADXL355 is what makes this station work over a season. It
   is not what makes it work by Sunday week.

**What the deadline actually wants** is the measurement that is already in hand:
the floor is the sensor's own electrical noise, proven in two bands, and the
next gain is therefore hardware. That is a stronger result than a rushed swap,
and it is already written down.

**After the contest**, in order: confirm price and stock on Mouser's and ADI's
own pages; order an EVAL-ADXL355Z; solder P1 and P2; wire it to the classic
SDA/SCL header pins first, because the unpatched library works there and it
removes one variable; read the same two-channel in-band/wideband ratio the
band-pass work introduced. That last step is what will show whether the site
noise stays negligible at 0.00008 g — the one thing the current measurement
cannot prove.

## 5. Verified, versus assumed

**Verified, with a source read on 2026-09-01:**

- UNO Q Qwiic is I2C4 / `Wire1` / 3.3 V only, header I2C is `Wire`, JSPI pin map
  and its lack of a 3.3 V pin — UNO Q datasheet ABX00162 rev. 17/06/2026.
- 2.2 kΩ I2C pull-ups to 3.3 V on both buses — UNO Q schematic, sheet 19.
- ADXL355 noise density 22.5 µg/√Hz at ±2 g, 25 at ±8 g; SPI *and* I2C; I2C
  enabled by strapping pin 2 to pin 6; addresses 0x1D/0x53; the point-to-point
  SDA warning — ADXL354/355 datasheet Rev. D.
- EVAL-ADXL355Z headers are **not** fitted — ADI product page ("vias for
  populating 6-pin headers") and user guide UG-1030 BOM ("do not insert").
- EVAL-ADXL355-PMDZ uses the Pmod **extended SPI** interface — ADI system-level
  documentation.
- SCA3300-D01: 37 µg/√Hz Mode 1, SPI-only 12-pin map, 3-wire unsupported, ODR
  fixed at 2000 Hz with the noise spec conditional on reading every cycle —
  Murata SCA3300-D01 datasheet.
- `PL ADXL355` v1.4.2 is the only ADXL355 library in the Arduino index; released
  2026-08-27; hardcodes `Wire` at 13 I2C call sites; accepts a custom
  `SPIClass`; **compiles and links for `arduino:zephyr:unoq`**, and still does
  after the `Wire1` substitution — both builds run locally.
- No Qwiic/STEMMA-QT ADXL355 board exists from SparkFun, Adafruit or ADI.
- KX134-1211 at 130 µg/√Hz, i.e. louder than the LSM6DSOX — SparkFun product
  specification.
- All detection rates: computed by `tools/sensor-gain.py` over 2185 real USGS
  events, method validated against the published station figures.

**Assumed, or not established — do not treat as settled:**

- **Prices and stock.** Every EVAL-ADXL355Z figure came from an aggregator, one
  of which served 2020 data. Confirm on mouser.com and analog.com before
  ordering. No shipping date to Los Angeles was confirmed with any vendor.
- **Whether the EVAL-ADXL355-PMDZ's Pmod header ships pre-soldered**, and in
  what orientation. This is decisive for the amount of hand-work and it could
  not be determined from the documentation.
- **ADXL357's 80 µg/√Hz** was taken from ADI product literature, not read out
  of the ADXL356/357 PDF during this survey. It only affects a candidate
  already rejected.
- **KX132-1211's noise density at ±2 g** — not confirmed from the Kionix/ROHM
  datasheet. Possibly better than 130 µg/√Hz, almost certainly not competitive
  with 22.5.
- **The floor-scaling assumption below 1e-4 g.** The site was shown to
  contribute nothing resolvable *at 0.00036 g*. It cannot follow that it stays
  negligible five times lower. The ADXL355 rates are therefore an upper bound
  on what the site will allow, and the way to find out is to run it.
- **Whether the Modulino's Qwiic pull-ups are load-bearing.** The board's own
  2.2 kΩ resistors should be sufficient alone, but this has only been read off
  a schematic, never tested with a pull-up-less peripheral.
- **Availability of a Grillo OpenEEW board** to a private buyer.

## 6. Reproducing the numbers

```bash
python3 tools/sensor-gain.py --lat <station lat> --lon <station lon>
```

Queries USGS directly, or takes a cached geojson as an argument. Without
`--lat/--lon` it falls back to `python/config.example.yaml`, which is downtown
LA and **not** where the board is — that inflates the rates by about 24%,
because the station's site sits further from the Puente Hills cluster. The station's real
position lives only in the board's gitignored `config.yaml`.
