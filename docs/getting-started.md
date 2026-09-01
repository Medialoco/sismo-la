# Getting started — end-to-end checklist

The full path from zero to a calibrating seismograph. Tick as you go.

## 0. Software chain (no hardware needed) — DONE
- [x] Python venv + dependencies installed (`python/.venv`).
- [x] Live USGS fetch verified (M2+ around LA, distances computed).
- [x] Full pipeline runs in `--mock` mode.

```bash
cd python
source .venv/bin/activate
python pipeline.py --mock          # headless variant
```

### Web dashboard (device vs USGS map)
A Leaflet dashboard overlays the USGS catalog (circles at epicenters, colored by
magnitude — same legend as the `quakes.html` tool) with the device's own
detections (intensity circle at the station location, linked to the matched USGS
event for side-by-side comparison).

```bash
cd python
source .venv/bin/activate
python main.py --mock              # then open http://localhost:8000
python main.py --replay            # DEMO/VIDEO mode: replays the last 24h of
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

The public page is `web-remote/index.html`, and this repository already
publishes it on GitHub Pages (`.github/workflows/pages.yml` serves everything
under `web-remote/`). It fetches USGS live from the browser and overlays the
station's readings from a `station.json` sitting beside it, so the target of
`publish:` has to be `web-remote/station.json` in this repository. Every
snapshot commit redeploys the page, so `interval_s` is 1800 — one push every
half hour, and a snapshot that differs only by its clock is skipped entirely.
Nothing is lost in between: each snapshot carries the whole confirmed history,
rebuilt from the journal.

Three things have to line up, and missing any one of them looks identical from
outside — a page with no device data:

- [ ] **A `config.yaml` on the board.** Without one the app silently falls back
      to `config.example.yaml`, where publishing is off. Check the startup log
      for a `[Sismo-LA] publisher on (...)` line; no line, no publisher.
- [ ] **`publish.enabled: true`** in that file.
- [ ] **A token the container can read.** App Lab builds the container's compose
      file from `app.yaml`, which has no field for environment variables, and
      regenerates it on every start — so a secret cannot be passed through the
      environment. The app folder is bind-mounted at `/app`, so put the token in
      a file there instead:

      ```bash
      printf '%s' 'github_pat_...' > ~/ArduinoApps/sismo-la/.sismo-token
      chmod 600 ~/ArduinoApps/sismo-la/.sismo-token
      ```

      Use a *fine-grained* token limited to this one repository with
      "Contents: read and write" and nothing else. `.sismo-token` is gitignored;
      this repository is public, and committing it would hand anyone write
      access.

The page is fully self-contained, so it works just as well dropped on any
other static host. If the station publishes nothing, the page shows the USGS
catalogue alone rather than breaking.

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

## 5. Bring the board's toolchain up to date (do this FIRST)
The stock image can ship a zephyr core too old to build *any* Bridge app —
including Arduino's own examples. Symptom: `MsgPack.h: No such file or
directory`, or a `RPCClient::get_response` argument-count error.

- [ ] On the board: `arduino-cli lib update-index && arduino-cli core update-index`
- [ ] `arduino-cli core install arduino:zephyr@0.90.0`
      (confined to `~/.arduino15`; no `apt`, no `dpkg`, reversible)
- [ ] Sanity check with an official app first, so a later failure is
      unambiguously yours: `arduino-app-cli app start examples:blink-with-ui`,
      then `arduino-app-cli app stop examples:blink-with-ui`.

## 6. Run it as one App (both halves together)
- [ ] Copy the repo to the board, e.g.
      `COPYFILE_DISABLE=1 tar --exclude=.git -czf - sismo-la | ssh arduino@<board-ip> 'tar xzf - -C ~/ArduinoApps'`.
      The `COPYFILE_DISABLE=1` matters on macOS: without it the archive carries
      AppleDouble `._*` files into the app folder.
- [ ] `arduino-app-cli app start ~/ArduinoApps/sismo-la` — builds the sketch,
      flashes the MCU, installs `python/requirements.txt`, runs `python/main.py`.
      No `config.yaml` is needed: it falls back to `config.example.yaml`.
- [ ] `arduino-app-cli app logs ~/ArduinoApps/sismo-la` — both halves interleaved.
      Within ~10 s you should see `mcu status: noise floor ready`, then a
      `mcu alive ... dyn=0.0007g` heartbeat. A `dyn` that moves is your proof
      the IMU is really being read.
- [ ] Tap the desk; expect a line like
      `shake PGA=0.0224g dur=583ms f=2.6Hz no USGS match`.
- [ ] **Check `dom_hz` actually varies between taps.** It was stuck near 25 Hz
      until the sign-test fix of 2026-08-31; a constant value means the fix did
      not take, and both the distance model and the AI filter run blind.
      Confirmed working on hardware: 2.57 / 4.99 / 10.60 Hz on three taps.
- [ ] Open `http://<board-ip>:8000` for the dashboard.

Note on transports: the app defaults to `source.type: bridge`, the only one
that works on the board. App Lab runs the Python half in a container, where the
MCU's `Monitor` stream is unreachable but the router socket is mounted — so the
sketch pushes each detection as a `seismic_event` RPC notification. `monitor`
and `serial` remain for host-side debugging.

## 7. Calibration & AI (over time)
- [ ] Let it run in LA; accumulate M2+ correlations (calibration points).
- [ ] Collect noise samples (truck, door, footsteps) for Edge Impulse.
- [ ] Train + deploy the earthquake-vs-noise classifier.

### Grading the calibration honestly
Every detection is appended to `event_log.jsonl` with what the models predicted
*before* they learned it, so the journal can be replayed for out-of-sample
residuals rather than the training ones the dashboard shows.

```bash
python audit.py                      # the honest scoreboard
python audit.py --include-synthetic  # also score --replay events (circular)
```

Read the operational line first: it estimates distance from the shake, as the
station must in the field. It is the only figure that describes what the device
can really do, and it is several times worse than the panel's number.

## 8. Media for the submission
- [ ] Restart `python main.py --replay` so calibration starts from zero.
- [ ] `./tools/capture-timelapse.sh 48` — screenshots the dashboard and
      assembles `calibration-timelapse.mp4`. Convergence is invisible if the
      model is already trained, hence the restart.
- [ ] Shoot the live tap last: it needs retakes, and the MCU heartbeat should be
      on camera before you tap so the sensor is visibly alive.
- [ ] Narration and subtitles: `docs/video-script.md`, `docs/video/narration.srt`.

## 9. Hackster write-up
- [ ] Follow `hackster-submission.md` (cover image, story in steps, code snippets…).
- [ ] Deadline: September 13, 2026.
