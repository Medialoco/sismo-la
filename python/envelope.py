"""Continuous record of how much the ground moved, second by second.

The station's blind STA/LTA trigger has to decide on its own, from half a second
of signal, whether what it just saw was an earthquake. Testing tens of thousands
of windows a day forces it to demand a large excursion, and on this station's
measured noise that works out to about 2 mg for an earthquake-shaped wavetrain,
i.e. M3.9 at 30 km. Most of southern California's earthquakes are smaller than
that and pass unnoticed.

The USGS publishes the origin time of every one of them. If a record of the
ground motion exists, the arrival instant can be computed after the fact and
looked at directly — a handful of windows per earthquake instead of ~170000 a
day. `retro.py` does that search; this module is the record it searches.

Format, one file per UTC day, `envelope/YYYY-MM-DD.csv`:

    # sismo-la envelope v1 band=0.7-12Hz unit=ug bucket_ms=1000
    <ms since midnight UTC>,<peak ug>,<rms ug>

Plain text on purpose: it has to be greppable on a board with no shell, and the
storage argument is already won — 19 bytes a second is 1.6 MB a day, against
954 MB free. It is still capped: `retention_days` is enforced on every rollover,
because that free space is 10% of the disk and an unattended station must not be
the thing that fills it.

TIMING — read this before touching `append_batch`.
The MCU stamps its buckets with `millis()`, and this MCU's clock runs 1099 ppm
slow against the board's NTP-synced clock (measured over a 2.6 h run: 9331.8 s
of MCU time for 9342.1 s of wall time, 10.3 s of accumulated error). An absolute
timestamp derived from `millis()` and a boot-time offset would therefore drift
straight through the width of the arrival window the search uses, and it would do
it silently — the file would look perfectly well-formed. So each batch is
re-anchored on the wall clock at the moment it arrives, and the MCU's
milliseconds are used only for the offsets *within* that batch, where the same
drift amounts to 11 ms.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone

HEADER = "# sismo-la envelope v1 band=0.7-12Hz unit=ug bucket_ms=1000\n"
_DAY_FILE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.csv$")


class EnvelopeStore:
    """Append-only, one file per UTC day. Never raises on a write."""

    def __init__(self, directory: str, retention_days: int = 14) -> None:
        self.directory = directory
        self.retention_days = int(retention_days)
        self.enabled = bool(directory)
        self.samples_written = 0
        self.last_write: datetime | None = None
        self._last_day = ""

    # --- writing ----------------------------------------------------------
    def append_batch(self, payload: str, n: int, bucket_ms: int,
                     received: datetime) -> int:
        """Store one MCU batch.

        ``payload`` is ``"peak_ug:rms_ug,..."``, oldest bucket first, the last
        one ending at ``received``. Returns the number of samples stored.
        """
        if not self.enabled:
            return 0
        rows = []
        parts = [p for p in payload.split(",") if p]
        for index, part in enumerate(parts[:n]):
            peak, _, rms = part.partition(":")
            try:
                peak_ug, rms_ug = int(peak), int(rms)
            except ValueError:
                continue
            # bucket `index` ends (len-1-index) buckets before the batch does
            offset = (len(parts) - 1 - index) * bucket_ms
            rows.append((received - timedelta(milliseconds=offset),
                         peak_ug, rms_ug))
        written = 0
        for when, peak_ug, rms_ug in rows:
            if self._write(when, peak_ug, rms_ug):
                written += 1
        if written:
            self.samples_written += written
            self.last_write = received
        return written

    def _write(self, when: datetime, peak_ug: int, rms_ug: int) -> bool:
        day = when.strftime("%Y-%m-%d")
        midnight = when.replace(hour=0, minute=0, second=0, microsecond=0)
        ms = int((when - midnight).total_seconds() * 1000)
        path = os.path.join(self.directory, f"{day}.csv")
        try:
            os.makedirs(self.directory, exist_ok=True)
            new = not os.path.exists(path)
            with open(path, "a", encoding="utf-8") as f:
                if new:
                    f.write(HEADER)
                f.write(f"{ms},{peak_ug},{rms_ug}\n")
        except OSError as e:
            print(f"[envelope] could not append: {e}", flush=True)
            return False
        if day != self._last_day:
            self._last_day = day
            self.purge()
        return True

    def purge(self) -> list[str]:
        """Delete day files older than ``retention_days``. Returns what went."""
        if not self.enabled or self.retention_days <= 0:
            return []
        cutoff = (datetime.now(timezone.utc)
                  - timedelta(days=self.retention_days)).strftime("%Y-%m-%d")
        removed = []
        for day in self.days():
            if day < cutoff:
                try:
                    os.remove(os.path.join(self.directory, f"{day}.csv"))
                    removed.append(day)
                except OSError:
                    pass
        if removed:
            print(f"[envelope] purged {', '.join(removed)}", flush=True)
        return removed

    # --- reading ----------------------------------------------------------
    def days(self) -> list[str]:
        try:
            names = os.listdir(self.directory)
        except OSError:
            return []
        return sorted(m.group(1) for m in
                      (_DAY_FILE.match(n) for n in names) if m)

    def read(self, start: datetime, end: datetime) -> list[tuple[float, float, float]]:
        """Samples in [start, end] as (epoch_s, peak_g, rms_g), time-ordered.

        Reads whole day files and filters: a day is 86400 lines, which is a
        few MB and well under a second, and the alternative (an index) is a
        second thing that can disagree with the data.
        """
        out: list[tuple[float, float, float]] = []
        day = start.astimezone(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0)
        last = end.astimezone(timezone.utc)
        t0, t1 = start.timestamp(), end.timestamp()
        while day <= last:
            path = os.path.join(self.directory, day.strftime("%Y-%m-%d.csv"))
            base = day.timestamp()
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line or line[0] == "#":
                            continue
                        try:
                            ms, peak, rms = line.split(",")
                            epoch = base + int(ms) / 1000.0
                            if t0 <= epoch <= t1:
                                out.append((epoch, int(peak) / 1e6,
                                            int(rms) / 1e6))
                        except ValueError:
                            continue
            except OSError:
                pass
            day += timedelta(days=1)
        out.sort(key=lambda r: r[0])
        return out

    def coverage(self) -> dict:
        """What the search actually has to work with."""
        days = self.days()
        total = 0
        for day in days:
            path = os.path.join(self.directory, f"{day}.csv")
            try:
                total += os.path.getsize(path)
            except OSError:
                pass
        return {
            "days": len(days),
            "first_day": days[0] if days else None,
            "last_day": days[-1] if days else None,
            "bytes": total,
            "retention_days": self.retention_days,
            "samples_written": self.samples_written,
            "last_write": self.last_write.isoformat() if self.last_write else None,
        }
