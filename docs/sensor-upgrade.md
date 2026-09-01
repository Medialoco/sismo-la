# Sensor upgrade: what is actually pluggable into an UNO Q

Surveyed **2026-09-01**. Every price, stock figure and datasheet number below
carries the date it was read, because all three move.

The station's at-rest noise floor was measured that morning to be the
LSM6DSOX's own electrical noise, in two independent bands, to within 4-10% of
the datasheet white-noise line: 0.00036 g measured in the 0.7-12 Hz band against
0.00040 g predicted, 0.00052 g against 0.00050 g wideband, both averaged over
the same ten seconds so that neither figure depends on comparing one night with
another. No *filter* can go further: the noise is white and inside the seismic
band, so the only bandwidth left to remove is bandwidth an earthquake needs.
This document answers the question that follows: **which quieter accelerometer
can be plugged into this board, at what cost in hand-work, and what does it buy
in detections per year.**

One correction to the framing, made the same afternoon. An earlier version of
this paragraph said "the software has run out of room", and that was wrong by
one word. The filter had; the *blind trigger* had not, because its threshold is
set by a false-alarm budget rather than by the noise. Spending that budget
differently — recording a continuous envelope and re-reading it at the arrival
time the USGS catalog implies — is worth a factor 7 to 8 in amplitude, a full
magnitude unit, and it is already deployed (configuration in
`docs/getting-started.md`, gain reproduced by `tools/retro-gain.py`). Everything
below still stands, because that trick needs the catalog to say when to look and
therefore cannot make the station detect anything *on its own*. A quieter sensor is still the only route to a lower autonomous threshold,
and the two gains multiply rather than overlap.

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
   probability, summed over **2185 real events** (M>=2 within 160 km of the
   station, 2021-09-01 to 2026-09-01, USGS FDSN, fetched 2026-09-01).

Validation: at 0.0044 g — the trigger floor before the band-pass — the script
returns **1.31-6.56** detections/year against the 1.31-6.57 published for that
floor, and at 0.00308 g it returns **1.98-9.79** against the 1.98-9.80 published
for the current one. The magnitude table reproduces exactly. The method is the
same one, re-runnable.

The `x1 .. x4` spread in every rate below is unknown site amplification, and it
is not a rounding error — station-to-station scatter is 0.347 of the fit's 0.390
log10, i.e. site response dominates and an indoor mount makes it unknowable.

### The numbers

Noise densities are from manufacturer datasheets at the stated full scale, which
is not optional: the density moves with the range.

| Sensor | µg/√Hz | floor (g) | M@10km | M@30 | M@50 | M@100 | M@160 | det/year (x1..x4) | mean wait | P(one in 12 d) |
|---|---|---|---|---|---|---|---|---|---|---|
| KX134-1211 (±8 g) | 300 | 0.00839 | 3.6 | 4.4 | 4.8 | 5.4 | 5.8 | 0.6 - 3.1 | 118-599 d | 2-10% |
| KX132-1211 (±2 g) | 130 | 0.00364 | 3.2 | 4.0 | 4.4 | 5.0 | 5.4 | 1.6 - 8.1 | 45-224 d | 5-23% |
| **LSM6DSOX, current (±4 g)** | **110** | **0.00308** | 3.1 | 3.9 | 4.3 | 4.9 | 5.3 | **2.0 - 9.8** | 37-184 d | 6-28% |
| ADXL357 (±10 g) | 75 | 0.00210 | 2.9 | 3.7 | 4.1 | 4.7 | 5.1 | 3.1 - 14.7 | 25-118 d | 10-38% |
| ISM330DHCX (HP) | 60 | 0.00168 | 2.8 | 3.6 | 4.0 | 4.6 | 5.0 | 4.0 - 18.5 | 20-91 d | 12-46% |
| SCA3300-D01 (±3 g, mode 1) | 44 | 0.00123 | 2.7 | 3.5 | 3.9 | 4.5 | 4.9 | 5.8 - 25.2 | 14-63 d | 17-56% |
| **ADXL355 (±2 g)** | **22.5** | **0.00063** | 2.3 | 3.1 | 3.5 | 4.1 | 4.5 | **12.2 - 47.0** | 8-30 d | 33-79% |
| IIS2ICLX (2-axis) | 15 | 0.00042 | 2.1 | 2.9 | 3.3 | 3.9 | 4.3 | 18.5 - 66.9 | 5-20 d | 46-89% |

Read every magnitude as **±0.45 Mw (1σ)**, and below M3 as extrapolation: the
smallest earthquake in the fit is M3.03.

Two honest limits on the bottom rows. The floor-scaling assumption was only
*measured* at 0.00036 g; below roughly 1e-4 g, where an ADXL355 or IIS2ICLX
would sit, the site's own contribution has never been shown to be negligible,
because it could not be separated from zero at the current floor. Expect the
first factor of 2-3 to be certain and the rest to be probable. An earlier
estimate of 10.9-42.8/year for the ADXL355 is superseded: it was computed with
25 µg/√Hz, the value in Rev. 0 of the datasheet. Rev. D says 22.5, which gives
12.2-47.0.
The difference is 0.05 Mw and changes nothing. The IIS2ICLX row is an upper
bound twice over: two axes instead of three (the current `pga_g` is a 3-vector
magnitude), and the same site-noise caveat, one step further down.

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
- **EVAL-ADXL355-PMDZ** (~$36-47): Pmod form factor, wired for the **extended
  SPI** Pmod interface. The chip can do I2C; this board cannot, as shipped.
  **The 12-pin right-angle header is already soldered** — confirmed from ADI's
  own product photograph (`EVAL-ADXL355-PMDZ 08-043217 REV A` on
  wiki.analog.com, 2026-09-01). Female Dupont jumpers plug onto it. ADI's own
  no-OS guide documents exactly that wiring to boards that have no Pmod
  socket. This is the lowest-hand-work ADXL355 path: bucket (b), wires, no
  soldering.
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
  of link failures on innocuous-looking calls: `expf` does not link at all here,
  because it sets `errno` and this Zephyr link provides no `__errno`, which is
  why `sketch.ino` carries its own polynomial exponential. It links.
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

**Hand-work verdict: bucket (b) on the PMDZ, bucket (c) on the EVAL-Z.** The
PMDZ is six Dupont wires (3.3 V from JANALOG/IOREF, GND, MOSI, MISO, SCK, plus
a GPIO chip-select — JSPI has no CS and no 3.3 V pin). The EVAL-Z is twelve
header pins to solder first, then the same number of wires, plus two ground
straps if I2C is used. Neither is a Qwiic cable. The PMDZ is the one to
order: the library's SPI path already accepts a custom `SPIClass`, so no
patch, and SPI also sidesteps the point-to-point I2C bug.

### SCA3300-D01 — disqualified, and for a different reason than expected

**Noise: 44 µg/√Hz typical in Mode 1 (±3 g, 70 Hz), 35 in Modes 3/4 (±1.5 g).**
The cover of the Murata SCA3300-D01 datasheet says "Ultra-low 37 µg/√Hz"; the
specification table does not contain a 37. Cite the table. 2.5x quieter than
the LSM6DSOX in the mode this station would actually use — 5.8-25.2
detections/year.

**Interface: SPI only, confirmed from the 12-pin map.** CSB, MISO, MOSI, SCK,
and nothing else. "3-wire SPI connection is not supported." Frames are 32-bit
off-frame with CRC — not a register SPI. **So a Qwiic connector on any SCA3300
board can carry power and nothing else.** The user's suspicion is correct, and
it is a property of the silicon.

**There is also no SparkFun SCA3300 board.** The catalog of 18 SparkFun
accelerometers (2026-09-01) has none; the product URL, the GitHub library and
the docs page all 404; the retired-product archive has a SCA3000 (SEN-08791)
and nothing later. The "Qwiic-shaped SPI trap" does not exist here because the
board itself does not exist. The Murata Chip Carrier (SCA3300-D01-PCB) is
**discontinued at Digi-Key**, and the MIKROE Inclinometer Click is an SCL3300.

**And there is a worse problem, which is why this is disqualified rather than
merely inconvenient.** The ODR is fixed at 2000 Hz and "if all data is not
read the full noise performance of sensor is not met" — 6000 32-bit SPI frames
per second against a loop measured at 95.3 Hz. There is no SCA3300 library in
the Arduino index.

**Verdict: no.** More firmware work than the ADXL355, for less gain, over a bus
that needs more wires, and no board to buy from a US distributor.

### ISM330DHCX — the only quieter part that actually plugs in

**Noise: 60 µg/√Hz typical, 100 max, high-performance mode, independent of ODR
and full scale** (ST datasheet note 8, verified 2026-09-01). 1.83x quieter.
4.0-18.5 detections/year, 0.30 Mw — the same order as the band-pass just
flashed, not a step change.

**Board: SparkFun 6DoF IMU Breakout - ISM330DHCX (Qwiic), SEN-19764, $25.50,
in stock** on sparkfun.com 2026-09-01. Two real Qwiic connectors, I2C at 0x6B
(0x6A alternate), 3.3 V. **Bucket (a): one Qwiic cable, nothing else.** SparkFun
ships from Boulder, CO; the exact LA delivery date was not confirmed.

**Library: `SparkFun_6DoF_ISM330DHCX` v1.0.6.** `library.properties` has no
`depends=` line — only `Wire.h` and `SPI.h` from the core, so the hermetic
profile needs one entry. `QwI2C::init(TwoWire&)` accepts `Wire1` by design.
Not compiled against `arduino:zephyr` during this survey.

This is a drop-in replacement for the Modulino Movement. The only reason it is
not the recommendation is that ×1.83 does not change the station, and swapping
it now still puts the hardware on the bench for a gain the band-pass already
bought.

### IIS2ICLX — quieter than the ADXL355, and unavailable

**Noise: 15 µg/√Hz typical, 30 max**, independent of the ±0.5/±1/±2/±3 g
range (ST datasheet, verified). 7.3x quieter. 18.5-66.9 detections/year on
paper.

**Interface: native I2C and SPI.** The register map is the LSM6DSO family's —
`CTRL1_XL` at 0x10, the same `HPCF_XL` field this sketch already writes — and
the ODRs include 104 Hz. The firmware would almost port. **It is two axes
(X and Y).** That is a second break in the definition of `pga_g`, after the
band-pass.

**No Qwiic board exists.** The only ready I2C board, MIKROE Inclinometer 2
Click (MIKROE-5156), ships with jumpers in the I2C position, and is **out of
stock everywhere** authorised (MIKROE, SparkFun SEN-20585 retired, TME empty).
Secondary brokers quote 9-14 business days. The ST STEVAL-MKI209V1K ($32.46)
is a DIL24 ribbon, not a plug. **Not a 12-day part, and not a 3-axis one.**

Worth knowing: it is the only non-ADI MEMS that beats the ADXL355 on noise.
Revisit after the contest only if a board reappears.

### ADXL357 — quieter on paper, not where it counts

**Noise: 75 µg/√Hz at ±10 g** (ADXL356/357 datasheet Rev. A; older Pr-D
revisions said 80). Only 1.5x better than the LSM6DSOX, because the part's
point is a ±10/±20/±40 g range. 3.1-14.7 detections/year. Same board problem
as the ADXL355, for a quarter of the benefit. **No.**

### KX134 / KX132 — the trap of a convenient connector

SparkFun sells both as Qwiic breakouts with a maintained library (`SparkFun
KX13X` v2.0.4) that accepts an alternate `TwoWire`. Everything the current
setup has.

**And both are louder than what is already on the board**, from the
manufacturer datasheets, not the shop pages:

- **KX134-1211: 300 µg/√Hz** at ±8 g, ODR 50 Hz (ROHM/Kionix datasheet table 1).
  SparkFun's own page quotes 130; that figure is the sister part. Fitting a
  KX134 would drop the station from 2.0-9.8 detections a year to **0.6-3.1**.
- **KX132-1211: 130 µg/√Hz** (Kionix rev. 1.0); SparkFun says 150. Either way,
  worse than 110. SEN-17871, $15.50, in stock.

This pair is kept because it is the shape of mistake this exercise exists to
avoid: the easiest board to plug in is the one that makes the instrument worse.

### Geophones and a Qwiic ADC — the Raspberry Shake route

A 4.5 Hz geophone with a 24-bit ADC is quieter in 1-10 Hz than any MEMS part
here, including the ADXL355. It is also the wrong answer for the next 12 days,
for reasons that are logistical rather than analog.

**What is actually in stock in the US, 2026-09-01:**

- **SM-24** (ION, 10 Hz, 28.8 V/(m/s), 375 Ω): **$69.95, in stock at SparkFun**
  (Niwot, CO). The only geophone that ships domestically. Its corner is 10 Hz,
  so it misses the lower half of the 1-10 Hz band a local M4 occupies; that is
  compensable digitally, at a cost in firmware.
- **4.5 Hz elements** (Racotech RGI-4.5Hz / Tinyos PS-4.5B / EGL EG-4.5-II,
  ~28.8 V/(m/s)): $33-35 from China, ~10 business days announced, or factory
  quote. None are on a US shelf.
- **No geophone ships with a preamp attached.** GeoMCU and GeophoneDuino are
  KiCad files, not products.

**The ADC half is easier than the literature suggests, and a preamp is not
required.** That last claim is arithmetic, not taste. The SparkFun ADS1219
(SEN-27544, **$14.95, in stock**, two Qwiic ports, 24-bit / 20 effective) at
330 SPS and gain 4 has 4.54 µV rms of input-referred noise. Against a 4.5 Hz
28.8 V/(m/s) geophone, weighted by the geophone's own |H(f)| over 0.7-12 Hz,
that is **2.5×10⁻⁷ g** — 1 400x below the current 0.00036 g floor. Cross-check:
the published RS1D floor is 0.08 µm/s rms on 1-20 Hz; the same chain computed
here is 0.14 µm/s on 1-10 Hz. A factor 1.8 off a commercial instrument, which
is the right order of magnitude.

The NAU7802 (SEN-15242, $5.95) is quieter still and is **the only ADC with a
spring terminal** — press the geophone wires in, no soldering. It is on
**backorder**. The ADS1219 breaks out 0.1" pins and has no screw terminal:
headers have to be soldered, or wires jammed in the holes.

**The chain would be site-limited, not sensor-limited.** The current 0.00036 g
floor only proves the site is quieter than 0.00036 g (~194 µm/s at 2.9 Hz),
which is a loose bound. Urban 1-10 Hz floors measured elsewhere run 10 µm/s
(Taipei, night) to 500 µm/s (Karlsruhe cellars). If this site is the quiet end
of that, the real gain is closer to ×36 than ×1 400 — still seven times the
ADXL355, and enough that M2 at 100 km becomes reachable. The only way to
know is the same two-channel ratio this station already used.

**A geophone measures velocity.** Keep the Python pipeline on PGA: differentiate
inside the existing band-pass (`a_n = (v_n − v_{n-1}) · f_s`) and leave
`REF_GMPE` alone. Switching the whole project to PGV would force a refit of
every number in "Claims discipline" for no scientific gain. Keep the
LSM6DSOX on the bus for tilt and strong motion — that is the RS4D
architecture, and Qwiic is a bus. Polarisation of the floating coil is still
untested: two 100 kΩ resistors to mid-rail, or an asymmetric AINN-to-AGND
trick that the ADS1219 datasheet permits and nobody has confirmed in the
field.

**Not feasible in 12 days.** The only zero-solder ADC is backordered; the only
US-stocked geophone is the wrong corner frequency; and even with both parts on
the table the firmware is 8-13 days (Zephyr driver on `Wire1`, pole
compensation, counts→V→m/s→g, a third schema break). Two contest deliverables
are still missing.

**Worth doing after the contest, and more than the ADXL355** — provided the
site allows it. Order a 4.5 Hz element ($33-35) plus the ADS1219 ($14.95),
keep the Modulino, differentiate in firmware, measure the two-channel ratio.

### Ready-made seismic modules

- **Raspberry Shake RS1D**: $294.99 board / $584.99 turnkey (checked 2026-09-01
  for `docs/hardware.md`). A Raspberry Pi appliance, not an Arduino
  peripheral. It will not accept a different geophone. Buying one replaces
  the project.
- **Grillo OpenEEW / Grillo One / Pulse**: ADXL355-based, which confirms the
  part. **PCBWay out of stock, both shop SKUs sold out**, 2026-09-01. The
  Qwiic port on the OpenEEW node is an *output* for extra sensors, not the
  accelerometer interface (that is ESP32 HSPI).
- **Infiltec QM-4.5LV** ($345, ships in the US): 0.01-1.0 Hz, 16-bit, a
  teleseismic instrument. Wrong band.
- The `SW-420` / `801S` "earthquake sensor modules" are **vibration switches**.
  A spring and a rod. No units, no linearity, no sensitivity. Five to six
  orders of magnitude below the need.

## 4. Recommendation

**The ADXL355 is the only MEMS candidate that changes the answer, and it
should not be attempted before 2026-09-13.** The geophone is the better
long-term instrument, and it is even less of a 12-day job.

Why the ADXL355 is the right *next MEMS*: 4.9x lower noise, 6x the detection
rate, M@30 km from 3.9 to 3.1, P(one in 12 d) from 6-28% to 33-79%. The
ISM330DHCX is the only quieter part that plugs in over Qwiic, and it buys
0.30 Mw — the band-pass already did that. The IIS2ICLX would beat the
ADXL355 on paper (15 µg/√Hz) and has no board. Everything else is louder
than what is fitted, or more work for less gain.

Why not now, stated plainly:

1. **Two contest deliverables are still missing** — the cover photo, which must
   be a text-free shot of the physical station, and the video. Both need the
   station assembled and running. A sensor swap puts the hardware on the bench.
2. **Nothing here is a Qwiic cable except the ISM330DHCX, and that one is not
   worth the bench time.** The ADXL355 path is six Dupont wires onto a PMDZ
   (headers already fitted) plus a SPI rewrite of the sketch. The EVAL-Z still
   needs twelve pins soldered. Either way the station comes off the wall.
3. **The I2C library path needs a patch; the SPI path does not.** `PL ADXL355`
   hardcodes `Wire`. Its SPI entry point already takes a custom `SPIClass`,
   compiles for this core, and avoids the chip's point-to-point I2C bug. That
   is why the PMDZ, not the EVAL-Z, is the board to buy — after the deadline.
4. **A sensor arriving on 10 September is a liability, not an asset.** Order,
   receive, wire, flash, verify, re-measure the two-channel floor. That is not
   a two-day job on a station whose only remote surface is a read-only
   dashboard and which cannot be rebooted remotely.
5. **The upgrade would not rescue the calibration anyway.** At 12.2-47.0
   detections a year the mean wait is still 8-30 days, and the calibration needs
   eight points. The ADXL355 is what makes this station work over a season. It
   is not what makes it work by Sunday week.

**What the deadline actually wants** is the measurement that is already in hand:
the floor is the sensor's own electrical noise, proven in two bands, and the
next gain is therefore hardware. That is a stronger result than a rushed swap,
and it is already written down.

**The mechanical route, for the twelve days that remain**, is treated in
`docs/mechanical-gain.md`: nothing to order, and it answers the one question
this chapter has to leave open — whether the site stays negligible below
0.00036 g. Two sensors reporting an in-band floor over the same ten seconds
measure the site-to-sensor noise ratio directly, and that ratio is what decides
whether the ADXL355's 4.9x survives contact with the room. Its verdict is the
same as this one for the deadline itself: relocate the station, do not rebuild
it.

**After the contest**, two steps, in this order:

1. **ADXL355 first**, because it is a drop-in change of density and nothing
   else. Confirm stock on Mouser/ADI's own pages; order the **EVAL-ADXL355-PMDZ**;
   six Dupont wires to JSPI + JANALOG + a GPIO CS; use the unpatched library
   in SPI; read the two-channel ratio. That is what shows whether the site
   stays negligible at 0.00008 g.
2. **A 4.5 Hz geophone second**, if and only if that ratio says the site has
   room. SM-24 from SparkFun if impatience wins (wrong corner, ships now);
   a Chinese 4.5 Hz element plus the ADS1219 if it can wait ten days. Keep
   the LSM6DSOX. Differentiate in firmware. Do not refit the GMPE.

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
- EVAL-ADXL355-PMDZ uses the Pmod **extended SPI** interface, and its 12-pin
  header is **already soldered** — ADI wiki photograph, board rev.
  `08-043217 REV A`.
- SCA3300-D01: table values 44 µg/√Hz (mode 1) / 35 (modes 3/4), cover-page
  "37" is not in the table; SPI-only 12-pin map, 3-wire unsupported, ODR
  fixed at 2000 Hz with the noise spec conditional on reading every cycle —
  Murata SCA3300-D01 datasheet. No SparkFun SCA3300 board exists (catalog,
  product URL, GitHub, docs, retired archive all checked 2026-09-01).
- `PL ADXL355` v1.4.2 is the only ADXL355 library in the Arduino index; released
  2026-08-27; hardcodes `Wire` at 13 I2C call sites; accepts a custom
  `SPIClass`; **compiles and links for `arduino:zephyr:unoq`**, and still does
  after the `Wire1` substitution — both builds run locally.
- No Qwiic/STEMMA-QT ADXL355 board exists from SparkFun, Adafruit or ADI
  (Mikroe Accel Click is an ADXL345; Accel 16 is an ADXL363; Accel 32 is an
  ADXL382).
- KX134-1211 at **300 µg/√Hz** (ROHM/Kionix datasheet); KX132-1211 at
  **130 µg/√Hz** (Kionix rev. 1.0). Both louder than the LSM6DSOX.
- ISM330DHCX at 60 µg/√Hz (ST datasheet, HP mode, FS-independent);
  SparkFun SEN-19764 $25.50 in stock; library accepts `TwoWire&`.
- IIS2ICLX at 15 µg/√Hz, 2-axis, I2C native (ST datasheet); MIKROE-5156 out
  of stock at every authorised distributor.
- SM-24 $69.95 in stock at SparkFun; ADS1219 SEN-27544 $14.95 in stock;
  NAU7802 SEN-15242 on backorder; Grillo One / Pulse / OpenEEW all sold out
  or out of stock.
- ADXL357 at 75 µg/√Hz ±10 g — ADXL356/357 datasheet Rev. A.
- All detection rates: computed by `tools/sensor-gain.py` over 2185 real USGS
  events, method validated against the published station figures.

**Assumed, or not established — do not treat as settled:**

- **Prices and stock of the EVAL boards.** Every ADXL355 figure came from an
  aggregator; DigiKey/Mouser/Newark blocked automated reads, and the
  aggregators contradict each other (Mouser 135 / 337 / 506 on the same SKU).
  Confirm on the vendors' own pages before ordering. No shipping date to Los
  Angeles was confirmed with any vendor.
- **Whether the EVAL-ADXL355Z bag includes the unsoldered headers.** The
  user guide says the boards "include two 6-pin headers"; the BOM says
  "do not insert". Unresolved.
- **Whether a strap on the PMDZ (SCLK to DGND) would actually enable I2C.**
  The schematic ZIP timed out. Do not plan on it; use SPI.
- **SparkFun ISM330DHCX library on `arduino:zephyr`.** The API is right; it
  was not compiled.
- **The floor-scaling assumption below 1e-4 g**, and every geophone g-equivalent
  below the site's unknown floor. The site was shown to contribute nothing
  resolvable *at 0.00036 g*. It cannot follow that it stays negligible five
  or a thousand times lower.
- **AINN-to-AGND as a solder-free geophone bias.** Permitted by the ADS1219
  abs-max table, untested.
- **NAU7802 noise at 320 SPS.** The datasheet only quotes 10 and 80 SPS; the
  320 SPS figures were extrapolated as √Fe.

## 6. Reproducing the numbers

```bash
python3 tools/sensor-gain.py --lat <station lat> --lon <station lon>
```

Queries USGS directly, or takes a cached geojson as an argument. Without
`--lat/--lon` it falls back to `python/config.example.yaml`, which is downtown
LA and **not** where the board is — that inflates the rates by about 24%,
because the station sits further from the seismicity that dominates the
downtown counts. The station's real position lives only in the board's
gitignored `config.yaml`.
