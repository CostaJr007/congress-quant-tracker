/* GMT charts: dependency-free SVG renderers (line+volume, sparkline, squarified treemap layout). */
window.GMT = window.GMT || {};
(function (G) {
  "use strict";
  const U = G.util;
  const NS = "http://www.w3.org/2000/svg";
  function svgEl(tag, attrs) {
    const n = document.createElementNS(NS, tag);
    if (attrs) for (const k in attrs) n.setAttribute(k, attrs[k]);
    return n;
  }

  function niceTicks(min, max, count) {
    if (!(isFinite(min) && isFinite(max)) || min === max) { min = (min || 0) - 1; max = (max || 1) + 1; }
    const span = max - min, raw = span / Math.max(1, count);
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const norm = raw / mag;
    const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
    const t0 = Math.ceil(min / step) * step, out = [];
    for (let v = t0; v <= max + 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }

  /* ---------- line + volume chart with crosshair & arrow-key nav ----------
     series: [{d, o,h,l,c,v}] — no weekend/holiday filling: points are sessions only. */
  function lineVolume(container, opts) {
    container.innerHTML = "";
    const W = Math.max(220, container.clientWidth || 480);
    const H = Math.max(160, container.clientHeight || 260);
    const padL = 6, padR = 52, padT = 8, padB = 16;
    const s = opts.series;
    const n = s.length;
    const hasVol = s.some(p => p.v);
    const volH = hasVol ? Math.round((H - padT - padB) * 0.22) : 0;
    const priceH = H - padT - padB - volH - (hasVol ? 4 : 0);
    const svg = svgEl("svg", { width: "100%", height: "100%", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.aria || "price chart" });
    container.appendChild(svg);

    let lo = Infinity, hi = -Infinity, vMax = 0;
    s.forEach(p => { lo = Math.min(lo, p.l != null ? p.l : p.c); hi = Math.max(hi, p.h != null ? p.h : p.c); vMax = Math.max(vMax, p.v || 0); });
    const padY = (hi - lo) * 0.05 || 1; lo -= padY; hi += padY;
    const x = i => padL + (n === 1 ? 0 : i * (W - padL - padR) / (n - 1));
    const y = v => padT + (hi - v) / (hi - lo) * priceH;
    const yv = v => padT + priceH + 4 + volH - (vMax ? (v / vMax) * volH : 0);

    // grid + price axis (right)
    niceTicks(lo, hi, 4).forEach(t => {
      svg.appendChild(svgEl("line", { x1: padL, x2: W - padR, y1: y(t), y2: y(t), stroke: "#292929", "stroke-width": 1 }));
      const tx = svgEl("text", { x: W - padR + 4, y: y(t) + 3, fill: "#8A8A8A", "font-size": 9 });
      tx.textContent = U.fmtNum(t, opts.dp != null ? opts.dp : U.dpFor(t));
      svg.appendChild(tx);
    });
    // x date labels (~6)
    const stepL = Math.max(1, Math.floor(n / 6));
    for (let i = 0; i < n; i += stepL) {
      const tx = svgEl("text", { x: U.clamp(x(i) - 14, 0, W - 60), y: H - 4, fill: "#5C5C5C", "font-size": 8 });
      tx.textContent = s[i].d.slice(5);
      svg.appendChild(tx);
    }
    // volume bars (amber)
    const bw = Math.max(1, (W - padL - padR) / n * 0.62);
    s.forEach((p, i) => {
      if (!p.v) return;
      svg.appendChild(svgEl("rect", {
        x: x(i) - bw / 2, y: yv(p.v), width: bw, height: Math.max(1, padT + priceH + 4 + volH - yv(p.v)),
        fill: "rgba(242,140,0,.55)"
      }));
    });
    // volume axis label
    if (hasVol) {
      const vt = svgEl("text", { x: padL + 2, y: padT + priceH + 12, fill: "#5C5C5C", "font-size": 8 });
      vt.textContent = "VOL " + U.fmtVol(vMax);
      svg.appendChild(vt);
    }

    // price fill (minimal) + line (terminal green)
    const pts = s.map((p, i) => x(i).toFixed(1) + "," + y(p.c).toFixed(1));
    const area = `M${padL},${padT + priceH} L` + pts.join(" L") + ` L${W - padR},${padT + priceH} Z`;
    svg.appendChild(svgEl("path", { d: area, fill: "rgba(0,193,118,.06)", stroke: "none" }));
    svg.appendChild(svgEl("path", { d: "M" + pts.join(" L"), fill: "none", stroke: opts.color || "#00C176", "stroke-width": 1.2 }));

    // last price marker
    const lastC = s[n - 1].c;
    svg.appendChild(svgEl("line", { x1: padL, x2: W - padR, y1: y(lastC), y2: y(lastC), stroke: "#3A3A3A", "stroke-dasharray": "3 3" }));
    const lp = svgEl("text", { x: W - padR + 4, y: y(lastC) - 3, fill: "#F28C00", "font-size": 9, "font-weight": 700 });
    lp.textContent = U.fmtNum(lastC, opts.dp != null ? opts.dp : U.dpFor(lastC));
    svg.appendChild(lp);

    // optional trade-date vertical marker (congress disclosure link)
    if (opts.markDate) {
      let mi = -1;
      for (let i = 0; i < n; i++) {
        if (s[i].d === opts.markDate) { mi = i; break; }
        if (s[i].d > opts.markDate) { mi = i; break; } // first session on/after trade
      }
      if (mi < 0) mi = 0;
      if (mi >= 0) {
        svg.appendChild(svgEl("line", {
          x1: x(mi), x2: x(mi), y1: padT, y2: padT + priceH + 4 + volH,
          stroke: "#F28C00", "stroke-width": 1, "stroke-dasharray": "2 2", opacity: "0.85"
        }));
        const mt = svgEl("text", { x: U.clamp(x(mi) - 18, padL, W - 80), y: padT + 10, fill: "#F28C00", "font-size": 8 });
        mt.textContent = "TRADE";
        svg.appendChild(mt);
      }
    }

    // crosshair
    const chg = svgEl("g", { visibility: "hidden" });
    const vline = svgEl("line", { y1: padT, y2: padT + priceH + 4 + volH, stroke: "#F28C00", "stroke-width": 1 });
    const dot = svgEl("circle", { r: 2.4, fill: "#F28C00" });
    chg.appendChild(vline); chg.appendChild(dot);
    svg.appendChild(chg);
    const info = U.el("div", { class: "xh-info", "aria-hidden": "true" });
    container.appendChild(info);

    let idx = n - 1;
    function show(i, pinned) {
      idx = U.clamp(i, 0, n - 1);
      const p = s[idx];
      chg.setAttribute("visibility", "visible");
      vline.setAttribute("x1", x(idx)); vline.setAttribute("x2", x(idx));
      dot.setAttribute("cx", x(idx)); dot.setAttribute("cy", y(p.c));
      const rows = [p.d];
      if (p.o != null) rows.push("O " + U.fmtNum(p.o, 2) + "  H " + U.fmtNum(p.h, 2) + "  L " + U.fmtNum(p.l, 2) + "  C " + U.fmtNum(p.c, 2));
      else rows.push("C " + U.fmtNum(p.c, opts.dp != null ? opts.dp : 2));
      if (p.v) rows.push("VOL " + U.fmtVol(p.v));
      info.textContent = rows.join("\n");
      if (opts.onCrosshair) opts.onCrosshair(idx, p);
    }
    function hide() { chg.setAttribute("visibility", "hidden"); info.textContent = ""; if (opts.onCrosshair) opts.onCrosshair(-1, null); }
    svg.addEventListener("pointermove", e => {
      const r = svg.getBoundingClientRect();
      const px = (e.clientX - r.left) * (W / r.width);
      show(Math.round((px - padL) / ((W - padL - padR) / Math.max(1, n - 1))));
    });
    svg.addEventListener("pointerleave", hide);
    container.tabIndex = 0;
    container.addEventListener("keydown", e => {
      if (e.key === "ArrowLeft") { show(idx - 1); e.preventDefault(); }
      else if (e.key === "ArrowRight") { show(idx + 1); e.preventDefault(); }
      else if (e.key === "Home") { show(0); e.preventDefault(); }
      else if (e.key === "End") { show(n - 1); e.preventDefault(); }
      else if (e.key === "Enter") { if (opts.onPick) opts.onPick(idx, s[idx]); e.preventDefault(); }
    });
    container.__chart = { show, hide, getIndex: () => idx };
    return svg;
  }

  /* ---------- candlestick + volume (from Kimi market-dashboard, SVG port)
     series: [{d, o,h,l,c,v}] daily sessions. Supports markDate + crosshair. */
  function candlestickVolume(container, opts) {
    container.innerHTML = "";
    const W = Math.max(220, container.clientWidth || 480);
    const H = Math.max(160, container.clientHeight || 260);
    const padL = 6, padR = 52, padT = 8, padB = 16;
    const s = opts.series || [];
    const n = s.length;
    if (n < 1) {
      container.appendChild(U.el("div", { class: "dim", text: "> no OHLC series" }));
      return null;
    }
    const hasVol = s.some(p => p.v);
    const volH = hasVol ? Math.round((H - padT - padB) * 0.18) : 0;
    const priceH = H - padT - padB - volH - (hasVol ? 4 : 0);
    const svg = svgEl("svg", {
      width: "100%", height: "100%", viewBox: `0 0 ${W} ${H}`,
      role: "img", "aria-label": opts.aria || "candlestick chart"
    });
    container.appendChild(svg);

    let lo = Infinity, hi = -Infinity, vMax = 0;
    s.forEach(p => {
      const L = p.l != null ? p.l : p.c;
      const Hgh = p.h != null ? p.h : p.c;
      lo = Math.min(lo, L); hi = Math.max(hi, Hgh);
      vMax = Math.max(vMax, p.v || 0);
    });
    const padY = (hi - lo) * 0.05 || 1; lo -= padY; hi += padY;
    const x = i => padL + (n === 1 ? 0 : i * (W - padL - padR) / (n - 1));
    const y = v => padT + (hi - v) / (hi - lo) * priceH;
    const yv = v => padT + priceH + 4 + volH - (vMax ? (v / vMax) * volH : 0);
    const cw = Math.max(1.5, (W - padL - padR) / n * 0.62);

    // grid
    niceTicks(lo, hi, 4).forEach(t => {
      svg.appendChild(svgEl("line", { x1: padL, x2: W - padR, y1: y(t), y2: y(t), stroke: "#292929", "stroke-width": 1 }));
      const tx = svgEl("text", { x: W - padR + 4, y: y(t) + 3, fill: "#8A8A8A", "font-size": 9 });
      tx.textContent = U.fmtNum(t, opts.dp != null ? opts.dp : U.dpFor(t));
      svg.appendChild(tx);
    });
    const stepL = Math.max(1, Math.floor(n / 6));
    for (let i = 0; i < n; i += stepL) {
      const tx = svgEl("text", { x: U.clamp(x(i) - 14, 0, W - 60), y: H - 4, fill: "#5C5C5C", "font-size": 8 });
      tx.textContent = s[i].d.slice(5);
      svg.appendChild(tx);
    }

    // volume bars
    s.forEach((p, i) => {
      if (!p.v) return;
      const up = (p.c != null && p.o != null) ? p.c >= p.o : true;
      svg.appendChild(svgEl("rect", {
        x: x(i) - cw / 2,
        y: yv(p.v),
        width: cw,
        height: Math.max(1, padT + priceH + 4 + volH - yv(p.v)),
        fill: up ? "rgba(242,140,0,.45)" : "rgba(242,140,0,.22)"
      }));
    });
    if (hasVol) {
      const vt = svgEl("text", { x: padL + 2, y: padT + priceH + 12, fill: "#5C5C5C", "font-size": 8 });
      vt.textContent = "VOL " + U.fmtVol(vMax);
      svg.appendChild(vt);
    }

    // candles: wick + body
    s.forEach((p, i) => {
      const o = p.o != null ? p.o : p.c;
      const c = p.c;
      const hh = p.h != null ? p.h : Math.max(o, c);
      const ll = p.l != null ? p.l : Math.min(o, c);
      const up = c >= o;
      const col = up ? "#00C176" : "#FF4D4F";
      const xi = x(i);
      // wick
      svg.appendChild(svgEl("line", {
        x1: xi, x2: xi, y1: y(hh), y2: y(ll),
        stroke: col, "stroke-width": 1
      }));
      // body
      const top = Math.min(y(o), y(c));
      const bh = Math.max(1, Math.abs(y(c) - y(o)));
      svg.appendChild(svgEl("rect", {
        x: xi - cw / 2, y: top, width: cw, height: bh,
        fill: col, stroke: col
      }));
    });

    // last close line
    const lastC = s[n - 1].c;
    svg.appendChild(svgEl("line", {
      x1: padL, x2: W - padR, y1: y(lastC), y2: y(lastC),
      stroke: "#3A3A3A", "stroke-dasharray": "3 3"
    }));
    const lp = svgEl("text", { x: W - padR + 4, y: y(lastC) - 3, fill: "#F28C00", "font-size": 9, "font-weight": 700 });
    lp.textContent = U.fmtNum(lastC, opts.dp != null ? opts.dp : U.dpFor(lastC));
    svg.appendChild(lp);

    // Congressional Average BUY Price Line (Green dashed)
    if (opts.avgBuyPrice && opts.avgBuyPrice >= lo && opts.avgBuyPrice <= hi) {
      const yb = y(opts.avgBuyPrice);
      svg.appendChild(svgEl("line", {
        x1: padL, x2: W - padR, y1: yb, y2: yb,
        stroke: "#00C176", "stroke-width": 1.2, "stroke-dasharray": "4 3", opacity: "0.9"
      }));
      const bTag = svgEl("text", { x: W - padR + 4, y: yb - 2, fill: "#00C176", "font-size": 8, "font-weight": 800 });
      bTag.textContent = "▲ BUY " + U.fmtNum(opts.avgBuyPrice, 2);
      svg.appendChild(bTag);
    }

    // Congressional Average SELL Price Line (Red dashed)
    if (opts.avgSellPrice && opts.avgSellPrice >= lo && opts.avgSellPrice <= hi) {
      const ys = y(opts.avgSellPrice);
      svg.appendChild(svgEl("line", {
        x1: padL, x2: W - padR, y1: ys, y2: ys,
        stroke: "#FF4D4F", "stroke-width": 1.2, "stroke-dasharray": "4 3", opacity: "0.9"
      }));
      const sTag = svgEl("text", { x: W - padR + 4, y: ys - 2, fill: "#FF4D4F", "font-size": 8, "font-weight": 800 });
      sTag.textContent = "▼ SELL " + U.fmtNum(opts.avgSellPrice, 2);
      svg.appendChild(sTag);
    }

    // trade-date marker
    if (opts.markDate) {
      let mi = -1;
      for (let i = 0; i < n; i++) {
        if (s[i].d === opts.markDate) { mi = i; break; }
        if (s[i].d > opts.markDate) { mi = i; break; }
      }
      if (mi < 0) mi = 0;
      svg.appendChild(svgEl("line", {
        x1: x(mi), x2: x(mi), y1: padT, y2: padT + priceH + 4 + volH,
        stroke: "#F28C00", "stroke-width": 1.5, "stroke-dasharray": "3 2", opacity: "0.95"
      }));
      const mt = svgEl("text", {
        x: U.clamp(x(mi) - 16, padL, W - 70), y: padT + 10,
        fill: "#F28C00", "font-size": 8, "font-weight": 800
      });
      mt.textContent = "TX";
      svg.appendChild(mt);
    }

    // crosshair
    const chg = svgEl("g", { visibility: "hidden" });
    const vline = svgEl("line", { y1: padT, y2: padT + priceH + 4 + volH, stroke: "#F28C00", "stroke-width": 1 });
    chg.appendChild(vline);
    svg.appendChild(chg);
    const info = U.el("div", { class: "xh-info", "aria-hidden": "true" });
    container.appendChild(info);

    let idx = n - 1;
    function show(i) {
      idx = U.clamp(i, 0, n - 1);
      const p = s[idx];
      chg.setAttribute("visibility", "visible");
      vline.setAttribute("x1", x(idx)); vline.setAttribute("x2", x(idx));
      const o = p.o != null ? p.o : p.c;
      const rows = [p.d];
      rows.push("O " + U.fmtNum(o, 2) + "  H " + U.fmtNum(p.h != null ? p.h : p.c, 2) +
        "  L " + U.fmtNum(p.l != null ? p.l : p.c, 2) + "  C " + U.fmtNum(p.c, 2));
      if (p.v) rows.push("VOL " + U.fmtVol(p.v));
      if (opts.markDate && p.d === opts.markDate) rows.push("« TRADE DATE");
      info.textContent = rows.join("\n");
      if (opts.onCrosshair) opts.onCrosshair(idx, p);
    }
    function hide() {
      chg.setAttribute("visibility", "hidden");
      info.textContent = "";
      if (opts.onCrosshair) opts.onCrosshair(-1, null);
    }
    svg.addEventListener("pointermove", e => {
      const r = svg.getBoundingClientRect();
      const px = (e.clientX - r.left) * (W / r.width);
      show(Math.round((px - padL) / ((W - padL - padR) / Math.max(1, n - 1))));
    });
    svg.addEventListener("pointerleave", hide);
    container.tabIndex = 0;
    container.addEventListener("keydown", e => {
      if (e.key === "ArrowLeft") { show(idx - 1); e.preventDefault(); }
      else if (e.key === "ArrowRight") { show(idx + 1); e.preventDefault(); }
      else if (e.key === "Home") { show(0); e.preventDefault(); }
      else if (e.key === "End") { show(n - 1); e.preventDefault(); }
      else if (e.key === "Enter") { if (opts.onPick) opts.onPick(idx, s[idx]); e.preventDefault(); }
    });
    // auto-show trade bar if markDate present
    if (opts.markDate) {
      let mi = n - 1;
      for (let i = 0; i < n; i++) {
        if (s[i].d === opts.markDate || s[i].d > opts.markDate) { mi = i; break; }
      }
      show(mi);
    }
    container.__chart = { show, hide, getIndex: () => idx };
    return svg;
  }

  /* ---------- sparkline ---------- */
  function sparkline(container, values, opts) {
    container.innerHTML = "";
    const W = 96, H = 26;
    const svg = svgEl("svg", { width: "100%", height: H, viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", "aria-hidden": "true" });
    let lo = Math.min.apply(null, values), hi = Math.max.apply(null, values);
    if (lo === hi) { lo -= 1; hi += 1; }
    const x = i => i * (W - 2) / (values.length - 1) + 1;
    const y = v => 2 + (hi - v) / (hi - lo) * (H - 4);
    const pts = values.map((v, i) => x(i).toFixed(1) + "," + y(v).toFixed(1));
    svg.appendChild(svgEl("path", { d: "M" + pts.join(" L"), fill: "none", stroke: (opts && opts.color) || "#8A8A8A", "stroke-width": 1 }));
    container.appendChild(svg);
    return svg;
  }

  /* ---------- multi mini-series (sector intraday) ---------- */
  function miniLines(container, sets, opts) {
    container.innerHTML = "";
    const W = Math.max(200, container.clientWidth || 300);
    const H = Math.max(60, container.clientHeight || 90);
    const padL = 4, padR = 34, padT = 6, padB = 12;
    const svg = svgEl("svg", { width: "100%", height: "100%", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": (opts && opts.aria) || "sector intraday" });
    container.appendChild(svg);
    let lo = 0, hi = 0;
    sets.forEach(st => st.points.forEach(v => { lo = Math.min(lo, v); hi = Math.max(hi, v); }));
    const p = (hi - lo) * 0.08 || 0.5; lo -= p; hi += p;
    const x = i => padL + i * (W - padL - padR) / 23;
    const y = v => padT + (hi - v) / (hi - lo) * (H - padT - padB);
    // zero baseline
    svg.appendChild(svgEl("line", { x1: padL, x2: W - padR, y1: y(0), y2: y(0), stroke: "#3A3A3A", "stroke-dasharray": "2 3" }));
    const zt = svgEl("text", { x: W - padR + 3, y: y(0) + 3, fill: "#5C5C5C", "font-size": 8 }); zt.textContent = "0%";
    svg.appendChild(zt);
    [hi - p, lo + p].forEach(t => {
      const tx = svgEl("text", { x: W - padR + 3, y: y(t) + 3, fill: "#5C5C5C", "font-size": 8 });
      tx.textContent = U.fmtPct(t); svg.appendChild(tx);
    });
    const colors = { "AI-TECH": "#00C176", "ENERGY": "#FFB454", "FINANCIALS": "#3FA7A3" };
    sets.forEach(st => {
      const pts = st.points.map((v, i) => x(i).toFixed(1) + "," + y(v).toFixed(1));
      svg.appendChild(svgEl("path", { d: "M" + pts.join(" L"), fill: "none", stroke: colors[st.sector] || "#D7D7D7", "stroke-width": 1.2 }));
      if (!opts || opts.labels !== false) {
        const lx = svgEl("text", { x: padL + 2, y: y(st.points[st.points.length - 1]) + 3, fill: colors[st.sector] || "#D7D7D7", "font-size": 8, "font-weight": 700 });
        lx.textContent = st.sector.replace("-TECH", "");
        svg.appendChild(lx);
      }
    });
    return svg;
  }

  /* ---------- squarified treemap layout ----------
     items: [{key, value, payload}], rect {x,y,w,h} -> [{key,x,y,w,h,payload}] */
  function squarify(items, rect) {
    const out = [];
    const total = items.reduce((a, b) => a + Math.max(0, b.value), 0);
    if (total <= 0 || rect.w <= 0 || rect.h <= 0) return out;
    const scale = rect.w * rect.h / total;
    let row = [], rowVals = [], rest = items.slice(), rx = rect.x, ry = rect.y, rw = rect.w, rh = rect.h;
    function worst(vals, side) {
      let s = 0, mx = 0, mn = Infinity;
      vals.forEach(v => { s += v; mx = Math.max(mx, v); mn = Math.min(mn, v); });
      const s2 = s * s, side2 = side * side;
      return Math.max(side2 * mx / s2, s2 / (side2 * mn));
    }
    function layoutRow(rowItems, vals) {
      const s = vals.reduce((a, b) => a + b, 0);
      if (rw >= rh) {
        const w = s * scale / rh; let y = ry;
        rowItems.forEach((it, i) => { const h = vals[i] * scale / w; out.push({ key: it.key, payload: it.payload, x: rx, y: y, w: w, h: h }); y += h; });
        rx += w; rw -= w;
      } else {
        const h = s * scale / rw; let x = rx;
        rowItems.forEach((it, i) => { const w = vals[i] * scale / h; out.push({ key: it.key, payload: it.payload, x: x, y: ry, w: w, h: h }); x += w; });
        ry += h; rh -= h;
      }
    }
    while (rest.length) {
      const it = rest[0], v = Math.max(0, it.value);
      const side = Math.min(rw, rh);
      // worst-aspect must be computed in absolute AREA units (value × scale)
      const areas = rowVals.map(x => x * scale), aNew = v * scale;
      if (!row.length || worst(areas.concat(aNew), side) <= worst(areas, side)) { row.push(it); rowVals.push(v); rest.shift(); }
      else { layoutRow(row, rowVals); row = []; rowVals = []; }
    }
    if (row.length) layoutRow(row, rowVals);
    return out;
  }

  G.charts = { lineVolume, candlestickVolume, sparkline, miniLines, squarify, niceTicks, svgEl };
})(window.GMT);
