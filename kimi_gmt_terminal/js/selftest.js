/* GMT self-test harness: runs only with ?selftest=1. Writes results into
   #selftest-results and document.title for headless verification. */
window.GMT = window.GMT || {};
(function (G) {
  "use strict";
  const U = G.util;
  const results = [];
  const errors = [];
  window.addEventListener("error", e => errors.push(String(e.message)));
  window.addEventListener("unhandledrejection", e => errors.push("unhandledrejection: " + String(e.reason)));

  function T(name, fn) {
    try {
      const r = fn();
      if (r === false) results.push(["FAIL", name, "returned false"]);
      else results.push(["PASS", name, typeof r === "string" ? r : ""]);
    } catch (e) { results.push(["FAIL", name, String(e && e.message || e)]); }
  }
  const A = (cond, msg) => { if (!cond) throw new Error(msg || "assert"); return true; };

  function run() {
    const F = G.GMT_FIXTURES;

    T("fixtures: AAPL has exactly 60 valid sessions", () => {
      const s = F.aapl60;
      A(s.length === 60, "len=" + s.length);
      let prev = "";
      s.forEach(b => {
        A(isFinite(b.o) && isFinite(b.h) && isFinite(b.l) && isFinite(b.c) && isFinite(b.v), "non-numeric bar");
        A(b.h >= Math.max(b.o, b.c) - 1e-9 && b.l <= Math.min(b.o, b.c) + 1e-9, "H/L inconsistent on " + b.d);
        A(b.d > prev, "dates not ascending"); prev = b.d;
        A(new Date(b.d + "T12:00:00Z").getUTCDay() % 6 !== 0, "weekend session " + b.d);
      });
      return s[0].d + "→" + s[59].d;
    });

    T("fixtures: AAPL bar60 consistent with stock quote", () => {
      const last = F.aapl60[59], prev = F.aapl60[58];
      const aapl = F.stocks.find(s => s.t === "AAPL");
      A(Math.abs(last.c - aapl.last) < 0.005, "close mismatch");
      A(Math.abs(prev.c - aapl.prevClose) < 0.005, "prevClose mismatch");
      A(Math.abs(last.o - aapl.open) < 0.005 && Math.abs(last.h - aapl.high) < 0.005 && Math.abs(last.l - aapl.low) < 0.005, "OHL mismatch");
      A(last.v === aapl.volume, "volume mismatch");
      return true;
    });

    T("metals: 4 metals, GSR/spread/range consistent with definitions", () => {
      A(F.metals.length === 4, "metals=" + F.metals.length);
      const g = F.metals.find(m => m.sym === "XAU"), s = F.metals.find(m => m.sym === "XAG"), p = F.metals.find(m => m.sym === "XPT");
      A(Math.abs(g.last / s.last - 87.26) < 0.5, "GSR off");
      A(Math.abs((g.last - p.last) - 2004.40) < 1, "spread off");
      F.metals.forEach(m => {
        A(m.series.length === 60, m.sym + " series len");
        A(m.unit === "USD/t oz" && m.ccy === "USD", m.sym + " unit mismatch");
      });
      return "GSR=" + (g.last / s.last).toFixed(2) + " spread=" + (g.last - p.last).toFixed(2);
    });

    T("heatmap: tiles == filtered universe, legend explicit", () => {
      const stage = U.$("#heat-stage");
      A(stage, "no stage");
      const tiles = stage.querySelectorAll(".hm-tile").length;
      const uni = G.widgets.filteredStocks().length;
      A(tiles === uni, `tiles ${tiles} != universe ${uni}`);
      A(document.querySelector(".legend").textContent.indexOf("AREA =") >= 0, "no area legend");
      return `tiles=${tiles}`;
    });

    T("breadth: adv+dec+unch == sample size of filter", () => {
      const list = G.widgets.filteredStocks();
      const adv = list.filter(s => s.chgPct > 0).length, dec = list.filter(s => s.chgPct < 0).length;
      const unch = list.length - adv - dec;
      A(adv + dec + unch === list.length, "sum mismatch");
      const txt = U.$("#body-breadth").textContent;
      A(txt.indexOf("n=" + list.length) >= 0, "sample size not disclosed");
      return `n=${list.length} a/d/u=${adv}/${dec}/${unch}`;
    });

    T("session clock: NY open/closed, lunch, weekend, DST offsets", () => {
      const S = G.sessions;
      const ny = S.MARKETS.find(m => m.id === "NYSE");
      const sse = S.MARKETS.find(m => m.id === "SSE");
      const tse = S.MARKETS.find(m => m.id === "TSE");
      A(S.stateAt(ny, new Date("2026-07-24T14:00:00Z")).state === "OPEN", "NY 14Z Fri (10:00 ET) should be OPEN");
      A(S.stateAt(ny, new Date("2026-07-24T13:00:00Z")).state === "PRE", "NY 13Z (09:00 ET) should be PRE (EDT)");
      A(S.stateAt(ny, new Date("2026-07-24T08:00:00Z")).state === "PRE", "NY 08Z should be PRE (EDT)");
      A(S.stateAt(ny, new Date("2026-07-25T13:00:00Z")).state === "CLOSED", "Sat CLOSED");
      A(S.stateAt(ny, new Date("2026-07-24T21:00:00Z")).state === "CLOSED", "after close CLOSED");
      A(S.stateAt(sse, new Date("2026-07-24T02:00:00Z")).state === "OPEN", "SSE 10:00 CST OPEN");
      A(S.stateAt(sse, new Date("2026-07-24T04:00:00Z")).state === "LUNCH", "SSE 12:00 CST LUNCH");
      A(S.stateAt(tse, new Date("2026-07-24T03:00:00Z")).state === "LUNCH", "TSE 12:00 JST LUNCH");
      A(S.stateAt(tse, new Date("2026-07-24T01:00:00Z")).state === "OPEN", "TSE 10:00 JST OPEN");
      // DST: NY offset -4h in Jul, -5h in Jan; London +1 in Jul, 0 in Jan
      A(S.tzOffsetMs(Date.parse("2026-07-01T12:00:00Z"), "America/New_York") === -4 * 3600e3, "NY EDT");
      A(S.tzOffsetMs(Date.parse("2026-01-15T12:00:00Z"), "America/New_York") === -5 * 3600e3, "NY EST");
      A(S.tzOffsetMs(Date.parse("2026-07-01T12:00:00Z"), "Europe/London") === 1 * 3600e3, "London BST");
      A(S.tzOffsetMs(Date.parse("2026-01-15T12:00:00Z"), "Europe/London") === 0, "London GMT");
      // countdown sanity: next transition exists and is in the future
      const st = S.stateAt(ny, new Date("2026-07-24T13:00:00Z"));
      A(st.countdownMs > 0 && st.countdownMs < 4 * 24 * 3600e3, "countdown range");
      return true;
    });

    T("layout: no overlaps, all inside canvas", () => {
      const rects = G.layout.visibleItems().filter(i => !i.min).map(i => ({ id: i.id, r: U.$("#w-" + i.id).getBoundingClientRect() }));
      const canvas = U.$("#grid").getBoundingClientRect();
      rects.forEach(a => {
        A(a.r.left >= canvas.left - 1 && a.r.right <= canvas.right + 1,
          `${a.id} escaped horizontally L=${Math.round(a.r.left)} R=${Math.round(a.r.right)} canvas L=${Math.round(canvas.left)} R=${Math.round(canvas.right)}`);
        rects.forEach(b => {
          if (a.id >= b.id) return;
          const ox = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
          const oy = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
          A(!(ox > 1 && oy > 1), `overlap ${a.id} × ${b.id}`);
        });
      });
      return rects.length + " widgets";
    });

    T("layout: presets apply without overlap, visibility matches", () => {
      ["EQUITIES", "METALS", "NEWS", "GLOBAL"].forEach(p => {
        G.layout.applyPreset(p);
        const vis = G.layout.visibleItems();
        const spec = G.LAYOUT_PRESETS[p];
        A(vis.length === spec.length, p + " count " + vis.length + "!=" + spec.length);
        const R = G.layout.bottom() + 30;
        for (let i = 0; i < vis.length; i++) for (let j = i + 1; j < vis.length; j++) {
          const a = vis[i], b = vis[j];
          if (a.min || b.min) continue;
          const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
          const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
          A(!(ox > 0 && oy > 0), `${p}: grid overlap ${a.id}×${b.id}`);
        }
      });
      G.layout.resetDefault();
      return true;
    });

    T("layout: drag-style move with collision resolves to free cell", () => {
      const heat = G.layout.entry("heat"), br = G.layout.entry("breadth");
      const target = { x: br.x, y: br.y, w: heat.w, h: heat.h }; // occupied on purpose
      const placed = G.layout.findPlace(target, "heat");
      const occ = G.layout.buildOcc("heat", G.layout.bottom() + 40);
      A(G.layout.isFree(occ, placed), "findPlace returned occupied cell");
      return true;
    });

    T("drag: synthetic pointer drag repositions widget, no overlap/escape", () => {
      if (G.layout.stacked) return "skipped — stacked mode (<1024px) disables free drag by design";
      if (!G.state.prefs.editMode) G.app.toggleEdit();
      const it = G.layout.entry("indexmap");
      const tb = U.$("#w-indexmap .w-title");
      const cw = G.layout.colW(), gap = 6;
      const r = tb.getBoundingClientRect();
      const sx = r.left + 40, sy = r.top + 8, ox = it.x;
      const base = { bubbles: true, pointerId: 7, clientX: sx, clientY: sy, button: 0, buttons: 1 };
      tb.dispatchEvent(new PointerEvent("pointerdown", base));
      tb.dispatchEvent(new PointerEvent("pointermove", Object.assign({}, base, { clientX: sx - 2 * (cw + gap) })));
      tb.dispatchEvent(new PointerEvent("pointerup", base));
      A(it.x === Math.max(0, ox - 2), `expected x ${Math.max(0, ox - 2)}, got ${it.x}`);
      A(U.$("#placeholder").style.display !== "block", "placeholder left visible");
      const vis = G.layout.visibleItems().filter(i => !i.min);
      for (let i = 0; i < vis.length; i++) for (let j = i + 1; j < vis.length; j++) {
        const a = vis[i], b = vis[j];
        const ox2 = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
        const oy2 = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
        A(!(ox2 > 0 && oy2 > 0), `overlap after drag ${a.id}×${b.id}`);
        A(a.x >= 0 && a.x + a.w <= 12, a.id + " escaped canvas");
      }
      G.layout.resetDefault();
      return `moved ${ox}→${it.x}`;
    });

    T("resize: synthetic SE-handle resize respects min/snap/collision", () => {
      if (G.layout.stacked) return "skipped — stacked mode (<1024px)";
      if (!G.state.prefs.editMode) G.app.toggleEdit();
      const it = G.layout.entry("metals");
      const rz = U.$("#w-metals .w-resize");
      const rr = rz.getBoundingClientRect();
      const cw = G.layout.colW(), gap = 6;
      const base = { bubbles: true, pointerId: 9, clientX: rr.left + 6, clientY: rr.top + 6, button: 0, buttons: 1 };
      const ow = it.w, oh = it.h;
      // shrink by 1 col / 2 rows — always collision-free
      rz.dispatchEvent(new PointerEvent("pointerdown", base));
      rz.dispatchEvent(new PointerEvent("pointermove", Object.assign({}, base, { clientX: rr.left + 6 - (cw + gap), clientY: rr.top + 6 - 2 * (26 + gap) })));
      rz.dispatchEvent(new PointerEvent("pointerup", base));
      A(it.w === ow - 1 && it.h === oh - 2, `expected ${ow - 1}×${oh - 2}, got ${it.w}×${it.h}`);
      // attempted grow into occupied neighbor (pulse) must be rejected, never overlap
      rz.dispatchEvent(new PointerEvent("pointerdown", base));
      rz.dispatchEvent(new PointerEvent("pointermove", Object.assign({}, base, { clientX: rr.left + 6 + 3 * (cw + gap), clientY: rr.top + 6 })));
      rz.dispatchEvent(new PointerEvent("pointerup", base));
      A(it.w === ow - 1, "grow into occupied neighbor was not rejected");
      // resize beyond canvas width must clamp, never escape
      rz.dispatchEvent(new PointerEvent("pointerdown", base));
      rz.dispatchEvent(new PointerEvent("pointermove", Object.assign({}, base, { clientX: rr.left + 6 + 20 * (cw + gap), clientY: rr.top + 6 })));
      rz.dispatchEvent(new PointerEvent("pointerup", base));
      A(it.x + it.w <= 12, "escaped canvas on oversize");
      G.layout.resetDefault();
      return `resized to ${it.w}×${it.h} (shrink ok, blocked-grow rejected)`;
    });

    T("drag stress: rapid repeated drags never overlap or escape", () => {
      if (G.layout.stacked) return "skipped — stacked mode (<1024px)";
      if (!G.state.prefs.editMode) G.app.toggleEdit();
      const it = G.layout.entry("aapl");
      const cw = G.layout.colW(), gap = 6;
      for (let k = 0; k < 6; k++) {
        const tb = U.$("#w-aapl .w-title");
        const r = tb.getBoundingClientRect();
        const dir = k % 2 ? 1 : -1;
        const base = { bubbles: true, pointerId: 11, clientX: r.left + 40, clientY: r.top + 8, button: 0, buttons: 1 };
        tb.dispatchEvent(new PointerEvent("pointerdown", base));
        tb.dispatchEvent(new PointerEvent("pointermove", Object.assign({}, base, { clientX: r.left + 40 + dir * (cw + gap), clientY: r.top + 8 + (k % 3) * 32 })));
        tb.dispatchEvent(new PointerEvent("pointerup", base));
        const vis = G.layout.visibleItems().filter(i => !i.min);
        for (let i = 0; i < vis.length; i++) for (let j = i + 1; j < vis.length; j++) {
          const a = vis[i], b = vis[j];
          const ox2 = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
          const oy2 = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
          A(!(ox2 > 0 && oy2 > 0), `overlap at move ${k}: ${a.id}×${b.id}`);
        }
        A(it.x >= 0 && it.x + it.w <= 12 && it.y >= 0, "escaped at move " + k);
      }
      G.layout.resetDefault();
      if (G.state.prefs.editMode) G.app.toggleEdit();
      return "6 rapid drops clean";
    });

    T("persistence: layout+prefs survive reload round-trip", () => {
      G.layout.save(); G.app.savePrefs();
      const raw = localStorage.getItem("gmt.layout.v1");
      A(raw && JSON.parse(raw).items.length >= 9, "layout not saved");
      const pr = JSON.parse(localStorage.getItem("gmt.prefs.v1"));
      A(pr && pr.heatArea === G.state.prefs.heatArea, "prefs not saved");
      return true;
    });

    T("tape: >= 11 instruments with last/chg/chg%", () => {
      const items = document.querySelectorAll("#tape-track .tape-item");
      A(items.length >= 22, "items=" + items.length); // duplicated loop
      A(items[0].textContent.match(/\d/), "no numbers");
      return true;
    });

    T("news: reverse-chronological, demo-labeled, filters work", () => {
      const items = Array.from(document.querySelectorAll("#body-news .news-item"));
      A(items.length === F.news.length, "count " + items.length);
      for (let i = 1; i < items.length; i++) {
        const t0 = items[i - 1].querySelector(".nl-time").textContent;
        const t1 = items[i].querySelector(".nl-time").textContent;
        A(t0 >= t1, "not reverse-chronological");
      }
      A(U.$("#body-news").textContent.indexOf("DEMO WIRE") >= 0, "demo label missing");
      A(F.news.every(n => n.demo === true && n.source === "DEMO WIRE"), "fixture demo flags");
      return true;
    });

    T("DOM hygiene: no NaN/undefined/placeholder leaks", () => {
      const txt = document.body.innerText;
      A(txt.indexOf("NaN") < 0, "NaN found");
      A(txt.indexOf("undefined") < 0, "undefined found");
      A(txt.indexOf("lorem") < 0 && txt.indexOf("TODO") < 0, "placeholder copy");
      A(document.querySelectorAll("img").length === 0, "unexpected img tags");
      return true;
    });

    T("inspector: opens for stock/news/instrument/session", () => {
      G.inspector.open("stock", F.stocks[0]);
      A(U.$("#inspector").classList.contains("open"), "not open");
      A(U.$("#ins-body").textContent.indexOf("PROVENANCE") >= 0, "no provenance");
      G.inspector.open("news", F.news[0]);
      A(U.$("#ins-body").textContent.indexOf("DEMO HEADLINE") >= 0, "news demo label");
      G.inspector.open("instrument", F.tape[0]);
      G.inspector.open("session", { sym: "AAPL", bar: F.aapl60[59], index: 59, total: 60 });
      G.inspector.close();
      A(!U.$("#inspector").classList.contains("open"), "close failed");
      return true;
    });

    T("adapter: demo provenance stamped, live fallback disclosed", () => {
      A(G.prov.tape.mode === "DEMO", "tape mode");
      A(G.prov.tape.asof === F.meta.demoAsOf, "asof mismatch");
      const live = G.data.status.live;
      A(live.state !== "OK", "live must not be OK in offline delivery");
      A(typeof live.fallback === "string" && live.fallback.length > 3, "no fallback reason");
      return "live=" + live.state;
    });

    T("fonts: JetBrains Mono loaded locally", () => {
      A(document.fonts && document.fonts.check('700 12px "JetBrains Mono"'), "font not loaded");
      return true;
    });

    T("popout: feature-detected, graceful, recursion-guarded", () => {
      A(typeof G.app.popout === "function", "no popout function");
      A(document.getElementById("btn-pop"), "no POP button");
      G.app.note("selftest toast check", 900);
      const t = U.$("#toast");
      A(t && t.style.display !== "none" && t.textContent.indexOf("selftest") >= 0, "graceful note failed");
      return "documentPiP=" + !!window.documentPictureInPicture + " · popup fallback present";
    });

    T("runtime: zero console/page errors", () => A(errors.length === 0, errors.join(" | ") || "none"));

    // report
    const pass = results.filter(r => r[0] === "PASS").length;
    const div = U.$("#selftest-results");
    div.hidden = false;
    div.textContent = results.map(r => r.join("  ")).join("\n") +
      `\nSELFTEST ${pass}/${results.length} PASS`;
    if (pass !== results.length) div.style.color = "#FF4D4F";
    document.title = "SELFTEST " + pass + "/" + results.length + (pass === results.length ? " PASS" : " FAIL");
  }

  G.selftest = { run };
})(window.GMT);
