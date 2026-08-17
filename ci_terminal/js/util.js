/* GMT util: namespace, DOM helpers, formatting, storage. Plain script (file:// safe). */
window.GMT = window.GMT || {};
window.GMT.GMT_FIXTURES = window.GMT_FIXTURES; // fixtures.js ships a bare global; alias into namespace
(function (G) {
  "use strict";
  const U = {};
  U.$ = (s, r) => (r || document).querySelector(s);
  U.$$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  U.el = function (tag, attrs, kids) {
    const n = document.createElement(tag);
    if (attrs) for (const k in attrs) {
      if (k === "class") n.className = attrs[k];
      else if (k === "text") n.textContent = attrs[k];
      else if (k === "html") n.innerHTML = attrs[k];
      else if (k.startsWith("on") && typeof attrs[k] === "function") n.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] !== null && attrs[k] !== undefined) n.setAttribute(k, attrs[k]);
    }
    if (kids) (Array.isArray(kids) ? kids : [kids]).forEach(c => {
      if (c == null) return;
      n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return n;
  };
  U.clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  U.debounce = (fn, ms) => { let t; return function () { clearTimeout(t); t = setTimeout(() => fn.apply(this, arguments), ms); }; };
  U.esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  U.fmtNum = function (n, dp) {
    if (n === null || n === undefined || !isFinite(n)) return "—";
    return Number(n).toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp });
  };
  U.dpFor = v => (Math.abs(v) >= 1000 ? 2 : Math.abs(v) >= 100 ? 2 : Math.abs(v) >= 10 ? 2 : 3);
  U.sign = v => (v > 0 ? "+" : v < 0 ? "-" : "");
  U.arrow = v => (v > 0 ? "▲" : v < 0 ? "▼" : "•");
  U.cls = v => (v > 0 ? "up" : v < 0 ? "dn" : "flat");
  U.fmtChg = function (v, dp) {
    if (!isFinite(v)) return "—";
    return (v > 0 ? "+" : "") + U.fmtNum(v, dp == null ? 2 : dp);
  };
  U.fmtPct = function (v) {
    if (!isFinite(v)) return "—";
    return (v > 0 ? "+" : "") + v.toFixed(2) + "%";
  };
  U.fmtBig = function (mUsd) { // market cap given in $M
    if (!isFinite(mUsd)) return "—";
    if (mUsd >= 1e6) return (mUsd / 1e6).toFixed(2) + "T";
    if (mUsd >= 1e3) return (mUsd / 1e3).toFixed(1) + "B";
    return mUsd.toFixed(0) + "M";
  };
  U.fmtVol = function (v) {
    if (!isFinite(v)) return "—";
    if (v >= 1e9) return (v / 1e9).toFixed(2) + "B";
    if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
    if (v >= 1e3) return (v / 1e3).toFixed(1) + "K";
    return String(v);
  };
  U.fmtClock = function (d, tz, withSec) {
    try {
      return new Intl.DateTimeFormat("en-GB", {
        timeZone: tz, hour: "2-digit", minute: "2-digit",
        second: withSec ? "2-digit" : undefined, hour12: false
      }).format(d);
    } catch (e) { return "--:--"; }
  };
  U.fmtDate = function (d, tz) {
    try {
      return new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit", weekday: "short" }).format(d);
    } catch (e) { return "----/--/--"; }
  };
  U.tzOffsetLabel = function (d, tz) {
    try {
      const p = new Intl.DateTimeFormat("en-US", { timeZone: tz, timeZoneName: "shortOffset" }).formatToParts(d);
      const tzn = p.find(x => x.type === "timeZoneName");
      return tzn ? tzn.value.replace("GMT", "UTC") : "UTC?";
    } catch (e) { return "UTC?"; }
  };

  /* storage */
  const NS = "gmt.";
  U.store = {
    get(k, dflt) {
      try { const v = localStorage.getItem(NS + k); return v == null ? dflt : JSON.parse(v); }
      catch (e) { return dflt; }
    },
    set(k, v) { try { localStorage.setItem(NS + k, JSON.stringify(v)); } catch (e) { /* private mode */ } },
    del(k) { try { localStorage.removeItem(NS + k); } catch (e) {} }
  };

  /* async helper with timeout (used by live adapter) */
  U.fetchJson = function (url, timeoutMs) {
    return new Promise((resolve, reject) => {
      const ctrl = new AbortController();
      const t = setTimeout(() => { ctrl.abort(); reject(new Error("timeout " + timeoutMs + "ms")); }, timeoutMs || 4000);
      fetch(url, { signal: ctrl.signal, cache: "no-store" })
        .then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
        .then(j => { clearTimeout(t); resolve(j); })
        .catch(e => { clearTimeout(t); reject(e); });
    });
  };
  U.nowIso = () => new Date().toISOString();
  G.util = U;
})(window.GMT);
