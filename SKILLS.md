# SKILLS.md — how to work on this repository

Public notes for anyone (including an agent) changing Sismo-LA. Secrets, the
real station position, and session history stay in `AGENTS.md`, which is
gitignored. Do not copy them here.

## What the project is

One unattended strong-motion node in Los Angeles: Arduino UNO Q, Modulino
Movement (LSM6DSOX) on **Wire1**, Bridge RPC from the STM32 to Linux. The USGS
catalog is the external referee. Public page:
<https://medialoco.github.io/sismo-la/>.

Two claims stay separate:

- **Detection** — the blind STA/LTA trigger fired on its own.
- **Confirmation** — the catalog named the second, and the stored envelope was
  elevated there. Confirmations do not train the amplitude model
  (`retro.feed_calibration` is unused). The public list is
  `retro.confirmed`, not every journal row (a false crossing can remain in
  `confirmed` and must be filtered out).

Frozen constants since 1 September 2026 are what make the error rate quotable.
Do not retune a threshold to erase a row.

## Do not publish the station position

`publish.include_location` stays false. Downtown LA in `config.example.yaml` is
a placeholder. Anything per-event and derived from the real coordinates
(distance, predicted amplitude, `P(retro)`) locates the site. The public map is
a disc around the roster pin, not a marker on the house.

## Git

Every commit is `thepriben <5019565+thepriben@users.noreply.github.com>` for
both author and committer. The machine's global identity is a different
account, so pass both explicitly. Never leave
`Co-authored-by: Cursor` in history.

The station appends snapshot commits to `main` about every 20 minutes and does
not force-push. Fetch before pushing. Prefer `--force-with-lease` only when a
rewrite was required. `publi/` is local (excluded from git): the report is
deposited on Zenodo, not read from GitHub.

Concept DOI `10.5281/zenodo.22679542` always resolves to the latest report.
New Zenodo versions use **New version**, not a fresh record.

## Board

Python-only updates: `deploy/push.sh` (`docker restart`, MCU keeps running).
A silent MCU (`mcu_ok: false`, public badge **degraded**) needs
`deploy/reset-mcu.sh`, and if that stays silent,
`arduino-app-cli app restart` on the board, which reflashs the sketch.
`arduino-app-cli app restart` from a host that only wanted to reload Python
halts the MCU.

The dashboard answering HTTP is not proof the sensor is alive. The MCU
heartbeat (~10 s) is.

## Public page

`web-remote/`. Red means a recognised event or a station that is not reporting.
Do not put the audit triple or a false-confirmation essay on the page. Clicking
**Confirmed · known time** shows only the retained confirmations on the map.
