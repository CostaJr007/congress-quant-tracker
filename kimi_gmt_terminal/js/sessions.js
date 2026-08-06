/* GMT session engine: DST-safe market states via Intl, lunch breaks, countdowns.
   No holiday calendar is bundled -> holidays are NEVER inferred; the UI always
   discloses "HOLIDAY STATUS UNVERIFIED". */
window.GMT = window.GMT || {};
(function (G) {
  "use strict";

  /* minutes-of-day helpers */
  const M = (h, m) => h * 60 + (m || 0);

  const MARKETS = [
    { id: "SSE", name: "Shanghai (SSE)", tz: "Asia/Shanghai",
      segments: [[M(9, 30), M(11, 30)], [M(13, 0), M(15, 0)]], lunch: [M(11, 30), M(13, 0)], pre: null },
    { id: "HKEX", name: "Hong Kong (HKEX)", tz: "Asia/Hong_Kong",
      segments: [[M(9, 30), M(12, 0)], [M(13, 0), M(16, 0)]], lunch: [M(12, 0), M(13, 0)], pre: null },
    { id: "TSE", name: "Tokyo (TSE)", tz: "Asia/Tokyo",
      segments: [[M(9, 0), M(11, 30)], [M(12, 30), M(15, 30)]], lunch: [M(11, 30), M(12, 30)], pre: null },
    { id: "LSE", name: "London (LSE)", tz: "Europe/London",
      segments: [[M(8, 0), M(16, 30)]], lunch: null, pre: null },
    { id: "NYSE", name: "New York (NYSE/NASDAQ)", tz: "America/New_York",
      segments: [[M(9, 30), M(16, 0)]], lunch: null, pre: [M(4, 0), M(9, 30)] }
  ];

  /* cached formatters — Intl.DateTimeFormat construction is expensive */
  const _dtfCache = {};
  function _dtf(tz) {
    return _dtfCache[tz] || (_dtfCache[tz] = new Intl.DateTimeFormat("en-US", {
      timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false, weekday: "short"
    }));
  }

  /* wall-clock parts of `date` in timezone tz */
  function partsInTz(date, tz) {
    const p = _dtf(tz).formatToParts(date);
    const o = {};
    p.forEach(x => { o[x.type] = x.value; });
    return {
      y: +o.year, mo: +o.month, d: +o.day,
      wd: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(o.weekday),
      min: (+o.hour % 24) * 60 + (+o.minute), sec: +o.second
    };
  }

  /* offset (ms) of timezone tz at UTC instant utcMs: localWall - utc */
  function tzOffsetMs(utcMs, tz) {
    const w = partsInTz(new Date(utcMs), tz);
    const wallAsUtc = Date.UTC(w.y, w.mo - 1, w.d, Math.floor(w.min / 60), w.min % 60, w.sec);
    return wallAsUtc - utcMs;
  }

  /* UTC instant of a local wall time in tz (DST-safe, one refinement pass) */
  function zonedToUtc(y, mo, d, minutes, tz) {
    const guess = Date.UTC(y, mo - 1, d, Math.floor(minutes / 60), minutes % 60);
    let utc = guess - tzOffsetMs(guess, tz);
    const off2 = tzOffsetMs(utc, tz);
    const utc2 = guess - off2;
    if (utc2 !== utc) utc = utc2;
    return utc;
  }

  function isWeekend(mkt, y, mo, d, tz) {
    const utc = zonedToUtc(y, mo, d, 12 * 60, tz);
    return partsInTz(new Date(utc), tz).wd === 0 || partsInTz(new Date(utc), tz).wd === 6;
  }

  /* state of market at Date `now` -> {state, label, local, next:{utc,state} } */
  function stateAt(mkt, now) {
    const w = partsInTz(now, mkt.tz);
    const mins = w.min + w.sec / 60;
    let state;
    if (w.wd === 0 || w.wd === 6) state = "CLOSED";
    else if (mkt.pre && mins >= mkt.pre[0] && mins < mkt.pre[1]) state = "PRE";
    else if (mkt.segments.some(s => mins >= s[0] && mins < s[1])) state = "OPEN";
    else if (mkt.lunch && mins >= mkt.lunch[0] && mins < mkt.lunch[1]) state = "LUNCH";
    else state = "CLOSED";

    /* next transition: scan boundaries over the next 4 local days */
    const cands = [];
    for (let add = 0; add <= 4; add++) {
      const base = new Date(Date.UTC(w.y, w.mo - 1, w.d + add));
      const yy = base.getUTCFullYear(), mm = base.getUTCMonth() + 1, dd = base.getUTCDate();
      const wd = partsInTz(new Date(zonedToUtc(yy, mm, dd, 720, mkt.tz)), mkt.tz).wd;
      if (wd === 0 || wd === 6) {
        cands.push({ utc: zonedToUtc(yy, mm, dd, 0, mkt.tz), state: "CLOSED" }); // day start (weekend marker)
        continue;
      }
      cands.push({ utc: zonedToUtc(yy, mm, dd, 0, mkt.tz), state: "CLOSED" });
      if (mkt.pre) {
        cands.push({ utc: zonedToUtc(yy, mm, dd, mkt.pre[0], mkt.tz), state: "PRE" });
        cands.push({ utc: zonedToUtc(yy, mm, dd, mkt.pre[1], mkt.tz), state: "OPEN" });
      }
      mkt.segments.forEach((s, i) => {
        if (!mkt.pre || i > 0 || true) cands.push({ utc: zonedToUtc(yy, mm, dd, s[0], mkt.tz), state: "OPEN" });
        const isLast = i === mkt.segments.length - 1;
        cands.push({ utc: zonedToUtc(yy, mm, dd, s[1], mkt.tz), state: isLast ? "CLOSED" : "LUNCH" });
      });
      if (mkt.lunch) cands.push({ utc: zonedToUtc(yy, mm, dd, mkt.lunch[1], mkt.tz), state: "OPEN" });
    }
    const nowMs = now.getTime();
    const future = cands.filter(c => c.utc > nowMs + 500).sort((a, b) => a.utc - b.utc);
    let next = future[0] || null;
    // skip no-op transitions (same state continuing, e.g. midnight CLOSED->CLOSED)
    for (const c of future) { if (c.state !== state) { next = c; break; } }

    const nextLabel = !next ? "—" :
      (next.state === "OPEN" ? "opens" : next.state === "PRE" ? "pre-market" : next.state === "LUNCH" ? "lunch" : "closes");
    return {
      state: state,
      holiday: "UNVERIFIED",
      localMin: w.min, date: w,
      nextUtc: next ? next.utc : null,
      nextState: next ? next.state : null,
      nextVerb: nextLabel,
      countdownMs: next ? next.utc - nowMs : null
    };
  }

  function fmtCountdown(ms) {
    if (ms == null) return "—";
    const s = Math.max(0, Math.floor(ms / 1000));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), ss = s % 60;
    const pad = x => String(x).padStart(2, "0");
    return (h > 0 ? h + ":" : "") + pad(m) + ":" + pad(ss);
  }

  function sessionHoursLabel(mkt) {
    const f = mins => String(Math.floor(mins / 60)).padStart(2, "0") + ":" + String(mins % 60).padStart(2, "0");
    return mkt.segments.map(s => f(s[0]) + "–" + f(s[1])).join(" / ");
  }

  /* 24h map bands in display tz for the display-tz civil date containing `now` */
  function bandsForDisplay(mkt, now, displayTz) {
    const w = partsInTz(now, displayTz);
    const bands = [];
    for (let add = 0; add <= 0; add++) { // single display day; inner k-loop covers tz straddles
      const base = new Date(Date.UTC(w.y, w.mo - 1, w.d + add));
      const yy = base.getUTCFullYear(), mm = base.getUTCMonth() + 1, dd = base.getUTCDate();
      const dayStartUtc = zonedToUtc(yy, mm, dd, 0, displayTz);
      const dayEndUtc = zonedToUtc(yy, mm, dd, 24 * 60 - 1, displayTz) + 60000;
      // market's local civil dates overlapping this display day
      const probe = new Date(dayStartUtc + 12 * 3600 * 1000);
      const mw = partsInTz(probe, mkt.tz);
      const mDates = [];
      for (let k = -1; k <= 1; k++) {
        const mb = new Date(Date.UTC(mw.y, mw.mo - 1, mw.d + k));
        mDates.push([mb.getUTCFullYear(), mb.getUTCMonth() + 1, mb.getUTCDate()]);
      }
      mDates.forEach(dt => {
        const wd = partsInTz(new Date(zonedToUtc(dt[0], dt[1], dt[2], 720, mkt.tz)), mkt.tz).wd;
        if (wd === 0 || wd === 6) return;
        mkt.segments.forEach((s, i) => {
          const a = zonedToUtc(dt[0], dt[1], dt[2], s[0], mkt.tz);
          const b = zonedToUtc(dt[0], dt[1], dt[2], s[1], mkt.tz);
          if (b > dayStartUtc && a < dayEndUtc) {
            bands.push({ a: Math.max(a, dayStartUtc), b: Math.min(b, dayEndUtc), lunch: false });
          }
          if (mkt.lunch && i === 0) {
            const la = zonedToUtc(dt[0], dt[1], dt[2], mkt.lunch[0], mkt.tz);
            const lb = zonedToUtc(dt[0], dt[1], dt[2], mkt.lunch[1], mkt.tz);
            if (lb > dayStartUtc && la < dayEndUtc) {
              bands.push({ a: Math.max(la, dayStartUtc), b: Math.min(lb, dayEndUtc), lunch: true });
            }
          }
        });
      });
    }
    return bands;
  }

  G.sessions = { MARKETS, stateAt, fmtCountdown, sessionHoursLabel, partsInTz, zonedToUtc, tzOffsetMs, bandsForDisplay };
})(window.GMT);
