/* GMT widgets A–I. Registry + renderers. Chrome (title bar/controls) lives in layout.js. */
window.GMT = window.GMT || {};
(function (G) {
  "use strict";
  const U = G.util, el = U.el;

  /* sector heat color: green up / red down, intensity = |chgPct| mapped 0..3% */
  function heatColor(chgPct) {
    const a = U.clamp(Math.abs(chgPct) / 3, 0.06, 1);
    if (chgPct > 0) return `rgba(0,193,118,${(0.16 + 0.6 * a).toFixed(3)})`;
    if (chgPct < 0) return `rgba(255,77,79,${(0.16 + 0.6 * a).toFixed(3)})`;
    return "rgba(138,138,138,0.14)";
  }

  function filteredStocks() {
    const p = G.state.prefs;
    let list = G.datasets.stocks.slice();
    if (p.heatFilter !== "ALL") list = list.filter(s => s.sector === p.heatFilter);
    if (p.heatQuery) {
      const q = p.heatQuery.toUpperCase();
      list = list.filter(s => s.t.indexOf(q) >= 0 || s.name.toUpperCase().indexOf(q) >= 0);
    }
    return list;
  }

  function areaValue(s) {
    const mode = G.state.prefs.heatArea;
    if (mode === "MKTCAP") return s.mktCap;
    if (mode === "TURNOVER") return s.last * s.volume;
    return Math.max(Math.abs(s.chgPct), 0.05); // |CHG%| default; floor keeps flat names visible
  }
  const AREA_LABEL = { "CHG": "AREA = |CHG%| (absolute % move)", "MKTCAP": "AREA = MARKET CAP (USD)", "TURNOVER": "AREA = TURNOVER (last × volume, USD)" };

  const WIDGETS = {
    /* ---------- A. GLOBAL TICKER ---------- */
    ticker: {
      num: "01", title: "GLOBAL TICKER", min: [4, 4],
      render(body) {
        const rows = G.datasets.tape;
        const tbl = el("table", { class: "tbl", role: "grid", "aria-label": "global ticker quotes" });
        tbl.innerHTML = "<thead><tr><th>SYM</th><th>NAME</th><th>LAST</th><th>CHG</th><th>CHG%</th><th>STATE</th><th>SRC</th><th>AS-OF</th></tr></thead>";
        const tb = el("tbody");
        rows.forEach(r => {
          const tr = el("tr", { "data-click": "1", tabindex: "0", role: "row" });
          const dp = r.last >= 1000 ? 2 : 2;
          tr.innerHTML =
            `<td class="org" style="font-weight:800">${U.esc(r.sym)}</td><td class="dim">${U.esc(r.name)}</td>` +
            `<td class="num" style="font-weight:700">${U.fmtNum(r.last, dp)}</td>` +
            `<td class="num ${U.cls(r.chg)}">${U.arrow(r.chg)} ${U.fmtChg(r.chg, dp)}</td>` +
            `<td class="num ${U.cls(r.chgPct)}">${U.fmtPct(r.chgPct)}</td>` +
            `<td class="state-${U.esc(r.state)}">${U.esc(r.state)}</td>` +
            `<td class="faint">${U.esc(r.src)}</td><td class="faint">${U.esc(r.asof.slice(11, 16))} ET</td>`;
          const open = () => { G.app.setFocus(r.sym); };
          tr.addEventListener("click", open);
          tr.addEventListener("keydown", e => { if (e.key === "Enter") open(); });
          tb.appendChild(tr);
        });
        tbl.appendChild(tb);
        body.appendChild(tbl);
        body.appendChild(el("div", { class: "pad faint", text: "click row → focus asset & update chart · fixed-width tabular columns prevent digit jitter", style: "font-size:9px;padding:3px 8px" }));
      }
    },

    /* ---------- B. STOCK TRACKING heat matrix (hero) ---------- */
    heat: {
      num: "02", title: "STOCK TRACKING · AI/TECH — ENERGY — FINANCIALS", min: [5, 6],
      render(body) {
        const p = G.state.prefs;
        const bar = el("div", { class: "toolbar", role: "toolbar", "aria-label": "heatmap filters" });
        const segF = el("div", { class: "seg", role: "group", "aria-label": "sector filter" });
        ["ALL", "AI-TECH", "ENERGY", "FINANCIALS"].forEach(f => {
          segF.appendChild(el("button", {
            class: p.heatFilter === f ? "on" : "", "aria-pressed": p.heatFilter === f, text: f,
            onclick: () => { p.heatFilter = f; G.app.savePrefs(); G.app.rerender("heat"); G.app.rerender("breadth"); }
          }));
        });
        const segA = el("div", { class: "seg", role: "group", "aria-label": "area mapping" });
        [["CHG", "|CHG%|"], ["MKTCAP", "MKT CAP"], ["TURNOVER", "TURNOVER"]].forEach(([k, lab]) => {
          segA.appendChild(el("button", {
            class: p.heatArea === k ? "on" : "", "aria-pressed": p.heatArea === k, text: lab,
            onclick: () => { p.heatArea = k; G.app.savePrefs(); G.app.rerender("heat"); }
          }));
        });
        const q = el("input", {
          class: "search", placeholder: "> search ticker", value: p.heatQuery || "",
          "aria-label": "search ticker", style: "width:130px",
          oninput: U.debounce(e => { p.heatQuery = e.target.value.trim(); G.app.savePrefs(); G.app.rerender("heat"); }, 200)
        });
        bar.appendChild(segF); bar.appendChild(segA); bar.appendChild(q);
        bar.appendChild(el("span", { class: "spacer" }));
        bar.appendChild(el("span", { class: "chip demo", text: "DEMO DATA" }));
        body.appendChild(bar);

        const legend = el("div", { class: "legend", style: "padding:3px 8px;border-bottom:1px solid var(--line)" });
        legend.innerHTML =
          `<span>${U.esc(AREA_LABEL[p.heatArea])}</span>` +
          `<span><span class="sw" style="background:rgba(0,193,118,.76)"></span>▲ up · intensity = |chg%| / 3%</span>` +
          `<span><span class="sw" style="background:rgba(255,77,79,.76)"></span>▼ down</span>` +
          `<span><span class="sw" style="background:rgba(138,138,138,.14)"></span>• flat</span>`;
        body.appendChild(legend);

        const stage = el("div", { id: "heat-stage", role: "group", "aria-label": "sector heatmap" });
        body.appendChild(stage);
        requestAnimationFrame(() => drawHeat(stage));
      }
    },

    /* ---------- C. MARKET BREADTH ---------- */
    breadth: {
      num: "03", title: "MARKET BREADTH · FILTERED UNIVERSE", min: [3, 4],
      render(body) {
        const list = filteredStocks();
        const n = list.length;
        const adv = list.filter(s => s.chgPct > 0).length;
        const dec = list.filter(s => s.chgPct < 0).length;
        const unch = n - adv - dec;
        const gainer = list.slice().sort((a, b) => b.chgPct - a.chgPct)[0];
        const loser = list.slice().sort((a, b) => a.chgPct - b.chgPct)[0];
        const bySect = {};
        list.forEach(s => { bySect[s.sector] = (bySect[s.sector] || 0) + s.last * s.volume; });
        const actSect = Object.keys(bySect).sort((a, b) => bySect[b] - bySect[a])[0] || "—";
        const hl = G.state.prefs.breadthHL;

        const grid = el("div", { class: "breadth-grid" });
        function cell(k, v, s, act, key) {
          const c = el("div", { class: "b-cell", tabindex: "0", role: "button", "aria-label": k + " " + v });
          c.appendChild(el("div", { class: "k", text: k }));
          c.appendChild(el("div", { class: "v", text: v }));
          c.appendChild(el("div", { class: "s", text: s }));
          const go = () => act();
          c.addEventListener("click", go);
          c.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
          if (key && hl === key) c.style.borderColor = "var(--org)";
          grid.appendChild(c);
        }
        const setHL = key => {
          G.state.prefs.breadthHL = G.state.prefs.breadthHL === key ? null : key;
          G.app.savePrefs(); G.app.rerender("breadth"); G.app.rerender("heat");
        };
        cell("ADVANCERS", String(adv), "chg% > 0", () => setHL("ADV"), "ADV");
        cell("DECLINERS", String(dec), "chg% < 0", () => setHL("DEC"), "DEC");
        cell("UNCHANGED", String(unch), "chg% = 0", () => setHL("UNCH"), "UNCH");
        cell("A/D RATIO", dec ? (adv / dec).toFixed(2) : "∞", "adv / dec", () => G.inspector.open("breadth", { adv, dec, unch, n }));
        cell("TOP GAINER", gainer ? gainer.t : "—", gainer ? U.fmtPct(gainer.chgPct) : "", () => gainer && G.inspector.open("stock", gainer));
        cell("TOP LOSER", loser ? loser.t : "—", loser ? U.fmtPct(loser.chgPct) : "", () => loser && G.inspector.open("stock", loser));
        body.appendChild(grid);

        const barWrap = el("div");
        const bar = el("div", { class: "adbar", role: "img", "aria-label": `advance decline bar: ${adv} up, ${dec} down, ${unch} unchanged` });
        if (n) {
          bar.appendChild(el("div", { style: `width:${(adv / n * 100).toFixed(1)}%;background:var(--up)` }));
          bar.appendChild(el("div", { style: `width:${(unch / n * 100).toFixed(1)}%;background:var(--flat)` }));
          bar.appendChild(el("div", { style: `width:${(dec / n * 100).toFixed(1)}%;background:var(--dn)` }));
        }
        barWrap.appendChild(bar);
        body.appendChild(barWrap);
        body.appendChild(el("div", {
          class: "pad faint", style: "font-size:9px;padding:2px 8px",
          html: `SAMPLE n=${n} · filter=${U.esc(G.state.prefs.heatFilter)}${G.state.prefs.heatQuery ? " · q=" + U.esc(G.state.prefs.heatQuery) : ""}` +
            `<br>most active sector: <b class="org">${U.esc(actSect)}</b> (by Σ last×volume of sample)` +
            `<br>universe = current heatmap filter, not whole-market breadth`
        }));
      }
    }
  };

  /* heat drawing (needs live stage size) */
  function drawHeat(stage) {
    stage.innerHTML = "";
    const W = stage.clientWidth || 600, H = stage.clientHeight || 380;
    const list = filteredStocks();
    if (!list.length) {
      stage.appendChild(el("div", { class: "pad dim", text: "> no matches — clear search/filter" }));
      return;
    }
    const groups = {};
    list.forEach(s => { (groups[s.sector] = groups[s.sector] || []).push(s); });
    const gKeys = Object.keys(groups).sort();
    const gItems = gKeys.map(k => ({ key: k, value: groups[k].reduce((a, s) => a + areaValue(s), 0) }));
    const gRects = G.charts.squarify(gItems, { x: 0, y: 0, w: W, h: H });
    const hl = G.state.prefs.breadthHL;
    gRects.forEach(gr => {
      const gEl = el("div", { class: "hm-group", style: `left:${gr.x}px;top:${gr.y}px;width:${Math.max(0, gr.w - 2)}px;height:${Math.max(0, gr.h - 2)}px` });
      gEl.appendChild(el("div", { class: "hm-glabel", text: `${gr.key} · n=${groups[gr.key].length}` }));
      const inner = { x: 1, y: 17, w: Math.max(0, gr.w - 4), h: Math.max(0, gr.h - 20) };
      const items = groups[gr.key].map(s => ({ key: s.t, value: areaValue(s), payload: s }));
      const tiles = G.charts.squarify(items, { x: 0, y: 0, w: inner.w, h: inner.h });
      tiles.forEach(t => {
        const s = t.payload;
        const cls = U.cls(s.chgPct);
        const tile = el("div", {
          class: "hm-tile", tabindex: "0", role: "button",
          "aria-label": `${s.t} ${s.name} last ${s.last} change ${U.fmtPct(s.chgPct)}`,
          style: `left:${(inner.x + t.x).toFixed(1)}px;top:${(inner.y + t.y).toFixed(1)}px;width:${Math.max(0, t.w - 1).toFixed(1)}px;height:${Math.max(0, t.h - 1).toFixed(1)}px;background:${heatColor(s.chgPct)}`
        });
        const w = t.w, h = t.h;
        let inner_html = `<div class="t1 ${cls}">${U.esc(s.t)}</div>`;
        if (w > 66 && h > 40) inner_html += `<div class="t2">${U.esc(s.name)}</div>`;
        if (h > 52) inner_html += `<div class="t3 num">${U.fmtNum(s.last, 2)}</div>`;
        if (h > 34) inner_html += `<div class="t4 num ${cls}">${U.arrow(s.chgPct)} ${U.fmtPct(s.chgPct)}</div>`;
        tile.innerHTML = inner_html;
        if (hl) {
          const match = (hl === "ADV" && s.chgPct > 0) || (hl === "DEC" && s.chgPct < 0) || (hl === "UNCH" && s.chgPct === 0);
          if (!match) tile.classList.add("dimmed");
        }
        tile.addEventListener("pointerenter", e => G.app.hoverPreview("stock", s, tile));
        tile.addEventListener("pointerleave", () => G.app.hoverPreview(null));
        tile.addEventListener("click", () => { G.app.hoverPreview(null); G.app.setFocus(s.t); G.inspector.open("stock", s); });
        tile.addEventListener("keydown", e => { if (e.key === "Enter") { G.app.setFocus(s.t); G.inspector.open("stock", s); } });
        gEl.appendChild(tile);
      });
      stage.appendChild(gEl);
    });
  }

  G.widgets = { WIDGETS, drawHeat, filteredStocks, heatColor, areaValue, AREA_LABEL };
})(window.GMT);
