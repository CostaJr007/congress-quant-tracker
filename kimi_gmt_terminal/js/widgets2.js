/* GMT widgets part 2: sector intraday, news wire, AAPL, metals, pulse, index map. */
window.GMT = window.GMT || {};
(function (G) {
  "use strict";
  const U = G.util, el = U.el;
  const W = G.widgets.WIDGETS;

  /* ---------- D. SECTOR INTRADAY ---------- */
  W.sector = {
    num: "04", title: "SECTOR INTRADAY · NORMALIZED", min: [4, 4],
    render(body) {
      const sets = G.datasets.sectors;
      const bar = el("div", { class: "toolbar" });
      bar.appendChild(el("span", { class: "chip demo", text: "DEMO DATA" }));
      bar.appendChild(el("span", { class: "faint", style: "font-size:9px", text: "24 equal-interval pts · baseline open = 0% · equal-weight sector average of universe constituents" }));
      body.appendChild(bar);
      const box = el("div", { style: "position:relative;height:42%;min-height:110px;flex:0 0 auto" });
      body.appendChild(box);
      requestAnimationFrame(() => G.charts.miniLines(box, sets, { aria: "sector intraday normalized series", labels: false }));
      const colors = { "AI-TECH": "#00C176", "ENERGY": "#FFB454", "FINANCIALS": "#3FA7A3" };
      const lg = el("div", { class: "legend", style: "padding:2px 8px" });
      sets.forEach(st => lg.appendChild(el("span", { html: `<span style="color:${colors[st.sector]}">━</span> ${U.esc(st.sector)} <span class="num">${U.fmtPct(st.avg)}</span>` })));
      body.appendChild(lg);
      // sector-average change bars (zero-centered, scale ±1%)
      const bars = el("div", { style: "padding:2px 8px 4px;flex:0 0 auto" });
      sets.forEach(st => {
        const row = el("div", { class: "sbar-row" });
        row.appendChild(el("span", { class: "sbar-k", text: st.sector }));
        const track = el("div", { class: "sbar-track", role: "img", "aria-label": st.sector + " average change bar " + U.fmtPct(st.avg) });
        track.appendChild(el("div", { class: "sbar-zero" }));
        const pct = U.clamp(st.avg / 1, -1, 1) * 50; // ±1% → ±50%
        const fill = el("div", { class: "sbar-fill " + (st.avg >= 0 ? "upb" : "dnb") });
        fill.style.left = (pct >= 0 ? 50 : 50 + pct) + "%";
        fill.style.width = Math.abs(pct) + "%";
        track.appendChild(fill);
        row.appendChild(track);
        row.appendChild(el("span", { class: "num " + U.cls(st.avg), style: "width:58px;text-align:right", text: U.fmtPct(st.avg) }));
        bars.appendChild(row);
      });
      body.appendChild(bars);
      const tbl = el("table", { class: "tbl", style: "margin-top:2px" });
      tbl.innerHTML = "<thead><tr><th>SECTOR</th><th>AVG CHG</th><th>n</th><th>WEIGHTING</th><th>AS-OF</th></tr></thead>";
      const tb = el("tbody");
      sets.forEach(st => {
        const tr = el("tr");
        tr.innerHTML = `<td class="org" style="font-weight:800">${U.esc(st.sector)}</td>` +
          `<td class="num ${U.cls(st.avg)}">${U.arrow(st.avg)} ${U.fmtPct(st.avg)}</td>` +
          `<td class="num">${st.n}</td><td class="dim">${U.esc(st.weighting)}</td>` +
          `<td class="faint">${U.esc(st.asof.slice(11, 16))} ET</td>`;
        tb.appendChild(tr);
      });
      tbl.appendChild(tb);
      body.appendChild(tbl);
      body.appendChild(el("div", {
        class: "faint", style: "font-size:9px;padding:3px 8px",
        text: "single-region (US-listed) demo universe — no cross-timezone synchronicity implied. Closed markets in other widgets show state + last update."
      }));
    }
  };

  /* ---------- E. NEWS WIRE ---------- */
  const NEWS_CATS = ["AI", "TECH", "ENERGY", "FINANCE", "MACRO", "METALS"];
  W.news = {
    num: "05", title: "NEWS WIRE", min: [3, 5],
    render(body) {
      const p = G.state.prefs;
      const bar = el("div", { class: "toolbar" });
      NEWS_CATS.forEach(c => {
        const on = p.newsCats.indexOf(c) >= 0;
        bar.appendChild(el("button", {
          class: "chip" + (on ? " demo" : ""), text: c, "aria-pressed": on,
          style: on ? "border-color:var(--org);color:var(--org)" : "",
          onclick: () => {
            const i = p.newsCats.indexOf(c);
            if (i >= 0) p.newsCats.splice(i, 1); else p.newsCats.push(c);
            G.app.savePrefs(); G.app.rerender("news");
          }
        }));
      });
      bar.appendChild(el("span", { class: "spacer" }));
      bar.appendChild(el("button", {
        class: "chip", text: p.newsPaused ? "▶ RESUME" : "⏸ PAUSE", "aria-pressed": p.newsPaused,
        title: "Pause/resume auto-update. DEMO wire is static; control applies to LIVE feeds.",
        onclick: () => { p.newsPaused = !p.newsPaused; G.app.savePrefs(); G.app.rerender("news"); }
      }));
      const q = el("input", {
        class: "search", placeholder: "> grep", value: p.newsQ || "", "aria-label": "search headlines",
        style: "width:90px",
        oninput: U.debounce(e => { p.newsQ = e.target.value.trim(); G.app.savePrefs(); G.app.rerender("news"); }, 200)
      });
      bar.appendChild(q);
      body.appendChild(bar);

      const demoStrip = el("div", { style: "padding:2px 8px;font-size:9px;border-bottom:1px solid var(--line)" });
      demoStrip.appendChild(el("span", { class: "chip demo", text: "DEMO WIRE — ALL HEADLINES ARE ILLUSTRATIVE FIXTURES, NOT REAL NEWS" }));
      body.appendChild(demoStrip);

      const read = G.state.readNews;
      let list = G.datasets.news.slice().sort((a, b) => b.time.localeCompare(a.time)); // consistent comparator, 0 on ties
      if (p.newsCats.length) list = list.filter(n2 => p.newsCats.indexOf(n2.cat) >= 0);
      if (p.newsQ) { const qq = p.newsQ.toUpperCase(); list = list.filter(n2 => (n2.headline + n2.tickers.join(" ")).toUpperCase().indexOf(qq) >= 0); }
      const unread = list.filter(n2 => !read[n2.id]).length;
      body.appendChild(el("div", { class: "faint", style: "font-size:9px;padding:2px 8px", text: `> ${list.length} items · ${unread} unread · reverse-chronological · click opens summary/tickers/linked move` }));
      const wrap = el("div", { role: "feed", "aria-label": "news wire" });
      list.forEach(item => {
        const row = el("div", { class: "news-item" + (read[item.id] ? "" : " unread"), tabindex: "0", role: "article", "aria-label": item.headline });
        row.appendChild(el("span", { class: "nl-time num", text: item.time.slice(11, 19) }));
        row.appendChild(el("span", { class: "nl-cat cat-" + item.cat, text: "[" + item.cat + "]" }));
        const h = el("div", { class: "nl-head" });
        h.appendChild(el("span", { text: item.headline }));
        h.appendChild(document.createTextNode(" "));
        h.appendChild(el("span", { class: "nl-src", text: "— " + item.source }));
        row.appendChild(h);
        const open = () => { read[item.id] = 1; row.classList.remove("unread"); G.inspector.open("news", item); };
        row.addEventListener("click", open);
        row.addEventListener("keydown", e => { if (e.key === "Enter") open(); });
        wrap.appendChild(row);
      });
      if (!list.length) wrap.appendChild(el("div", { class: "pad dim", text: "> no wire items match filter" }));
      body.appendChild(wrap);
    }
  };

  /* ---------- F. AAPL 60-SESSION ---------- */
  W.aapl = {
    num: "06", title: "AAPL · 60 TRADING SESSIONS", min: [5, 5],
    render(body) {
      const s = G.datasets.aapl60;
      const last = s[s.length - 1], prev = s[s.length - 2];
      const chg = +(last.c - prev.c).toFixed(2), chgPct = +(chg / prev.c * 100).toFixed(2);
      const vol = s.reduce((a, b) => a + b.v, 0);
      const hi = el("div", { class: "toolbar", style: "gap:12px" });
      hi.innerHTML =
        `<span class="org" style="font-weight:800">AAPL</span>` +
        `<span class="num" style="font-weight:800;font-size:14px">${U.fmtNum(last.c, 2)}</span>` +
        `<span class="num ${U.cls(chg)}">${U.arrow(chg)} ${U.fmtChg(chg, 2)} (${U.fmtPct(chgPct)})</span>` +
        `<span class="dim">O <b class="num">${U.fmtNum(last.o, 2)}</b></span>` +
        `<span class="dim">PC <b class="num">${U.fmtNum(prev.c, 2)}</b></span>` +
        `<span class="dim">H <b class="num">${U.fmtNum(last.h, 2)}</b></span>` +
        `<span class="dim">L <b class="num">${U.fmtNum(last.l, 2)}</b></span>` +
        `<span class="dim">VOL <b class="num">${U.fmtVol(last.v)}</b></span>` +
        `<span class="dim">52W <b class="num">${U.fmtNum(G.GMT_FIXTURES.meta.aapl52w.low, 2)}–${U.fmtNum(G.GMT_FIXTURES.meta.aapl52w.high, 2)}</b></span>` +
        `<span class="chip demo">DEMO DATA</span>`;
      body.appendChild(hi);
      const box = el("div", { class: "chart-box", "aria-label": "AAPL 60 session chart; use left and right arrow keys to move crosshair" });
      body.appendChild(box);
      requestAnimationFrame(() => {
        G.charts.lineVolume(box, {
          series: s, dp: 2, color: "#00C176",
          aria: "AAPL price line with amber volume bars, 60 trading sessions",
          onPick: (i, p) => p && G.inspector.open("session", { sym: "AAPL", bar: p, index: i, total: s.length })
        });
      });
      body.appendChild(el("div", {
        class: "faint", style: "font-size:9px;padding:2px 8px;flex:0 0 auto",
        html: `> ${s.length} valid weekday sessions ${U.esc(s[0].d)} → ${U.esc(s[s.length - 1].d)} · no weekend/holiday filling (holiday calendar not applied)` +
          ` · split/adjustment: DEMO unadjusted fixture · Σvol ${U.fmtVol(vol)} · ←/→ move crosshair, Enter pins Inspector`
      }));
    }
  };

  /* ---------- G. PRECIOUS METALS ---------- */
  W.metals = {
    num: "07", title: "PRECIOUS METALS MONITOR", min: [5, 5],
    render(body) {
      const p = G.state.prefs;
      const metals = G.datasets.metals;
      const get = sym => metals.find(m => m.sym === sym);
      const cells = el("div", { class: "met-cells" });
      metals.forEach(m => {
        const c = el("div", { class: "met-cell" + (p.metalSel === m.sym ? " sel" : ""), tabindex: "0", role: "button", "aria-label": m.name });
        c.appendChild(el("div", { class: "row between" }, [
          el("span", { class: "k", text: m.sym }), el("span", { class: "faint", style: "font-size:8px", text: m.unit })
        ]));
        c.appendChild(el("div", { class: "v num", text: U.fmtNum(m.last, m.sym === "XAG" ? 3 : 2) }));
        c.appendChild(el("div", { class: "num " + U.cls(m.chgPct), style: "font-size:10px", text: `${U.arrow(m.chgPct)} ${U.fmtChg(m.chg, m.sym === "XAG" ? 3 : 2)} (${U.fmtPct(m.chgPct)})` }));
        const spark = el("div");
        c.appendChild(spark);
        requestAnimationFrame(() => G.charts.sparkline(spark, m.series.map(x => x.c), { color: U.cls(m.chgPct) === "dn" ? "#FF4D4F" : "#00C176" }));
        c.appendChild(el("div", { class: "faint", style: "font-size:8px", text: "as-of " + m.asof.slice(11, 16) + " ET · spot" }));
        const open = () => { p.metalSel = m.sym; G.app.savePrefs(); G.app.rerender("metals"); G.inspector.open("metal", m); };
        c.addEventListener("click", open);
        c.addEventListener("keydown", e => { if (e.key === "Enter") open(); });
        cells.appendChild(c);
      });
      body.appendChild(cells);

      // ratios & ranges with formulas
      const xau = get("XAU"), xag = get("XAG"), xpt = get("XPT"), xpd = get("XPD");
      const gsr = xau.last / xag.last, spread = xau.last - xpt.last;
      const rrow = el("div", { class: "ratio-row" });
      rrow.innerHTML =
        `<span>GOLD/SILVER RATIO <b class="num">${gsr.toFixed(2)}</b> = XAU/XAG = ${U.fmtNum(xau.last, 2)}/${U.fmtNum(xag.last, 3)} (unitless)</span>` +
        `<span>AU–PT SPREAD <b class="num">${U.fmtChg(spread, 2)}</b> = XAU−XPT (USD/t oz)</span>` +
        metals.map(m => {
          const lo = Math.min.apply(null, m.series.map(x => x.l)), hi2 = Math.max.apply(null, m.series.map(x => x.h));
          return `<span>${m.sym} 60D <b class="num">${U.fmtNum(lo, 2)}–${U.fmtNum(hi2, 2)}</b></span>`;
        }).join("");
      body.appendChild(rrow);
      body.appendChild(el("div", {
        class: "faint", style: "font-size:9px;padding:2px 8px",
        text: "definitions: spot, USD per troy ounce, single demo desk — homogeneous across all four metals, so ratios/spreads are compatible. If sources were mixed (spot vs futures) derivatives would be disabled."
      }));

      const sel = get(p.metalSel) || xau;
      body.appendChild(el("div", { class: "pad", style: "font-size:10px;padding:2px 8px" }, [
        el("b", { class: "org", text: sel.sym + " · 60 sessions · " }), el("span", { class: "dim", text: sel.series[0].d + " → " + sel.series[sel.series.length - 1].d })
      ]));
      const box = el("div", { class: "chart-box", style: "flex:1", "aria-label": sel.sym + " 60 session chart" });
      body.appendChild(box);
      requestAnimationFrame(() => {
        G.charts.lineVolume(box, {
          series: sel.series.map(x => ({ d: x.d, c: x.c, h: x.h, l: x.l })),
          dp: sel.sym === "XAG" ? 3 : 2, color: "#FFB454",
          onPick: (i, pt) => pt && G.inspector.open("session", { sym: sel.sym, bar: pt, index: i, total: sel.series.length, unit: sel.unit })
        });
      });
    }
  };

  /* ---------- H. MARKET PULSE ---------- */
  const PULSE_TZS = [["America/New_York", "NEW YORK"], ["Europe/London", "LONDON"], ["Asia/Shanghai", "SHANGHAI"], ["Asia/Hong_Kong", "HONG KONG"], ["Asia/Tokyo", "TOKYO"], ["Etc/UTC", "UTC"]];
  W.pulse = {
    num: "08", title: "MARKET PULSE · GLOBAL SESSION CLOCK", min: [4, 5],
    render(body) {
      const p = G.state.prefs;
      const bar = el("div", { class: "toolbar" });
      bar.appendChild(el("span", { class: "faint", style: "font-size:9px", text: "DISPLAY TZ" }));
      const sel = el("select", { class: "search", "aria-label": "display timezone" });
      PULSE_TZS.forEach(([tz, lab]) => sel.appendChild(el("option", { value: tz, text: lab, selected: p.tz === tz ? "selected" : null })));
      sel.addEventListener("change", () => { p.tz = sel.value; G.app.savePrefs(); tick(); });
      bar.appendChild(sel);
      bar.appendChild(el("span", { class: "spacer" }));
      bar.appendChild(el("span", { class: "chip stale", text: "HOLIDAY STATUS UNVERIFIED" }));
      body.appendChild(bar);

      const clock = el("div", { class: "pad", style: "text-align:center;border-bottom:1px solid var(--line)" });
      const big = el("div", { class: "bigclock", "aria-live": "off" });
      const sub = el("div", { class: "dim", style: "font-size:10px" });
      clock.appendChild(big); clock.appendChild(sub);
      body.appendChild(clock);

      const tbl = el("table", { class: "tbl" });
      tbl.innerHTML = "<thead><tr><th>MARKET</th><th>LOCAL</th><th>SESSION</th><th>STATE</th><th>NEXT</th><th>IN</th></tr></thead>";
      const tb = el("tbody"); tbl.appendChild(tb);
      body.appendChild(tbl);
      const map = el("div", { class: "pulse-map", role: "img", "aria-label": "24 hour session map with current time line" });
      body.appendChild(map);
      body.appendChild(el("div", { class: "faint", style: "font-size:8px;padding:2px 8px", text: "bands = regular sessions converted to display tz · amber band = lunch · orange line = NOW · weekends CLOSED · no holiday calendar bundled → holidays never inferred" }));

      const gen = (body.__pulseGen = (body.__pulseGen || 0) + 1);
      function tick() {
        if (body.__pulseGen !== gen || !document.body.contains(body)) return;
        const now = new Date();
        const tz = G.state.prefs.tz;
        big.textContent = U.fmtClock(now, tz, true);
        sub.textContent = U.fmtDate(now, tz) + " · " + tz + " · " + U.tzOffsetLabel(now, tz);
        tb.innerHTML = "";
        G.sessions.MARKETS.forEach(m => {
          const st = G.sessions.stateAt(m, now);
          const tr = el("tr", { "data-click": "1", tabindex: "0" });
          tr.innerHTML =
            `<td class="org" style="font-weight:700">${U.esc(m.id)}</td>` +
            `<td class="num">${U.fmtClock(now, m.tz, false)}</td>` +
            `<td class="dim num">${U.esc(G.sessions.sessionHoursLabel(m))}</td>` +
            `<td class="state-${st.state}">${st.state}${st.state === "CLOSED" && (st.date.wd === 0 || st.date.wd === 6) ? "/WKND" : ""}</td>` +
            `<td class="dim">${st.nextVerb} ${st.nextState ? "→ " + st.nextState : ""}</td>` +
            `<td class="num cy">${G.sessions.fmtCountdown(st.countdownMs)}</td>`;
          const open = () => G.inspector.open("market", { mkt: m, st: st, now: now.toISOString() });
          tr.addEventListener("click", open);
          tr.addEventListener("keydown", e => { if (e.key === "Enter") open(); });
          tb.appendChild(tr);
        });
        // 24h map
        map.innerHTML = "";
        const w = G.sessions.partsInTz(now, tz);
        const dayStart = G.sessions.zonedToUtc(w.y, w.mo, w.d, 0, tz);
        const dayEnd = G.sessions.zonedToUtc(w.y, w.mo, w.d, 24 * 60 - 1, tz) + 60000; // DST-safe: 23h/25h days
        G.sessions.MARKETS.forEach((m, i) => {
          const bands = G.sessions.bandsForDisplay(m, now, tz);
          bands.forEach(b => {
            const l = (b.a - dayStart) / (dayEnd - dayStart) * 100;
            const wd = (b.b - b.a) / (dayEnd - dayStart) * 100;
            map.appendChild(el("div", { class: "pm-band" + (b.lunch ? " lunch" : ""), style: `left:${l.toFixed(2)}%;width:${Math.max(0.4, wd).toFixed(2)}%;top:${6 + i * 15}px` }));
          });
          map.appendChild(el("div", { class: "pm-label", style: `left:2px;top:${6 + i * 15 + 1}px`, text: m.id }));
        });
        const nowX = (now.getTime() - dayStart) / (dayEnd - dayStart) * 100;
        map.appendChild(el("div", { class: "pm-now", style: `left:${U.clamp(nowX, 0, 100).toFixed(2)}%` }));
        for (let h = 0; h <= 24; h += 6) {
          map.appendChild(el("div", { class: "pm-label", style: `left:${(h / 24 * 100).toFixed(1)}%;bottom:1px`, text: String(h).padStart(2, "0") }));
        }
        setTimeout(tick, 1000);
      }
      tick();
    }
  };

  /* ---------- I. GLOBAL INDEX MAP / LIST ---------- */
  W.indexmap = {
    num: "09", title: "GLOBAL INDEX MAP · BY REGION", min: [4, 4],
    render(body) {
      const groups = { "AMERICAS": [], "EUROPE": [], "APAC": [], "METALS/FX/ENERGY": [] };
      G.datasets.tape.forEach(r => {
        const gk = groups[r.region] ? r.region : "METALS/FX/ENERGY"; // unknown region → fallback group, never an "undefined" key
        groups[gk].push(r);
      });
      const now = new Date();
      Object.keys(groups).forEach(gk => {
        if (!groups[gk].length) return;
        body.appendChild(el("div", { class: "pad", style: "padding:3px 8px 1px;font-size:9px;color:var(--org);font-weight:800;letter-spacing:1px", text: "├─ " + gk }));
        const tbl = el("table", { class: "tbl" });
        const tb = el("tbody");
        groups[gk].forEach(r => {
          const tr = el("tr", { "data-click": "1", tabindex: "0" });
          tr.innerHTML =
            `<td class="org" style="font-weight:800">${U.esc(r.sym)}</td>` +
            `<td class="dim">${U.esc(r.src)}</td>` +
            `<td class="num" style="font-weight:700">${U.fmtNum(r.last, 2)}</td>` +
            `<td class="num ${U.cls(r.chgPct)}">${U.arrow(r.chgPct)} ${U.fmtPct(r.chgPct)}</td>` +
            `<td class="state-${U.esc(r.state)}">${U.esc(r.state)}</td>` +
            `<td class="num dim">${U.fmtClock(now, r.tz, false)}</td>` +
            `<td class="faint">${U.esc(r.asof.slice(11, 16))}ET</td>`;
          const open = () => { G.app.setFocus(r.sym); G.inspector.open("instrument", r); };
          tr.addEventListener("click", open);
          tr.addEventListener("keydown", e => { if (e.key === "Enter") open(); });
          tb.appendChild(tr);
        });
        tbl.appendChild(tb);
        body.appendChild(tbl);
      });
      body.appendChild(el("div", { class: "faint", style: "font-size:9px;padding:3px 8px", text: "navigational region partition — no area/distortion encoding · local time = live clock in venue tz · as-of = demo quote time" }));
    }
  };
})(window.GMT);
