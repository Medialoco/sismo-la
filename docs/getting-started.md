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

### Web dashboard (device vs USGS map)
A Leaflet dashboard overlays the USGS catalog (circles at epicenters, colored by
magnitude — same legend as the `quakes.html` tool) with the device's own
detections (intensity circle at the station location, linked to the matched USGS
event for side-by-side comparison).

```bash
cd app
source .venv/bin/activate
python server.py --mock            # then open http://localhost:8000
python server.py --replay          # DEMO/VIDEO mode: replays the last 24h of
                                   # real USGS quakes as if the sensor were
                                   # detecting them live (~1 event / 12 s)
```

In `--replay` mode the map fills up within 2-3 minutes: USGS circles (ground
truth, colored by magnitude) and the device's own estimates in **red** —
estimated epicenter and estimated magnitude, deliberately imperfect (offset
center, over/under-sized circle), with a dashed red error vector between the
two. The side panel shows the live comparison (`device ~M1.4 vs USGS M1.5,
dist ~84 vs 83 km`), the calibration converging, and the AI filter rejecting
noise events (`AI 0% quake`) while confirming real ones (`AI 95%+`). This is
the shot for the contest video.

On the board, run the same command without `--mock` (serial/Bridge source). The
map needs WiFi (Leaflet + tiles + USGS). Display vs correlation thresholds are
split in `config.yaml`: `usgs.display_min_magnitude` controls the map, while
`usgs.min_magnitude` (M2) gates calibration matches.

### Autonomous mode: publish to a remote site
The device can run headless (WiFi + USB-C power only) and push its snapshot to
a public website every minute. Enable the `publish:` block in `config.yaml`:

```yaml
publish:
  enabled: true
  method: command          # post | file | command
  interval_s: 60
  command: "scp -q {file} user@host:/var/www/tools/station.json"
```

- `post` — HTTP POST the JSON to an endpoint you control.
- `file` — atomic write to a local path (synced or served folder).
- `command` — run any upload command (`scp`, `rsync`, `curl -T` for FTP…);
  `{file}` is replaced by the JSON temp-file path.

Then upload `web-remote/sismo.html` next to `station.json` on the site: it is a
fully static page (works on any host, e.g. next to `tools/quakes.html` on
benoit-prieur.fr) that fetches USGS live from the browser and overlays the
station's red estimates from `station.json`. If the station stops publishing,
the page degrades gracefully to a USGS-only map.

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
