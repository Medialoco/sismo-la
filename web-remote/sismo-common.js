/* Shared helpers for the public pages (no build step). */
(function (global) {
  'use strict';

  /** Journal list reconciled with live retro findings.

      The published journal is a rolling month, so September scrolls out of
      `confirmed` while the station still holds those findings. A withdrawal
      drops off; a finding the month-long list no longer carries stays. */
  function fromLive(f) {
    const mag = typeof f.magnitude === 'number' ? Math.round(f.magnitude * 100) / 100 : undefined;
    return {
      t: f.origin_time,
      id: f.event_id || '',
      usgs: mag,
      usgs_km: f.distance_km,
      place: f.place || '',
      z: f.z,
      win: f.window_s,
      lag: f.lag_s,
      pga: f.peak_g,
      base: f.baseline_g,
    };
  }

  function confirmedOf(s) {
    if (!s) return null;
    const journal = Array.isArray(s.confirmed) ? s.confirmed : null;
    const retro = s.retro;
    const live = retro && Array.isArray(retro.confirmed) ? retro.confirmed : null;
    if (!(live && live.length && journal)) return journal;
    const ids = new Set(live.map((f) => f.event_id).filter(Boolean));
    if (!ids.size) return journal;
    const kept = journal.filter((c) => c.id && ids.has(c.id));
    const have = new Set(kept.map((c) => c.id));
    for (const f of live) {
      if (f.event_id && !have.has(f.event_id)) kept.push(fromLive(f));
    }
    kept.sort((a, b) => String(b.t || '').localeCompare(String(a.t || '')));
    return kept;
  }

  global.SISMO = { confirmedOf };
})(typeof window !== 'undefined' ? window : globalThis);
