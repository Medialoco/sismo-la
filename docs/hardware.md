# Hardware: parts to buy and how to wire them

This project is deliberately **low-cost**: the value comes from the software
(STA/LTA + USGS calibration + edge AI), not from expensive sensors.

## Bill of materials (BOM)

| # | Part | Qty | Why | Approx. price |
|---|------|-----|-----|---------------|
| 1 | **Arduino UNO Q (4 GB)** | 1 | The board (Dragonwing MPU + STM32 MCU, WiFi) | provided by the contest, or ~$45–55 |
| 2 | **IMU / accelerometer over I²C** — see options below | 1 | Senses ground motion | ~$8–17 |
| 3 | **Qwiic cable** (JST-SH 4-pin) | 1 | Plug-and-play I²C to the UNO Q | ~$1.5 (often included) |
| 4 | **USB-C cable + power supply** | 1 | Powers the board (PD recommended) | ~$10 |

Optional (nice for the demo / dashboard):

| # | Part | Qty | Why |
|---|------|-----|-----|
| 5 | USB-C dongle/dock with HDMI + USB + PD | 1 | Show the dashboard locally on a screen |
| 6 | HDMI display + USB keyboard/mouse | 1 | Standalone use of the Linux side |
| 7 | Small enclosure + a bit of rigid coupling | 1 | Couple the sensor firmly to the floor/wall (better signal) |

### IMU options (pick one)

The recommended sensor is the same family used in real low-cost seismic projects
(a MEMS IMU). Any of these work over I²C:

- **Arduino Modulino Movement** (LSM6DSOX, 6-axis) — *recommended*: Qwiic, truly
  plug-and-play with the UNO Q, matches the `firmware/seismo_mcu` code as-is.
- **SparkFun / Adafruit LSM6DSOX breakout** — same chip, often has a Qwiic/STEMMA
  QT connector too.
- **MPU-6050 breakout** — cheapest, very common, but noisier; adapt the library
  in the sketch.
- **ADXL345 breakout** — 3-axis accelerometer only; fine for shake detection.

> The firmware currently targets the **LSM6DSOX via the `Modulino` library**.
> If you choose another chip, swap the sensor library and the read calls in
> `firmware/seismo_mcu/seismo_mcu.ino` (the `readDynamicMagnitude()` function).

## Wiring

### Option A — Modulino Movement over Qwiic (recommended, no soldering)

1. Take the **Qwiic cable**.
2. Plug one end into the **Qwiic connector on the UNO Q**.
3. Plug the other end into **either Qwiic port on the Modulino Movement**
   (the two ports are equivalent; the second lets you daisy-chain more Modulinos).
4. Power the UNO Q via **USB-C**. Done — no breadboard, no soldering.

```
 UNO Q  ──Qwiic cable──►  Modulino Movement (LSM6DSOX)
 (Qwiic)                  (Qwiic in / out)
```

The Qwiic connector already carries the 4 I²C signals:

| Qwiic pin | Signal |
|-----------|--------|
| 1 | GND |
| 2 | 3.3 V |
| 3 | SDA |
| 4 | SCL |

### Option B — generic I²C breakout (jumper wires)

If you use a non-Qwiic breakout, connect 4 wires to the UNO headers:

| Breakout pin | UNO Q pin | Notes |
|--------------|-----------|-------|
| VCC / VIN | **3.3 V** | use 3.3 V unless the board explicitly needs 5 V |
| GND | **GND** | common ground |
| SDA | **SDA** (also exposed as A4) | I²C data |
| SCL | **SCL** (also exposed as A5) | I²C clock |

```
 Breakout            UNO Q
 ┌──────┐            ┌──────────┐
 │ VCC ─┼────────────┤ 3.3V     │
 │ GND ─┼────────────┤ GND      │
 │ SDA ─┼────────────┤ SDA (A4) │
 │ SCL ─┼────────────┤ SCL (A5) │
 └──────┘            └──────────┘
```

Most breakouts already have I²C pull-up resistors; if yours does not and the bus
is unreliable, add 4.7 kΩ pull-ups from SDA and SCL to 3.3 V.

## Physical mounting (matters for signal quality)

A seismograph is only as good as its coupling to the ground:

- Mount the sensor **rigidly** to a solid surface (concrete floor, load-bearing
  wall), not on a wobbly desk.
- Keep it away from fans, HVAC, fridges and foot traffic (those are the "noise"
  the edge-AI model will have to reject).
- Once placed, **do not move it**: calibration is site-specific (see
  `calibration.md`).

## Quick check

- The IMU should appear on the I²C bus (LSM6DSOX default address `0x6A` or `0x6B`).
- Upload the sketch, open the serial monitor at **115200 baud**, then tap the desk:
  you should see JSON event lines like
  `{"t_ms":...,"pga_g":0.0123,"dur_ms":...,"dom_hz":...}`.

## To produce for the Hackster write-up

- [ ] A real photo of the UNO Q + IMU assembled.
- [ ] A clean **Fritzing** schematic (replaces the ASCII diagrams above).
- [ ] A short clip showing a tap on the desk triggering an event.
