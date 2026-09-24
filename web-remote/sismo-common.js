/* Shared helpers for the public pages (no build step). */
(function (global) {
  'use strict';

  /** Journal list reconciled with live retro findings (withdrawals drop off). */
  function confirmedOf(s) {
    if (!s) return null;
    const journal = Array.isArray(s.confirmed) ? s.confirmed : null;
    const retro = s.retro;
    const live = retro && Array.isArray(retro.confirmed) ? retro.confirmed : null;
    if (live && live.length && journal) {
      const ids = new Set(live.map((f) => f.event_id).filter(Boolean));
      if (ids.size) return journal.filter((c) => c.id && ids.has(c.id));
    }
    return journal;
  }

  global.SISMO = { confirmedOf };
})(typeof window !== 'undefined' ? window : globalThis);
