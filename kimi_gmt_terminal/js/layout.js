/* GMT layout engine: 12-col grid, drag/resize with snap + collision resolution,
   pin/lock, minimize/maximize, add/remove/restore, presets, localStorage persistence.
   Widgets can never overlap or leave the canvas. Stacked mode <1024px: no free drag. */
window.GMT = window.GMT || {};
(function (G) {
  "use strict";
  const U = G.util, el = U.el;
  const COLS = 12, ROWH = 26, GAP = 6;

  /* CONGRESS is default merge desk: disclosures + holders + chart + sector overlap */
  const CONGRESS = [
    { id: "cwire", x: 0, y: 0, w: 7, h: 16 },
    { id: "returns", x: 7, y: 0, w: 5, h: 16 },
    { id: "focuschart", x: 0, y: 16, w: 7, h: 11 },
    { id: "holders", x: 7, y: 16, w: 5, h: 6 },
    { id: "polbook", x: 7, y: 22, w: 5, h: 5 },
    { id: "sectordesk", x: 0, y: 27, w: 12, h: 10 }
  ];
  const DEFAULTS = CONGRESS;
  const PRESETS = {
    CONGRESS: CONGRESS,
    GLOBAL: [
      { id: "heat", x: 0, y: 0, w: 8, h: 15 },
      { id: "breadth", x: 8, y: 0, w: 4, h: 6 },
      { id: "news", x: 8, y: 6, w: 4, h: 9 },
      { id: "aapl", x: 0, y: 15, w: 7, h: 11 },
      { id: "sector", x: 7, y: 15, w: 5, h: 11 },
      { id: "metals", x: 0, y: 26, w: 7, h: 12 },
      { id: "pulse", x: 7, y: 26, w: 5, h: 12 },
      { id: "indexmap", x: 7, y: 38, w: 5, h: 7 },
      { id: "ticker", x: 0, y: 45, w: 12, h: 7 }
    ],
    EQUITIES: [
      { id: "heat", x: 0, y: 0, w: 8, h: 13 }, { id: "breadth", x: 8, y: 0, w: 4, h: 6 },
      { id: "news", x: 8, y: 6, w: 4, h: 7 }, { id: "aapl", x: 0, y: 13, w: 7, h: 11 },
      { id: "sector", x: 7, y: 13, w: 5, h: 11 }, { id: "indexmap", x: 0, y: 24, w: 12, h: 6 }
    ],
    METALS: [
      { id: "metals", x: 0, y: 0, w: 7, h: 15 }, { id: "pulse", x: 7, y: 0, w: 5, h: 12 },
      { id: "indexmap", x: 7, y: 12, w: 5, h: 7 }, { id: "heat", x: 0, y: 15, w: 7, h: 11 },
      { id: "breadth", x: 7, y: 19, w: 5, h: 7 }, { id: "news", x: 0, y: 26, w: 12, h: 6 },
      { id: "ticker", x: 0, y: 32, w: 12, h: 6 }
    ],
    NEWS: [
      { id: "news", x: 0, y: 0, w: 5, h: 17 }, { id: "heat", x: 5, y: 0, w: 7, h: 11 },
      { id: "breadth", x: 5, y: 11, w: 7, h: 6 }, { id: "ticker", x: 0, y: 17, w: 12, h: 7 },
      { id: "indexmap", x: 0, y: 24, w: 12, h: 6 }
    ]
  };

  const ASOF_OF = { metals: "metalsAsOf", pulse: "LIVE" };

  const L = {
    layout: [],
    nodes: {},
    stacked: window.matchMedia("(max-width:1023px)").matches,

    load() {
      const saved = U.store.get("layout.v3", null);
      const valid = saved && Array.isArray(saved.items) && saved.items.every(i => G.widgets.WIDGETS[i.id]);
      this.layout = valid ? saved.items : JSON.parse(JSON.stringify(DEFAULTS));
      // ensure every known widget has an entry (for restore/add)
      Object.keys(G.widgets.WIDGETS).forEach(id => {
        if (!this.layout.find(i => i.id === id)) {
          const d = DEFAULTS.find(x => x.id === id) || { x: 0, y: 99, w: 4, h: 5 };
          this.layout.push({ id: id, x: d.x, y: d.y, w: d.w, h: d.h, visible: false });
        }
      });
      this.layout.forEach(i => {
        if (i.visible === undefined) i.visible = true;
        const def = G.widgets.WIDGETS[i.id];
        if (!def) { i.visible = false; return; }
        const min = def.min;
        i.w = Math.max(i.w, min[0]); i.h = Math.max(i.h, min[1]);
      });
    },
    save() {
      U.store.set("layout.v3", { items: this.layout.map(i => ({ id: i.id, x: i.x, y: i.y, w: i.w, h: i.h, pinned: !!i.pinned, visible: i.visible !== false, min: !!i.min })) });
    },

    entry(id) { return this.layout.find(i => i.id === id); },
    visibleItems() { return this.layout.filter(i => i.visible !== false); },

    /* occupancy grid over rows [0..R) */
    buildOcc(ignoreId, R) {
      const occ = [];
      for (let r = 0; r < R; r++) occ.push(new Array(COLS).fill(null));
      this.visibleItems().forEach(i => {
        if (i.id === ignoreId || i.min) return;
        for (let y = i.y; y < i.y + i.h; y++) for (let x = i.x; x < i.x + i.w; x++) {
          if (y < R && x >= 0 && x < COLS) occ[y][x] = i.id;
        }
      });
      return occ;
    },
    isFree(occ, rect) {
      if (rect.x < 0 || rect.x + rect.w > COLS || rect.y < 0) return false;
      for (let y = rect.y; y < rect.y + rect.h; y++) {
        if (y >= occ.length) return false;
        for (let x = rect.x; x < rect.x + rect.w; x++) if (occ[y][x]) return false;
      }
      return true;
    },
    findPlace(rect, ignoreId) {
      const R = this.bottom() + rect.h + 30;
      const occ = this.buildOcc(ignoreId, R);
      rect.x = U.clamp(rect.x, 0, COLS - rect.w);
      rect.y = Math.max(0, rect.y);
      if (this.isFree(occ, rect)) return rect;
      // scan downward (same x), then other x offsets, expanding
      for (let dy = 0; dy < R; dy++) {
        for (let dx = 0; dx <= COLS - rect.w; dx++) {
          const cand = { x: U.clamp(rect.x + (dx % 2 ? Math.ceil(dx / 2) : -Math.floor(dx / 2)), 0, COLS - rect.w), y: rect.y + dy, w: rect.w, h: rect.h };
          if (this.isFree(occ, cand)) return cand;
        }
      }
      return { x: 0, y: R, w: rect.w, h: rect.h };
    },
    bottom() { return this.visibleItems().reduce((b, i) => Math.max(b, i.min ? i.y + 1 : i.y + i.h), 0); },
    compact() {
      const R = this.bottom() + 40;
      let moved = true, guard = 0;
      while (moved && guard++ < 60) {
        moved = false;
        this.visibleItems().forEach(i => {
          if (i.pinned || i.min) return;
          const occ = this.buildOcc(i.id, R);
          while (i.y > 0 && this.isFree(occ, { x: i.x, y: i.y - 1, w: i.w, h: i.h })) { i.y--; moved = true; }
        });
      }
    },

    colW() { const gw = U.$("#grid").clientWidth; return (gw - (COLS + 1) * GAP) / COLS; },
    toPx(r) {
      const cw = this.colW();
      return {
        x: GAP + r.x * (cw + GAP), y: GAP + r.y * (ROWH + GAP),
        w: r.w * cw + (r.w - 1) * GAP, h: r.min ? 22 : r.h * ROWH + (r.h - 1) * GAP
      };
    },

    mount() {
      const grid = U.$("#grid");
      grid.innerHTML = "";
      this.nodes = {};
      this.layout.forEach(item => {
        const def = G.widgets.WIDGETS[item.id];
        const node = el("section", {
          class: "widget", id: "w-" + item.id, "aria-label": def.title,
          style: item.visible === false ? "display:none" : ""
        });
        // title bar
        const tb = el("div", { class: "w-title" });
        tb.appendChild(el("span", { class: "w-num", text: def.num }));
        tb.appendChild(el("span", { class: "w-name", text: def.title }));
        tb.appendChild(el("span", { class: "w-asof", id: "asof-" + item.id }));
        // mobile reorder buttons
        ["▲", "▼"].forEach((sym, k) => {
          tb.appendChild(el("button", {
            class: "w-btn ord-btn", text: sym, "aria-label": (k ? "move down" : "move up"),
            onclick: () => this.reorder(item.id, k ? 1 : -1)
          }));
        });
        tb.appendChild(el("button", {
          class: "w-btn", text: item.pinned ? "🔒" : "📌", "aria-label": "pin/lock widget", "aria-pressed": !!item.pinned,
          title: "pin/lock against drag & resize",
          onclick: () => { item.pinned = !item.pinned; node.classList.toggle("pinned", item.pinned); this.save(); this.mount(); }
        }));
        tb.appendChild(el("button", {
          class: "w-btn", text: item.min ? "▣" : "—", "aria-label": "minimize widget",
          onclick: () => { item.min = !item.min; this.save(); this.applyAll(); if (!item.min) G.app.rerender(item.id); }
        }));
        tb.appendChild(el("button", {
          class: "w-btn", text: "▢", "aria-label": "maximize widget",
          onclick: () => this.maximize(item.id)
        }));
        tb.appendChild(el("button", {
          class: "w-btn", text: "✕", "aria-label": "close widget (restorable via ADD WIDGET)",
          onclick: () => { item.visible = false; this.save(); this.applyAll(); G.app.syncAddMenu(); }
        }));
        node.appendChild(tb);
        const body = el("div", { class: "w-body", id: "body-" + item.id });
        node.appendChild(body);
        const rz = el("div", { class: "w-resize", "aria-hidden": "true" });
        node.appendChild(rz);
        if (item.pinned) node.classList.add("pinned");
        grid.appendChild(node);
        this.nodes[item.id] = node;
        this.bindDrag(item, node, tb);
        this.bindResize(item, node, rz);
        this.observe(item.id, body);
      });
      this.applyAll();
    },

    observe(id, body) {
      if (!("ResizeObserver" in window)) return;
      let t, first = true, lastW = 0, lastH = 0;
      const ro = new ResizeObserver(() => {
        const w = body.clientWidth, h = body.clientHeight;
        // skip the initial observation (mount's applyAll has already set the final
        // size and renderAll draws against it) and skip content-only mutations:
        // re-rendering on a no-change delivery clears the body and leaves async
        // chart draws (rAF) racing whoever reads the DOM next — real size changes only
        if (first) { first = false; lastW = w; lastH = h; return; }
        if (w === lastW && h === lastH) return;
        lastW = w; lastH = h;
        clearTimeout(t);
        t = setTimeout(() => {
          const it = this.entry(id);
          if (it && it.visible !== false && !it.min) G.app.rerender(id, true);
        }, 220);
      });
      ro.observe(body);
    },

    applyAll() {
      const grid = U.$("#grid");
      // DOM order = layout order (stacked mode uses it)
      this.layout.forEach(i => { const n = this.nodes[i.id]; if (n && n.parentNode === grid) grid.appendChild(n); });
      this.visibleItems().forEach(i => {
        const n = this.nodes[i.id];
        const px = this.toPx(i);
        n.style.left = px.x + "px"; n.style.top = px.y + "px";
        n.style.width = px.w + "px"; n.style.height = px.h + "px";
        n.style.display = "";
      });
      this.layout.filter(i => i.visible === false).forEach(i => { this.nodes[i.id].style.display = "none"; });
      grid.style.height = (this.bottom() * (ROWH + GAP) + 2 * GAP) + "px";
    },

    maximize(id) {
      const i = this.entry(id);
      if (i._max) {
        Object.assign(i, i._max); delete i._max;
      } else {
        i._max = { x: i.x, y: i.y, w: i.w, h: i.h };
        const others = this.visibleItems().filter(o => o.id !== id);
        i.x = 0; i.y = others.length ? Math.min.apply(null, others.map(o => o.y)) : 0;
        i.w = COLS; i.h = Math.max(i.h, 14);
        i.min = false;
        // resolve collisions caused by expansion
        const R = this.bottom() + i.h + 30;
        others.forEach(o => { if (!o.pinned) { const occ = this.buildOcc(o.id, R); if (!this.isFree(occ, o)) Object.assign(o, this.findPlace({ x: o.x, y: o.y + 1, w: o.w, h: o.h }, o.id)); } });
      }
      this.save(); this.applyAll(); G.app.rerender(id, true);
    },

    reorder(id, dir) {
      const idx = this.layout.indexOf(this.entry(id));
      const j = idx + dir;
      if (j < 0 || j >= this.layout.length) return;
      const tmp = this.layout[idx]; this.layout[idx] = this.layout[j]; this.layout[j] = tmp;
      // keep grid positions stable on desktop by swapping rects too
      if (!this.stacked) {
        const a = this.layout[idx], b = this.layout[j];
        const r = { x: a.x, y: a.y }; a.x = b.x; a.y = b.y; b.x = r.x; b.y = r.y;
      }
      this.save(); this.applyAll();
    },

    bindDrag(item, node, handle) {
      let drag = null;
      handle.addEventListener("pointerdown", e => {
        if (!G.state.prefs.editMode || item.pinned || this.stacked) return;
        if (e.target.closest("button")) return;
        drag = { startX: e.clientX, startY: e.clientY, ox: item.x, oy: item.y };
        node.classList.add("dragging");
        try { handle.setPointerCapture(e.pointerId); } catch (err) { /* synthetic/unsupported pointer */ }
        e.preventDefault();
      });
      handle.addEventListener("pointermove", e => {
        if (!drag) return;
        const cw = this.colW();
        const dx = Math.round((e.clientX - drag.startX) / (cw + GAP));
        const dy = Math.round((e.clientY - drag.startY) / (ROWH + GAP));
        const rect = { x: U.clamp(drag.ox + dx, 0, COLS - item.w), y: Math.max(0, drag.oy + dy), w: item.w, h: item.h };
        const occ = this.buildOcc(item.id, this.bottom() + item.h + 30);
        const free = this.isFree(occ, rect);
        const ph = U.$("#placeholder");
        const px = this.toPx(rect);
        ph.style.display = "block";
        ph.style.left = px.x + "px"; ph.style.top = px.y + "px";
        ph.style.width = px.w + "px"; ph.style.height = px.h + "px";
        ph.classList.toggle("blocked", !free);
        drag.rect = rect; drag.free = free;
      });
      const drop = () => {
        if (!drag) return;
        node.classList.remove("dragging");
        U.$("#placeholder").style.display = "none";
        if (drag.rect) {
          if (drag.free) { item.x = drag.rect.x; item.y = drag.rect.y; }
          else Object.assign(item, this.findPlace(drag.rect, item.id));
          this.compact();
          this.save(); this.applyAll();
        }
        drag = null;
      };
      handle.addEventListener("pointerup", drop);
      handle.addEventListener("pointercancel", drop);
    },

    bindResize(item, node, rz) {
      let rs = null;
      rz.addEventListener("pointerdown", e => {
        if (!G.state.prefs.editMode || item.pinned || this.stacked) return;
        rs = { startX: e.clientX, startY: e.clientY, ow: item.w, oh: item.h };
        try { rz.setPointerCapture(e.pointerId); } catch (err) { /* synthetic/unsupported pointer */ }
        e.preventDefault(); e.stopPropagation();
      });
      rz.addEventListener("pointermove", e => {
        if (!rs) return;
        const min = G.widgets.WIDGETS[item.id].min;
        const cw = this.colW();
        const dw = Math.round((e.clientX - rs.startX) / (cw + GAP));
        const dh = Math.round((e.clientY - rs.startY) / (ROWH + GAP));
        const rect = {
          x: item.x, y: item.y,
          w: U.clamp(rs.ow + dw, min[0], COLS - item.x),
          h: Math.max(min[1], rs.oh + dh)
        };
        const occ = this.buildOcc(item.id, this.bottom() + rect.h + 30);
        rs.free = this.isFree(occ, rect); rs.rect = rect;
        const px = this.toPx(rect);
        node.style.width = px.w + "px"; node.style.height = px.h + "px";
        node.style.opacity = rs.free ? "" : ".6";
      });
      const up = () => {
        if (!rs) return;
        node.style.opacity = "";
        if (rs.rect) {
          if (rs.free) { item.w = rs.rect.w; item.h = rs.rect.h; }
          this.compact(); this.save();
        }
        rs = null;
        this.applyAll(); G.app.rerender(item.id, true);
      };
      rz.addEventListener("pointerup", up);
      rz.addEventListener("pointercancel", up);
    },

    addWidget(id) {
      const i = this.entry(id);
      const d = DEFAULTS.find(x => x.id === id) || { w: 4, h: 6 };
      const min = G.widgets.WIDGETS[id].min;
      const rect = this.findPlace({ x: 0, y: this.bottom(), w: Math.max(d.w, min[0]), h: Math.max(d.h, min[1]) }, id);
      Object.assign(i, rect, { visible: true, min: false });
      this.save(); this.mount(); G.app.renderWidget(id);
      this.applyAll();
    },
    removeWidget(id) { const i = this.entry(id); if (i) { i.visible = false; this.save(); this.applyAll(); } },

    applyPreset(name) {
      const spec = PRESETS[name];
      if (!spec) return;
      this.layout.forEach(i => {
        const s = spec.find(x => x.id === i.id);
        if (s) { Object.assign(i, JSON.parse(JSON.stringify(s)), { visible: true, min: false }); }
        else i.visible = false;
      });
      G.state.prefs.preset = name;
      G.app.savePrefs(); this.save(); this.mount(); G.app.renderAll(); G.app.syncAddMenu();
    },
    resetDefault() {
      this.layout = JSON.parse(JSON.stringify(DEFAULTS));
      Object.keys(G.widgets.WIDGETS).forEach(id => {
        if (!this.layout.find(i => i.id === id)) this.layout.push({ id: id, x: 0, y: 99, w: 4, h: 5, visible: false });
      });
      G.state.prefs.preset = "CONGRESS";
      G.app.savePrefs(); this.save(); this.mount(); G.app.renderAll(); G.app.syncAddMenu();
    }
  };

  G.layout = L;
  G.LAYOUT_DEFAULTS = DEFAULTS;
  G.LAYOUT_PRESETS = PRESETS;
})(window.GMT);
