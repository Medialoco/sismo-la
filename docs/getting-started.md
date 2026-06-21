# Getting started — end-to-end checklist

The full path from zero to a calibrating seismograph. Tick as you go.

## 0. Software chain (no hardware needed) — DONE
- [x] Python venv + dependencies installed (`app/.venv`).
- [x] Live USGS fetch verified (M3+ around LA, distances computed).
- [x] Full pipeline runs in `--mock` mode.

```bash
cd app
source .venv/bin/activate
python main.py --mock
```

## 1. App Lab — Network setup (GUI, you do it)
- [ ] Select your WiFi SSID and enter the password (2.4 or 5 GHz).
- [ ] Wait for "Connected" + an IP.
- [ ] Avoid guest networks with a captive portal; the board must reach
      `https://earthquake.usgs.gov`.

## 2. App Lab — Board config (GUI, you do it)
- [ ] Board name, e.g. `uno-q-sismo`.
- [ ] Confirm model: Arduino UNO Q (4 GB).
- [ ] If asked, create Linux (MPU) user + password — **write them down**.
- [ ] Accept any OS/firmware update App Lab offers.

## 3. Verify internet from the board (terminal on the board's Linux)
Once online, from the App Lab board terminal (or SSH):

```bash
curl -s "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&latitude=34.0522&longitude=-118.2437&maxradiuskm=160&minmagnitude=3&limit=1" | head -c 300
```
- [ ] Returns GeoJSON → the board can reach USGS.

## 4. Sensor
- [ ] Buy **Modulino Movement (ABX00101)** — includes a 5 cm Qwiic cable.
- [ ] Plug it into the UNO Q **Qwiic** port (bus `Wire1` on the UNO Q).
- [ ] Mount it rigidly to a solid surface (see `hardware.md`).

## 5. Flash & first signal (MCU)
- [ ] Build/flash `firmware/seismo_mcu/seismo_mcu.ino` via App Lab.
- [ ] Open the serial monitor at 115200 baud, tap the desk.
- [ ] See JSON lines: `{"t_ms":...,"pga_g":...,"dur_ms":...,"dom_hz":...}`.

## 6. Wire MCU → Linux
- [ ] Replace the prototype serial transport with the App Lab **Bridge (RPC)**.
- [ ] Point `app/config.yaml` `source.type` to the real source.
- [ ] Run `app/main.py` on the board; confirm shakes flow through.

## 7. Calibration & AI (over time)
- [ ] Let it run in LA; accumulate M3+ correlations (calibration points).
- [ ] Collect noise samples (truck, door, footsteps) for Edge Impulse.
- [ ] Train + deploy the earthquake-vs-noise classifier.

## 8. Hackster write-up
- [ ] Follow `hackster-submission.md` (cover image, story in steps, code snippets…).
- [ ] Deadline: August 30, 2026.
