/* Shared helpers for the public pages (no build step). */
(function (global) {
  'use strict';

  /** Optional operator clips keyed by USGS event id — not part of the snapshot. */
  const CONFIRMED_MEDIA = {
    ci41545920: {
      href: 'https://www.tiktok.com/@medialocotube/video/7684700897254952206',
      title: 'Short clip about this confirmation',
    },
  };

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

  function mediaAnchor(id, className) {
    const m = CONFIRMED_MEDIA[id];
    if (!m) return '';
    const cls = className || 'src';
    return `<a class="${cls}" href="${m.href}" target="_blank" rel="noopener noreferrer"` +
      ` title="${m.title}">clip</a>`;
  }

  global.SISMO = { confirmedOf, mediaAnchor, CONFIRMED_MEDIA };
})(typeof window !== 'undefined' ? window : globalThis);
