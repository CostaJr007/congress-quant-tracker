/* GMT acceptance harness: runs only with ?accept=1. Loaded BEFORE all other app
   scripts so it can instrument Intl.DateTimeFormat construction, setTimeout
   scheduling and error channels from the very first byte. Writes results into
   #accept-results and document.title ("ACCEPT n/n PASS") for headless capture.
   Zero overhead in normal use: everything below is skipped without the param. */
window.GMT = window.GMT || {};
(function (G) {
  "use strict";
  if (location.search.indexOf("accept=1") < 0) return;

  /* ---- instrumentation ------------------------------------------------- */
  const errors = [];
  window.addEventListener("error", e => {
    errors.push(e.target && e.target !== window ? "resource: " + (e.target.src || e.target.href || e.target.tagName) : String(e.message));
  }, true); // capture phase: also catches failed <script>/<link>/<img> loads
  window.addEventListener("unhandledrejection", e => errors.push("unhandledrejection: " + String(e.reason)));
  const nativeConsoleError = console.error.bind(console);
  let consoleErrors = 0;
  console.error = function () { consoleErrors++; return nativeConsoleError.apply(null, arguments); };

  const NativeDTF = Intl.DateTimeFormat;
  let dtfCount = 0;
  Intl.DateTimeFormat = function (loc, opt) { dtfCount++; return new NativeDTF(loc, opt); };
  Intl.DateTimeFormat.prototype = NativeDTF.prototype;
  Intl.DateTimeFormat.supportedLocalesOf = NativeDTF.supportedLocalesOf.bind(NativeDTF);

  const nativeST = window.setTimeout.bind(window);
  const nativeCT = window.clearTimeout.bind(window);
  const pending = new Set();
  let stCalls = 0;
  window.setTimeout = function (fn, ms) {
    stCalls++;
    const rest = Array.prototype.slice.call(arguments, 2);
    const id = nativeST(function () { pending.delete(id); fn.apply(null, rest); }, ms);
    pending.add(id);
    return id;
  };
  window.clearTimeout = function (id) { pending.delete(id); return nativeCT(id); };
  const sleep = ms => new Promise(res => nativeST(res, ms)); // harness-internal: NOT counted

  /* ---- helpers --------------------------------------------------------- */
  function snapshotState() {
    return JSON.stringify({
      edit: G.state.prefs.editMode, tape: G.state.prefs.tapePaused,
      add: document.getElementById("addmenu").classList.contains("open"),
      ds: document.getElementById("dstatus").classList.contains("open"),
      layout: G.layout.layout.map(i => [i.id, i.x, i.y, i.w, i.h, i.visible === false ? 0 : 1])
    });
  }
  function key(k, mods) {
    document.dispatchEvent(new KeyboardEvent("keydown", Object.assign({ key: k, bubbles: true, cancelable: true }, mods || {})));
  }

  /* ---- run -------------------------------------------------------------- */
  function run() {
    const R = [];
    const T = (name, ok, detail) => R.push([ok ? "PASS" : "FAIL", name, detail || ""]);
    (async () => {
      // 1. horizontal overflow at this viewport
      const de = document.documentElement;
      const ovX = Math.max(de.scrollWidth, document.body ? document.body.scrollWidth : 0) - window.innerWidth;
      T("horizontal overflow == 0 @ " + window.innerWidth + "px viewport", ovX === 0, "scrollWidth-innerWidth=" + ovX);

      // 2. all 9 command-bar buttons hittable (scrollIntoView + elementFromPoint)
      const btns = Array.from(document.querySelectorAll("#cmdbar button"));
      let hits = 0;
      btns.forEach(b => {
        b.scrollIntoView({ block: "nearest", inline: "center" });
        const r = b.getBoundingClientRect();
        const at = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        if (at === b || b.contains(at)) hits++;
      });
      T("all 9 cmdbar buttons hittable", btns.length === 9 && hits === 9, hits + "/" + btns.length + " hittable");

      // 3. modifier chords must not trigger app actions
      const s0 = snapshotState();
      key("r", { metaKey: true }); key("r", { ctrlKey: true }); key("a", { metaKey: true });
      key("d", { metaKey: true }); key("t", { metaKey: true }); key("e", { metaKey: true });
      const s1 = snapshotState();
      T("Cmd/Ctrl+R,A,D,T,E trigger no app action", s0 === s1, s0 === s1 ? "app state identical before/after chords" : "STATE CHANGED");

      // 4. plain keys still work (regression guard) + custom layout survives Cmd+R
      const e0 = G.state.prefs.editMode;
      key("e"); const e1 = G.state.prefs.editMode;
      key("e"); const e2 = G.state.prefs.editMode;
      G.layout.applyPreset("METALS"); // a real customization (persisted to localStorage)
      const before = snapshotState();
      const stored = (localStorage.getItem("gmt.layout.v1") || "").length > 2; // custom layout persisted → a real reload restores it
      key("r", { metaKey: true }); key("r", { ctrlKey: true });
      const after = snapshotState();
      G.layout.applyPreset("GLOBAL"); // restore
      T("plain keys work · customized layout survives Cmd+R unchanged", e1 === !e0 && e2 === e0 && before === after && stored,
        "edit " + e0 + "→" + e1 + "→" + e2 + " · layout identical=" + (before === after) + " · persisted=" + stored);

      // 5. Intl.DateTimeFormat construction rate in steady state
      const d0 = dtfCount, t0 = Date.now();
      await sleep(2000);
      const dtfRate = (dtfCount - d0) / ((Date.now() - t0) / 1000);
      T("Intl.DateTimeFormat constructions/sec < 200", dtfRate < 200, dtfRate.toFixed(1) + "/s steady-state (was 6736/s pre-fix)");

      // 6. pending setTimeout timers must not grow after 10x full re-render
      const p0 = pending.size;
      for (let i = 0; i < 10; i++) G.app.renderAll();
      await sleep(1500); // transient pulse-tick timeouts (1s) fire and die via gen-guard
      const p1 = pending.size;
      T("pending setTimeout stable after 10x rerender", p1 <= p0, p0 + " → " + p1 + " (no leak/growth)");

      // 7. setTimeout rate after 8x window resize == x1.0
      const c0 = stCalls, u0 = Date.now();
      await sleep(2000);
      const rate0 = (stCalls - c0) / ((Date.now() - u0) / 1000);
      for (let i = 0; i < 8; i++) { window.dispatchEvent(new Event("resize")); await sleep(300); }
      await sleep(500);
      const c1 = stCalls, u1 = Date.now();
      await sleep(2000);
      const rate1 = (stCalls - c1) / ((Date.now() - u1) / 1000);
      const ratio = rate0 > 0.01 ? rate1 / rate0 : 1;
      T("setTimeout rate after 8x resize == x1.0", ratio >= 0.5 && ratio <= 1.5,
        "x" + ratio.toFixed(2) + " (" + rate0.toFixed(1) + "/s → " + rate1.toFixed(1) + "/s)");

      // 8. zero console/page/request errors across the whole run
      T("zero console/page/request errors", errors.length === 0 && consoleErrors === 0,
        errors.slice(0, 3).join(" | ") + (consoleErrors ? " console.error×" + consoleErrors : "") || "none");

      // report
      const pass = R.filter(r => r[0] === "PASS").length;
      const div = document.getElementById("accept-results");
      div.hidden = false;
      div.textContent =
        "GMT ACCEPTANCE — viewport " + window.innerWidth + "x" + window.innerHeight + "\n" +
        R.map(r => r.join("  ")).join("\n") + `\nACCEPT ${pass}/${R.length} PASS`;
      if (pass !== R.length) div.style.color = "#FF4D4F";
      document.title = "ACCEPT " + pass + "/" + R.length + (pass === R.length ? " PASS" : " FAIL");
    })().catch(e => {
      const div = document.getElementById("accept-results");
      div.hidden = false;
      div.textContent = "ACCEPT HARNESS ERROR: " + (e && e.message || e);
      document.title = "ACCEPT HARNESS ERROR";
    });
  }

  G.accept = { run };
})(window.GMT);
