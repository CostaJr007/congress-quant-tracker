/* CI://TERMINAL congress widgets — month browser + LIVE filters (no offline UX) */
window.GMT = window.GMT || {};
(function (G) {
  "use strict";
  const U = G.util, el = U.el;
  const W = G.widgets.WIDGETS;

  function partyCls(p) {
    if (p === "D") return "party-d";
    if (p === "R") return "party-r";
    return "party-i";
  }

  function focusTrade(t) {
    if (!t) return;
    if (t.ticker) G.state.prefs.focusTicker = t.ticker.toUpperCase();
    if (t.politician || t.representative) G.state.prefs.focusPolitician = t.politician || t.representative;
    if (t.trade_date || t.transaction_date) G.state.prefs.focusTradeDate = t.trade_date || t.transaction_date;
    else G.state.prefs.focusTradeDate = null;
    const rawSide = (t.side || t.transaction_type || t.type || "").toUpperCase();
    G.state.prefs.focusTradeType = (rawSide.includes("BUY") || rawSide.includes("PURCHASE")) ? "BUY" : ((rawSide.includes("SELL") || rawSide.includes("SALE")) ? "SELL" : "BUY");
    G.state.prefs.focusTradePrice = t.price || t.trade_price || null;
    G.app.savePrefs();
    G.app.onCongressFocus();
    G.inspector.open("trade", t);
  }

  function focusPol(name) {
    G.state.prefs.focusPolitician = name;
    G.app.savePrefs();
    G.app.onCongressFocus();
    G.inspector.open("politician", { name: name });
  }

  function focusTicker(tk, tradeDate, tradeType, tradePrice) {
    G.state.prefs.focusTicker = (tk || "").toUpperCase();
    if (tradeDate) G.state.prefs.focusTradeDate = tradeDate;
    else G.state.prefs.focusTradeDate = null;
    if (tradeType) G.state.prefs.focusTradeType = tradeType;
    if (tradePrice != null) G.state.prefs.focusTradePrice = tradePrice;
    G.app.savePrefs();
    G.app.onCongressFocus();
  }

  /** format ISO date for dense terminal: keep full YYYY-MM-DD when short space, else MM-DD */
  function fmtDate(d, full) {
    if (!d) return "—";
    const s = String(d).slice(0, 10);
    return full ? s : (s.length >= 10 ? s.slice(5) : s);
  }

  function btn(lab, on, click) {
    return el("button", { class: on ? "on" : "", text: lab, onclick: click });
  }

  /* Group by DEPUTY/SENATOR name (per month view). Heavy filers collapse by default. */
  const MIN_BLOCK = 3;

  function groupByMember(rows) {
    const map = {};
    const order = [];
    (rows || []).forEach(t => {
      const name = t.politician || "Unknown";
      if (!map[name]) {
        map[name] = {
          key: name,
          name: name,
          party: t.party,
          chamber: t.chamber,
          state: t.state_district,
          bioguide_id: t.bioguide_id || null,
          photo_url: t.photo_url || null,
          trades: [],
          buys: 0,
          sells: 0,
          tickers: [],
          last_filed: null,
          last_tx: null
        };
        order.push(name);
      }
      const g = map[name];
      g.trades.push(t);
      if (!g.bioguide_id && t.bioguide_id) g.bioguide_id = t.bioguide_id;
      if (!g.photo_url && t.photo_url) g.photo_url = t.photo_url;
      if (t.side === "BUY") g.buys++;
      else g.sells++;
      if (t.ticker && g.tickers.indexOf(t.ticker) < 0) g.tickers.push(t.ticker);
      if (t.filing_date && (!g.last_filed || t.filing_date > g.last_filed)) g.last_filed = t.filing_date;
      if (t.trade_date && (!g.last_tx || t.trade_date > g.last_tx)) g.last_tx = t.trade_date;
    });
    // most active first (like leaderboard feel)
    return order.map(k => map[k]).sort((a, b) => b.trades.length - a.trades.length);
  }

  /** Resolve photo URLs to absolute paths (terminal is under /terminal/). */
  function absUrl(u) {
    if (!u) return null;
    if (/^https?:\/\//i.test(u)) return u;
    if (u.charAt(0) === "/") {
      try { return (location.origin || "") + u; } catch (e) { return u; }
    }
    return u;
  }

  /** Local /politicians/{bioguide}.jpg → CDN → initials. */
  function photoSrcs(g) {
    const id = g.bioguide_id;
    const list = [];
    if (g.photo_url) list.push(absUrl(g.photo_url));
    if (id) {
      list.push(absUrl("/politicians/" + encodeURIComponent(id) + ".jpg"));
      list.push("https://theunitedstates.io/images/congress/225x275/" + encodeURIComponent(id) + ".jpg");
    }
    return list.filter((u, i, a) => u && a.indexOf(u) === i);
  }

  function renderAvatar(g, size) {
    const sz = size || 40;
    const initials = (g.name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();
    const wrap = el("span", {
      class: "avatar " + partyCls(g.party),
      title: g.name || "",
      style: "width:" + sz + "px;height:" + sz + "px;min-width:" + sz + "px;min-height:" + sz + "px"
    });
    const srcs = photoSrcs(g);
    if (!srcs.length) {
      wrap.textContent = initials;
      return wrap;
    }
    const img = document.createElement("img");
    img.alt = g.name || "photo";
    img.width = sz;
    img.height = sz;
    img.decoding = "async";
    img.referrerPolicy = "no-referrer";
    img.style.cssText = "width:100%;height:100%;object-fit:cover;object-position:top center;display:block";
    let i = 0;
    function showInitials() {
      while (wrap.firstChild) wrap.removeChild(wrap.firstChild);
      wrap.textContent = initials;
    }
    img.onerror = function () {
      i++;
      if (i < srcs.length) {
        img.src = srcs[i];
      } else {
        showInitials();
      }
    };
    img.onload = function () {
      wrap.classList.add("has-photo");
    };
    img.src = srcs[0];
    wrap.appendChild(img);
    return wrap;
  }

  function isBlockExpanded(key) {
    const st = G.state.wireExpand || {};
    // default: collapsed when heavy; expanded when few trades
    if (st[key] === undefined) return false;
    return !!st[key];
  }
  function toggleBlock(key) {
    G.state.wireExpand = G.state.wireExpand || {};
    const cur = isBlockExpanded(key);
    G.state.wireExpand[key] = !cur;
    // for light groups that default open, track explicitly
    G.app.rerender("cwire");
  }
  function memberIsOpen(g) {
    const st = G.state.wireExpand || {};
    if (st[g.key] !== undefined) return !!st[g.key];
    // few trades → open; many → collapsed (anti-spam)
    return g.trades.length < MIN_BLOCK;
  }

  function renderTradeRow(t, dateField, tb) {
    const tr = el("tr", { "data-click": "1", tabindex: "0" });
    const d = (dateField === "trade" ? t.trade_date : t.filing_date) || t.trade_date || "";
    const chg = t.price_change_pct;
    tr.innerHTML =
      `<td class="num" style="font-weight:600">${U.esc(fmtDate(t.trade_date, true))}</td>` +
      `<td class="faint">${U.esc(fmtDate(t.filing_date, true))}</td>` +
      `<td class="${t.side === "BUY" ? "up" : "dn"}" style="font-weight:800">${U.esc(t.side)}</td>` +
      `<td class="org" style="font-weight:800">${U.esc(t.ticker || "—")}</td>` +
      `<td class="num dim" style="font-size:9px">${U.esc((t.amount || "—").replace(/\$/g, "").slice(0, 12))}</td>` +
      `<td class="num ${chg != null ? U.cls(chg) : "dim"}">${chg != null ? U.fmtPct(chg) : "—"}</td>` +
      `<td class="num">${t.score != null ? t.score : "—"}</td>`;
    tr.addEventListener("click", e => { e.stopPropagation(); focusTrade(t); });
    tb.appendChild(tr);
  }

  function renderTradeTable(trades, dateField) {
    const tbl = el("table", { class: "tbl compact" });
    tbl.innerHTML = "<thead><tr><th>TX DATE</th><th>FILED</th><th>SIDE</th><th>TKR</th><th>AMT</th><th>Δ%</th><th>SCR</th></tr></thead>";
    const tb = el("tbody");
    trades.forEach(t => renderTradeRow(t, dateField, tb));
    tbl.appendChild(tb);
    return tbl;
  }

  /* ---------- K. CONGRESS WIRE ---------- */
  W.cwire = {
    num: "11", title: "MEMBERS · BY MONTH", min: [6, 8],
    render(body) {
      const p = G.state.prefs;
      const months = G.datasets.congressMonths || [];
      const meta = G.datasets.cwireMeta || {};
      const rows = G.datasets.cwire || [];
      const active = months.find(m => m.month === p.wireMonth);

      /* --- month browser --- */
      const monthBox = el("div", { class: "month-browser", style: "background:#050505;border-bottom:1px solid var(--line2);padding:4px 8px" });
      
      const mbTop = el("div", { style: "display:flex;align-items:center;justify-content:space-between;margin-bottom:4px" });
      mbTop.appendChild(el("div", {
        class: "mb-head",
        html: `<span class="org" style="font-weight:800;font-size:10px">📅 DISCLOSURE TIMELINE</span> · ` +
          `<span class="dim" style="font-size:9px">indexing by ${(p.wireDateField || "filing") === "trade" ? "execution date" : "official filing date"}</span>`
      }));

      const dateRow = el("div", { class: "seg", style: "display:inline-flex;border:1px solid var(--line2);border-radius:2px;padding:1px;background:#000" });
      dateRow.appendChild(el("button", {
        class: (p.wireDateField || "filing") === "filing" ? "on" : "",
        style: ((p.wireDateField || "filing") === "filing" ? "background:var(--org);color:#000;font-weight:800;" : "") + "font-size:9px;padding:1px 6px",
        text: "FILED DATE",
        onclick: () => { p.wireDateField = "filing"; G.app.savePrefs(); G.app.reloadMonthsAndWire(); }
      }));
      dateRow.appendChild(el("button", {
        class: p.wireDateField === "trade" ? "on" : "",
        style: (p.wireDateField === "trade" ? "background:var(--org);color:#000;font-weight:800;" : "") + "font-size:9px;padding:1px 6px",
        text: "TRADE DATE",
        onclick: () => { p.wireDateField = "trade"; G.app.savePrefs(); G.app.reloadMonthsAndWire(); }
      }));
      mbTop.appendChild(dateRow);
      monthBox.appendChild(mbTop);

      const chipRow = el("div", { class: "month-chips", style: "display:flex;flex-wrap:wrap;gap:3px;align-items:center" });
      chipRow.appendChild(el("button", {
        class: "mchip" + (p.wireMonth === "" ? " on" : ""),
        style: "font-weight:800;font-size:9px;padding:2px 6px",
        text: "✦ ALL MONTHS",
        title: "View all recorded months",
        onclick: () => { p.wireMonth = ""; G.app.savePrefs(); G.app.loadCongressWire(); }
      }));
      // group by year
      const byYear = {};
      months.forEach(m => {
        (byYear[m.year] ||= []).push(m);
      });
      Object.keys(byYear).map(Number).sort((a, b) => b - a).forEach(year => {
        chipRow.appendChild(el("span", { class: "myear", style: "color:var(--org);font-weight:800;font-size:10px;margin-left:4px", text: String(year) }));
        byYear[year].forEach(m => {
          chipRow.appendChild(el("button", {
            class: "mchip" + (p.wireMonth === m.month ? " on" : ""),
            style: "font-size:9px;padding:2px 5px",
            text: m.label.replace(" " + year, "") + " ·" + m.count,
            title: m.label + " · " + m.count + " trades",
            onclick: () => { p.wireMonth = m.month; G.app.savePrefs(); G.app.loadCongressWire(); }
          }));
        });
      });
      monthBox.appendChild(chipRow);
      body.appendChild(monthBox);

      /* --- filters: segmented CHAMBER / PARTY / SIDE --- */
      const filterBar = el("div", {
        class: "toolbar",
        style: "display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:4px 8px;background:var(--bg2);border-bottom:1px solid var(--line2)"
      });

      // 1. CHAMBER GROUP
      const segChamber = el("div", { class: "seg", style: "display:inline-flex;align-items:center;border:1px solid var(--line2);border-radius:2px;padding:1px;background:#050505" });
      segChamber.appendChild(el("span", { class: "faint", style: "font-size:9px;font-weight:800;padding:2px 5px;color:var(--org)", text: "CHAMBER:" }));
      [["ALL", "ALL", "All Chambers"], ["House", "HOUSE", "House of Representatives"], ["Senate", "SENATE", "US Senate"]].forEach(([lab, v, title]) => {
        const on = (p.wireChamber || "ALL") === v;
        segChamber.appendChild(el("button", {
          class: on ? "on" : "",
          style: (on ? "background:var(--org);color:#000;font-weight:800;" : "") + "font-size:9px;padding:2px 6px",
          text: lab,
          title: title,
          onclick: () => { p.wireChamber = v; G.app.savePrefs(); G.app.loadCongressWire(); }
        }));
      });
      filterBar.appendChild(segChamber);

      // 2. PARTY GROUP
      const segParty = el("div", { class: "seg", style: "display:inline-flex;align-items:center;border:1px solid var(--line2);border-radius:2px;padding:1px;background:#050505" });
      segParty.appendChild(el("span", { class: "faint", style: "font-size:9px;font-weight:800;padding:2px 5px;color:var(--org)", text: "PARTY:" }));
      [["ALL", "ALL", "All Parties"], ["(D) DEM", "D", "Democrats"], ["(R) REP", "R", "Republicans"]].forEach(([lab, v, title]) => {
        const on = (p.wireParty || "ALL") === v;
        const col = on ? "background:var(--org);color:#000;font-weight:800;" : (v === "D" ? "color:#3FA7A3;" : (v === "R" ? "color:#FF7B72;" : ""));
        segParty.appendChild(el("button", {
          class: on ? "on" : "",
          style: col + "font-size:9px;padding:2px 6px",
          text: lab,
          title: title,
          onclick: () => { p.wireParty = v; G.app.savePrefs(); G.app.loadCongressWire(); }
        }));
      });
      filterBar.appendChild(segParty);

      // 3. TRADE SIDE GROUP (BUY vs SELL)
      const segSide = el("div", { class: "seg", style: "display:inline-flex;align-items:center;border:1px solid var(--line2);border-radius:2px;padding:1px;background:#050505" });
      segSide.appendChild(el("span", { class: "faint", style: "font-size:9px;font-weight:800;padding:2px 5px;color:var(--org)", text: "SIDE:" }));
      [["ALL TRADES", "ALL", "All buys and sells"], ["▲ BUY", "BUY", "Purchases only"], ["▼ SELL", "SELL", "Sales only"]].forEach(([lab, v, title]) => {
        const on = (p.wireSide || "ALL") === v;
        const col = on
          ? (v === "BUY" ? "background:#00C176;color:#000;font-weight:800;" : (v === "SELL" ? "background:#FF4D4F;color:#000;font-weight:800;" : "background:var(--org);color:#000;font-weight:800;"))
          : (v === "BUY" ? "color:#00C176;" : (v === "SELL" ? "color:#FF4D4F;" : ""));
        segSide.appendChild(el("button", {
          class: on ? "on" : "",
          style: col + "font-size:9px;padding:2px 6px",
          text: lab,
          title: title,
          onclick: () => { p.wireSide = v; G.app.savePrefs(); G.app.loadCongressWire(); }
        }));
      });
      filterBar.appendChild(segSide);

      body.appendChild(filterBar);

      /* search member / ticker */
      const searchRow = el("div", { class: "toolbar" });
      const inp = el("input", {
        type: "search",
        placeholder: "search member or ticker…",
        value: p.wireQ || "",
        style: "flex:1;min-width:120px;background:#0A0A0A;border:1px solid var(--line2);color:var(--ink);padding:3px 8px;font:11px var(--mono)"
      });
      let tmr;
      inp.addEventListener("input", () => {
        clearTimeout(tmr);
        tmr = setTimeout(() => {
          p.wireQ = inp.value.trim();
          G.app.savePrefs();
          G.app.loadCongressWire();
        }, 350);
      });
      searchRow.appendChild(inp);
      searchRow.appendChild(el("button", {
        text: "↻", title: "reload",
        onclick: () => G.app.loadCongressWire()
      }));
      searchRow.appendChild(el("button", {
        style: "background:#121212;border:1px solid #3A3A3A;color:var(--org);font-size:9px;font-weight:800;padding:2px 8px;cursor:pointer;white-space:nowrap;margin-left:auto",
        text: "🏆 RANKINGS",
        title: "Abrir mesa dedicada de Rankings e Retornos",
        onclick: () => {
          G.layout.applyPreset("RANKINGS");
          G.app.syncPresetButtons();
        }
      }));
      body.appendChild(searchRow);

      /* summary */
      const sum = G.datasets.congressSummary;
      const label = p.wireMonth
        ? ((active && active.label) || p.wireMonth)
        : "ALL MONTHS";
      const members = groupByMember(rows);
      body.appendChild(el("div", {
        class: "pad", style: "font-size:10px;padding:4px 8px;border-bottom:1px solid var(--line)",
        html: `<b class="org">${U.esc(label)}</b> · ` +
          `<b>${members.length}</b> members · ` +
          `<b>${meta.total != null ? meta.total : rows.length}</b> trades` +
          (sum ? ` · age ${sum.data_age_days != null ? sum.data_age_days + "d" : "?"}` : "")
      }));

      if (G.state.wireError) {
        body.appendChild(el("div", {
          class: "pad", style: "color:var(--dn)",
          text: "> API error: " + G.state.wireError + " — start FastAPI on :8000"
        }));
        return;
      }

      if (!rows.length) {
        body.appendChild(el("div", { class: "pad dim", text: "> no members/trades for this month" }));
        return;
      }

      /* --- member cards (like web_fused TradeGroupList) --- */
      const scroller = el("div", { class: "wire-scroll" });
      const dateField = p.wireDateField || "filing";

      members.forEach(g => {
        const open = memberIsOpen(g);
        const heavy = g.trades.length >= MIN_BLOCK;
        const tkrPreview = g.tickers.slice(0, 8).join(" ") + (g.tickers.length > 8 ? " +" + (g.tickers.length - 8) : "");

        const card = el("div", { class: "member-card" + (heavy ? " heavy" : "") + (open ? " open" : "") });

        const head = el("div", {
          class: "member-card-head",
          tabindex: "0",
          role: "button",
          "aria-expanded": open
        });

        head.appendChild(el("span", { class: "chev", text: open ? "▾" : "▸" }));
        head.appendChild(renderAvatar(g, 44));

        const meta = el("div", { class: "member-meta" });
        const nameRow = el("div", { class: "member-name" });
        nameRow.appendChild(el("span", { class: "name", text: g.name }));
        nameRow.appendChild(el("span", { class: partyCls(g.party) + " ptag", text: g.party || "?" }));
        nameRow.appendChild(el("span", { class: "chip txn", text: g.trades.length + " trades" }));
        meta.appendChild(nameRow);
        meta.appendChild(el("div", {
          class: "member-sub",
          html: `<span class="dim">${U.esc(g.chamber || "")}${g.state ? " · " + U.esc(g.state) : ""}</span>` +
            ` · <span class="up">${g.buys} buy</span>` +
            ` · <span class="dn">${g.sells} sell</span>` +
            (g.last_filed ? ` · filed ${U.esc(fmtDate(g.last_filed, true))}` : "")
        }));
        if (!open) {
          meta.appendChild(el("div", {
            class: "member-tickers dim",
            title: g.tickers.join(", "),
            text: tkrPreview
          }));
        }
        head.appendChild(meta);
        head.appendChild(el("span", { class: "expand-hint faint", text: open ? "hide" : "expand" }));

        head.addEventListener("click", () => {
          G.state.wireExpand = G.state.wireExpand || {};
          G.state.wireExpand[g.key] = !open;
          G.app.rerender("cwire");
        });
        head.addEventListener("dblclick", e => {
          e.preventDefault();
          focusPol(g.name);
        });
        card.appendChild(head);

        if (open) {
          const bodyTrades = el("div", { class: "member-card-body" });
          // action row
          const acts = el("div", { class: "toolbar", style: "padding:2px 6px" });
          acts.appendChild(el("button", {
            text: "OPEN BOOK",
            class: "on",
            onclick: e => { e.stopPropagation(); focusPol(g.name); }
          }));
          acts.appendChild(el("span", {
            class: "faint", style: "font-size:9px",
            text: g.tickers.length + " tickers · click row → chart"
          }));
          bodyTrades.appendChild(acts);
          bodyTrades.appendChild(renderTradeTable(g.trades, dateField));
          card.appendChild(bodyTrades);
        }

        scroller.appendChild(card);
      });

      body.appendChild(scroller);
      body.appendChild(el("div", {
        class: "faint", style: "font-size:8px;padding:2px 8px",
        text: "> cards = members in this month · expand for trades · OPEN BOOK / dbl-click → politician desk"
      }));
    }
  };

  /* ---------- L. ASSET HOLDERS ---------- */
  W.holders = {
    num: "12", title: "ASSET HOLDERS · SAME TICKER", min: [4, 5],
    render(body) {
      const tk = G.state.prefs.focusTicker || "—";
      const h = G.datasets.holders;
      const bar = el("div", { class: "toolbar" });
      bar.appendChild(el("span", { class: "org", style: "font-weight:800;font-size:13px", text: tk }));
      if (h && h.name) bar.appendChild(el("span", { class: "dim", text: h.name }));
      body.appendChild(bar);

      if (!h || !h.holders) {
        body.appendChild(el("div", { class: "pad dim", text: "> select a trade or ticker" }));
        return;
      }

      if (h && h.positioning) {
        const pos = h.positioning;
        const pcrCard = el("div", {
          style: "margin:4px 6px;padding:6px 8px;background:#0A0E14;border:1px solid var(--line2);border-radius:3px;display:flex;flex-direction:column;gap:4px"
        });
        const vwapRow = (pos.avg_buy_price || pos.avg_sell_price)
          ? `<div style="display:flex;justify-content:space-between;font-size:9px;border-top:1px dashed #292929;padding-top:3px;margin-top:2px">` +
            (pos.avg_buy_price ? `<span style="color:#00C176;font-weight:700">▲ AVG BUY: $${U.fmtNum(pos.avg_buy_price, 2)}</span>` : '<span class="dim">▲ AVG BUY: —</span>') +
            (pos.avg_sell_price ? `<span style="color:#FF4D4F;font-weight:700">▼ AVG SELL: $${U.fmtNum(pos.avg_sell_price, 2)}</span>` : '<span class="dim">▼ AVG SELL: —</span>') +
            `</div>`
          : "";
        pcrCard.innerHTML =
          `<div style="display:flex;justify-content:space-between;align-items:center;font-size:10px">` +
          `<span style="font-weight:800;color:${pos.sentiment_color}">● ${pos.sentiment}</span>` +
          `<span class="dim">P/C RATIO: <b style="color:var(--org)">${pos.put_call_ratio}</b> (${pos.buy_count}B / ${pos.sell_count}S)</span>` +
          `</div>` +
          `<div style="height:5px;width:100%;background:#FF4D4F;border-radius:2px;overflow:hidden;display:flex">` +
          `<div style="width:${pos.buy_pct}%;background:#00C176;height:100%"></div>` +
          `</div>` +
          `<div style="display:flex;justify-content:space-between;font-size:9px" class="faint">` +
          `<span style="color:#00C176">▲ BUY ${pos.buy_pct}% ($${U.fmtVol(pos.buy_volume)})</span>` +
          `<span style="color:#FF4D4F">▼ SELL ${pos.sell_pct}% ($${U.fmtVol(pos.sell_volume)})</span>` +
          `</div>` +
          vwapRow;
        body.appendChild(pcrCard);
      }

      body.appendChild(el("div", {
        class: "pad", style: "font-size:10px;padding:3px 8px",
        html: `<span class="up">House ${h.house_count || 0}</span> · <span class="org">Senate ${h.senate_count || 0}</span> · ` +
          `<b>${h.unique_politicians || 0}</b> members · ${h.total_trades || 0} trades` +
          (h.sector ? ` · ${U.esc(h.sector)}` : "")
      }));

      const list = h.holders || [];
      if (!list.length) {
        body.appendChild(el("div", { class: "pad dim", text: "> no members traded " + tk }));
        return;
      }
      const scroller = el("div", { class: "wire-scroll" });
      list.forEach(pol => {
        const row = el("div", {
          class: "holder-row",
          tabindex: "0",
          "data-click": "1"
        });
        row.appendChild(renderAvatar({
          name: pol.name,
          party: pol.party,
          bioguide_id: pol.bioguide_id,
          photo_url: pol.photo_url || (pol.bioguide_id ? "/politicians/" + pol.bioguide_id + ".jpg" : null)
        }, 32));
        const meta = el("div", { class: "holder-meta" });
        meta.innerHTML =
          `<div><span class="name">${U.esc((pol.name || "").slice(0, 24))}</span> ` +
          `<span class="${partyCls(pol.party)}">${U.esc(pol.party || "?")}</span> ` +
          `<span class="dim">${U.esc((pol.chamber || "").slice(0, 6))}</span></div>` +
          `<div class="faint">${pol.trades} tx · <span class="up">${pol.buys || 0}B</span>/<span class="dn">${pol.sells || 0}S</span>` +
          ` · last ${U.esc(fmtDate(pol.last_date, true))} ${U.esc(pol.last_side || "")}</div>`;
        row.appendChild(meta);
        row.addEventListener("click", () => focusPol(pol.name));
        scroller.appendChild(row);
      });
      body.appendChild(scroller);
    }
  };

  /* ---------- M. SECTOR DESK ---------- */
  W.sectordesk = {
    num: "13", title: "SECTOR DESK · HOUSE×SENATE", min: [5, 6],
    render(body) {
      const p = G.state.prefs;
      const sectors = G.datasets.sectorList || [];
      const desk = G.datasets.sectorDesk;
      const bar = el("div", { class: "toolbar" });
      const sel = el("select", {
        style: "background:#0A0A0A;color:var(--ink);border:1px solid var(--line2);font:11px var(--mono);padding:2px 4px;max-width:220px",
        onchange: (e) => {
          p.sectorFilter = e.target.value;
          G.app.savePrefs();
          G.app.loadSectorDesk(p.sectorFilter);
        }
      });
      const cur = (desk && desk.sector) || p.sectorFilter || (sectors[0] && sectors[0].sector) || "";
      if (!sectors.length && cur) sel.appendChild(el("option", { value: cur, text: cur, selected: "selected" }));
      sectors.forEach(s => {
        const o = el("option", { value: s.sector, text: s.sector + " (" + s.n + ")" });
        if (s.sector === cur) o.selected = true;
        sel.appendChild(o);
      });
      bar.appendChild(sel);
      body.appendChild(bar);

      if (!desk) {
        body.appendChild(el("div", { class: "pad dim", text: "> pick a sector" }));
        return;
      }

      if (desk && desk.positioning) {
        const pos = desk.positioning;
        const secCard = el("div", {
          style: "margin:3px 6px;padding:4px 8px;background:#0A0E14;border:1px solid var(--line2);border-radius:3px;display:flex;justify-content:space-between;align-items:center;font-size:10px"
        });
        secCard.innerHTML =
          `<span style="font-weight:800;color:${pos.sentiment_color}">● ${pos.sentiment} (${pos.buy_pct}% BUY)</span>` +
          `<span class="dim">P/C RATIO: <b style="color:var(--org)">${pos.put_call_ratio}</b> · Vol: $${U.fmtVol(pos.buy_volume + pos.sell_volume)}</span>`;
        body.appendChild(secCard);
      }
      body.appendChild(el("div", {
        class: "pad", style: "font-size:10px;padding:3px 8px",
        html: `<b class="org">${U.esc(desk.sector || "")}</b> · ` +
          `<span class="up">H ${desk.house_count || 0}</span> · <span class="org">S ${desk.senate_count || 0}</span> · ` +
          `${desk.unique_politicians || 0} members · ${desk.unique_tickers || 0} tickers`
      }));

      const cols = el("div", { style: "display:grid;grid-template-columns:1fr 1fr;gap:4px;min-height:0;flex:1;overflow:hidden;padding:0 4px" });
      const left = el("div", { class: "wire-scroll" });
      left.appendChild(el("div", { class: "org", style: "font-size:9px;font-weight:800;padding:2px", text: "MEMBERS" }));
      const tp = el("table", { class: "tbl compact" });
      tp.innerHTML = "<thead><tr><th>NAME</th><th>P</th><th>CH</th><th>#</th></tr></thead>";
      const tbp = el("tbody");
      (desk.politicians || []).slice(0, 50).forEach(pol => {
        const tr = el("tr", { "data-click": "1" });
        tr.innerHTML =
          `<td style="text-align:left">${U.esc((pol.name || "").slice(0, 16))}</td>` +
          `<td class="${partyCls(pol.party)}">${U.esc(pol.party || "?")}</td>` +
          `<td class="dim">${U.esc((pol.chamber || "?").slice(0, 1))}</td>` +
          `<td class="num">${pol.trades}</td>`;
        tr.addEventListener("click", () => focusPol(pol.name));
        tbp.appendChild(tr);
      });
      tp.appendChild(tbp);
      left.appendChild(tp);

      const right = el("div", { class: "wire-scroll" });
      right.appendChild(el("div", { class: "org", style: "font-size:9px;font-weight:800;padding:2px", text: "TICKERS" }));
      const tt = el("table", { class: "tbl compact" });
      tt.innerHTML = "<thead><tr><th>TKR</th><th>#</th><th>POLS</th></tr></thead>";
      const tbt = el("tbody");
      (desk.tickers || []).slice(0, 50).forEach(tk => {
        const tr = el("tr", { "data-click": "1" });
        tr.innerHTML =
          `<td class="org" style="font-weight:800">${U.esc(tk.ticker)}</td>` +
          `<td class="num">${tk.trades}</td>` +
          `<td class="num">${tk.unique_politicians || 0}</td>`;
        tr.addEventListener("click", () => focusTicker(tk.ticker));
        tbt.appendChild(tr);
      });
      tt.appendChild(tbt);
      right.appendChild(tt);
      cols.appendChild(left);
      cols.appendChild(right);
      body.appendChild(cols);
    }
  };

  /* ---------- N. POLITICIAN BOOK ---------- */
  W.polbook = {
    num: "14", title: "POLITICIAN BOOK", min: [4, 5],
    render(body) {
      const book = G.datasets.polbook;
      const bar = el("div", { class: "toolbar" });
      if (book && book.name) {
        bar.appendChild(renderAvatar({
          name: book.name,
          party: book.party,
          bioguide_id: book.bioguide_id,
          photo_url: book.photo_url
        }, 48));
        bar.appendChild(el("span", { class: "org", style: "font-weight:800", text: book.name }));
        bar.appendChild(el("span", { class: partyCls(book.party), text: " " + (book.party || "") }));
        bar.appendChild(el("span", { class: "dim", text: " " + (book.chamber || "") + " · " + (book.state_district || "") }));
      } else {
        bar.appendChild(el("span", { class: "dim", text: "click a member in wire / holders" }));
      }
      body.appendChild(bar);

      if (!book) {
        body.appendChild(el("div", { class: "pad dim", text: "> no politician selected" }));
        return;
      }
      body.appendChild(el("div", {
        class: "pad faint", style: "font-size:9px",
        text: `${book.trades_total || 0} trades · ${book.unique_tickers || 0} tickers · dates = trade date (TX)`
      }));

      const scroller = el("div", { class: "wire-scroll" });

      /* per-ticker with last trade date */
      scroller.appendChild(el("div", {
        class: "org", style: "font-size:9px;font-weight:800;padding:2px 2px 2px", text: "ASSETS (last trade)"
      }));
      const tbl = el("table", { class: "tbl compact" });
      tbl.innerHTML = "<thead><tr><th>TKR</th><th>TX DATE</th><th>SIDE</th><th>#</th><th>B/S</th><th>FILED</th></tr></thead>";
      const tb = el("tbody");
      (book.tickers || []).forEach(t => {
        const tr = el("tr", { "data-click": "1", title: "open chart · last trade " + (t.last_trade_date || "—") });
        tr.innerHTML =
          `<td class="org" style="font-weight:800">${U.esc(t.ticker)}</td>` +
          `<td class="num" style="color:var(--ink);font-weight:700">${U.esc(fmtDate(t.last_trade_date, true))}</td>` +
          `<td class="${t.last_side === "BUY" ? "up" : "dn"}">${U.esc(t.last_side || "—")}</td>` +
          `<td class="num dim">${t.trades}</td>` +
          `<td class="num dim">${t.buys || 0}/${t.sells || 0}</td>` +
          `<td class="faint">${U.esc(fmtDate(t.last_filing_date, true))}</td>`;
        tr.addEventListener("click", () => {
          // open asset with this member's last trade date on chart
          focusTicker(t.ticker, t.last_trade_date || t.last_filing_date || null);
        });
        tb.appendChild(tr);
      });
      tbl.appendChild(tb);
      scroller.appendChild(tbl);

      /* full trade list with both dates */
      if (book.recent_trades && book.recent_trades.length) {
        scroller.appendChild(el("div", {
          class: "org", style: "font-size:9px;font-weight:800;padding:8px 2px 2px", text: "ALL TRADES (this member)"
        }));
        const rt = el("table", { class: "tbl compact" });
        rt.innerHTML = "<thead><tr><th>TX DATE</th><th>FILED</th><th>SIDE</th><th>TKR</th><th>AMT</th><th>SCR</th></tr></thead>";
        const rtb = el("tbody");
        book.recent_trades.forEach(t => {
          const tr = el("tr", { "data-click": "1" });
          tr.innerHTML =
            `<td class="num" style="font-weight:700">${U.esc(fmtDate(t.trade_date, true))}</td>` +
            `<td class="faint">${U.esc(fmtDate(t.filing_date, true))}</td>` +
            `<td class="${t.side === "BUY" ? "up" : "dn"}" style="font-weight:800">${U.esc(t.side)}</td>` +
            `<td class="org" style="font-weight:800">${U.esc(t.ticker || "—")}</td>` +
            `<td class="num dim" style="font-size:9px">${U.esc((t.amount || "—").replace(/\$/g, "").slice(0, 12))}</td>` +
            `<td class="num">${t.score != null ? t.score : "—"}</td>`;
          tr.addEventListener("click", () => focusTrade(Object.assign({}, t, { politician: book.name })));
          rtb.appendChild(tr);
        });
        rt.appendChild(rtb);
        scroller.appendChild(rt);
      }
      body.appendChild(scroller);
      body.appendChild(el("div", {
        class: "faint", style: "font-size:8px;padding:2px 8px",
        text: "> TX DATE = trade date · FILED = disclosure date · click row → chart marks that date"
      }));
    }
  };

  /* ---------- P. RETURNS LEADERBOARD ---------- */
  W.returns = {
    num: "16", title: "RETURNS LEADERBOARD · EST.", min: [4, 6],
    render(body) {
      const p = G.state.prefs;
      const data = G.datasets.returns;
      const loading = G.datasets.returnsLoading;
      const err = G.datasets.returnsError;

      const bar = el("div", {
        class: "toolbar",
        style: "display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:4px 8px;background:var(--bg2);border-bottom:1px solid var(--line2)"
      });

      // View mode: Members (grouped) vs Trades (individual)
      const segView = el("div", { class: "seg", style: "display:inline-flex;align-items:center;border:1px solid var(--line2);border-radius:2px;padding:1px;background:#050505" });
      segView.appendChild(el("span", { class: "faint", style: "font-size:9px;font-weight:800;padding:2px 5px;color:var(--org)", text: "VIEW:" }));
      [["MEMBERS", "member", "Rank by Congress Member (consolidated)"], ["TRADES", "trade", "Rank individual transactions"]].forEach(([lab, v, title]) => {
        const on = (p.returnsMode || "member") === v;
        segView.appendChild(el("button", {
          class: on ? "on" : "",
          style: (on ? "background:var(--org);color:#000;font-weight:800;" : "") + "font-size:9px;padding:2px 6px",
          text: lab,
          title: title,
          onclick: () => { p.returnsMode = v; G.app.savePrefs(); G.app.loadReturns(); }
        }));
      });
      bar.appendChild(segView);

      // Side: ALL vs BUY vs SELL
      const segSide = el("div", { class: "seg", style: "display:inline-flex;align-items:center;border:1px solid var(--line2);border-radius:2px;padding:1px;background:#050505" });
      segSide.appendChild(el("span", { class: "faint", style: "font-size:9px;font-weight:800;padding:2px 5px;color:var(--org)", text: "SIDE:" }));
      [["ALL", "ALL", "All Sides"], ["▲ BUY", "BUY", "Buys only"], ["▼ SELL", "SELL", "Sells only"]].forEach(([lab, v, title]) => {
        const on = (p.returnsSide || "ALL") === v;
        const col = on
          ? (v === "BUY" ? "background:#00C176;color:#000;font-weight:800;" : (v === "SELL" ? "background:#FF4D4F;color:#000;font-weight:800;" : "background:var(--org);color:#000;font-weight:800;"))
          : (v === "BUY" ? "color:#00C176;" : (v === "SELL" ? "color:#FF4D4F;" : ""));
        segSide.appendChild(el("button", {
          class: on ? "on" : "",
          style: col + "font-size:9px;padding:2px 6px",
          text: lab,
          title: title,
          onclick: () => { p.returnsSide = v; G.app.savePrefs(); G.app.loadReturns(); }
        }));
      });
      bar.appendChild(segSide);

      bar.appendChild(el("button", {
        text: "↻", title: "Reload returns (yfinance)",
        style: "margin-left:auto;font-size:11px;padding:1px 6px",
        onclick: () => G.app.loadReturns()
      }));
      bar.appendChild(el("button", {
        text: "🏛️ CONGRESS DESK",
        title: "Voltar para Mesa Principal do Congresso",
        style: "font-size:10px;padding:2px 8px;font-weight:700;background:#121212;border:1px solid #3A3A3A;color:var(--org);cursor:pointer",
        onclick: () => {
          G.layout.applyPreset("CONGRESS");
          G.app.syncPresetButtons();
        }
      }));
      body.appendChild(bar);

      // Month selection ribbon for returns leaderboard
      const mb = el("div", { class: "month-browser", style: "border-bottom:1px solid var(--line2);padding:4px 6px;background:#050505" });
      const chips = el("div", { class: "month-chips" });
      const allChip = el("button", {
        class: "mchip" + (!p.wireMonth ? " on" : ""),
        text: "✦ ALL MONTHS",
        onclick: () => { p.wireMonth = null; G.app.savePrefs(); G.app.loadReturns(); }
      });
      chips.appendChild(allChip);
      const months = G.datasets.congressMonths || [];
      months.slice(0, 10).forEach(m => {
        const on = p.wireMonth === m.month;
        const btn = el("button", {
          class: "mchip" + (on ? " on" : ""),
          text: m.month + (m.count ? ` ·${m.count}` : ""),
          onclick: () => { p.wireMonth = m.month; G.app.savePrefs(); G.app.loadReturns(); }
        });
        chips.appendChild(btn);
      });
      mb.appendChild(chips);
      body.appendChild(mb);

      const monthLab = p.wireMonth || "ALL MONTHS";
      body.appendChild(el("div", {
        class: "pad faint", style: "font-size:9px;padding:3px 8px",
        text: monthLab + " · side-adj % = BUY:+Δ / SELL:−Δ · $ PnL from range mid (est.) · click member/trade to focus chart"
      }));

      if (loading) {
        body.appendChild(el("div", { class: "pad dim", text: "> pricing trades via yfinance… (cached)" }));
        return;
      }
      if (err) {
        body.appendChild(el("div", { class: "pad", style: "color:var(--dn)", text: "> " + err }));
        return;
      }
      if (!data || !data.rows || !data.rows.length) {
        body.appendChild(el("div", { class: "pad dim", text: "> no priced returns for this filter" }));
        return;
      }

      body.appendChild(el("div", {
        class: "pad", style: "font-size:9px;padding:2px 8px",
        text: `scored ${data.scored} · skip ${data.skipped || 0} · tickers ${data.tickers_priced || "—"} · ${data.mode}`
      }));

      const scroller = el("div", { class: "wire-scroll" });
      const mode = data.mode || "trade";

      if (mode === "member") {
        data.rows.forEach((r, i) => {
          const card = el("div", { class: "member-card", style: "margin:4px 6px;border:1px solid var(--line2);background:#080808" });
          const head = el("div", { class: "member-card-head", style: "display:flex;align-items:center;gap:8px;padding:6px 8px;cursor:pointer" });
          const chev = el("span", { class: "chev", text: "▶", style: "color:var(--org);font-weight:800;width:12px;font-size:10px" });
          head.appendChild(chev);
          head.appendChild(el("span", {
            class: "rank num", style: "width:16px;font-weight:800;color:var(--org);font-size:11px",
            text: String(i + 1)
          }));
          head.appendChild(renderAvatar({
            name: r.politician, party: r.party,
            bioguide_id: r.bioguide_id, photo_url: r.photo_url
          }, 32));
          const meta = el("div", { class: "holder-meta", style: "flex:1;min-width:0" });
          const avg = r.avg_return_adj;
          meta.innerHTML =
            `<div><span class="name" style="font-weight:800;color:var(--ink)">${U.esc(r.politician || "")}</span> ` +
            `<span class="${partyCls(r.party)}">${U.esc(r.party || "?")}</span> ` +
            `<span class="num ${avg >= 0 ? "up" : "dn"}" style="font-weight:800">${avg >= 0 ? "+" : ""}${avg}%</span>` +
            ` <span class="faint" style="font-size:9px">avg adj</span></div>` +
            `<div class="faint" style="font-size:9px">${r.trades} tx · ${r.unique_tickers} tkrs` +
            (r.sum_pnl_mid_est != null ? ` · PnL $${U.fmtNum(r.sum_pnl_mid_est, 0)}` : "") +
            (r.best_trade ? ` · best ${U.esc(r.best_trade.ticker)} ${r.best_trade.return_side_adj}%` : "") +
            `</div>`;
          head.appendChild(meta);
          card.appendChild(head);

          const cardBody = el("div", { class: "member-card-body", style: "display:none;border-top:1px solid var(--line);background:#050505;padding:4px" });
          const tradesList = r.trades_list || [];
          if (tradesList.length > 0) {
            const tbl = el("table", { class: "tbl compact" });
            tbl.innerHTML = "<thead><tr><th>TX DATE</th><th>SIDE</th><th>TKR</th><th>PRICE</th><th>NOW</th><th>Δ%</th><th>ADJ%</th><th>PnL$</th></tr></thead>";
            const tb = el("tbody");
            tradesList.forEach(t => {
              const tr = el("tr", { "data-click": "1", tabindex: "0", style: "cursor:pointer" });
              const chg = t.change_pct;
              const adj = t.return_side_adj;
              tr.appendChild(el("td", { class: "faint", text: fmtDate(t.trade_date, true) }));
              tr.appendChild(el("td", { class: t.side === "BUY" ? "up" : "dn", style: "font-weight:800", text: t.side || "?" }));
              tr.appendChild(el("td", { class: "org", style: "font-weight:800", text: t.ticker || "—" }));
              tr.appendChild(el("td", { class: "num dim", text: t.price_at_trade != null ? "$" + U.fmtNum(t.price_at_trade, 2) : "—" }));
              tr.appendChild(el("td", { class: "num dim", text: t.price_now != null ? "$" + U.fmtNum(t.price_now, 2) : "—" }));
              tr.appendChild(el("td", { class: "num " + (chg >= 0 ? "up" : "dn"), text: (chg >= 0 ? "+" : "") + (chg != null ? chg : "—") }));
              tr.appendChild(el("td", { class: "num " + (adj >= 0 ? "up" : "dn"), style: "font-weight:800", text: (adj >= 0 ? "+" : "") + (adj != null ? adj : "—") }));
              tr.appendChild(el("td", { class: "num dim", text: t.pnl_mid_est != null ? "$" + U.fmtNum(t.pnl_mid_est, 0) : "—" }));

              tr.addEventListener("click", e => {
                e.stopPropagation();
                focusTrade({
                  id: t.id,
                  ticker: t.ticker,
                  politician: r.politician,
                  party: r.party,
                  chamber: r.chamber,
                  side: t.side,
                  trade_date: t.trade_date,
                  filing_date: t.filing_date,
                  amount: t.amount,
                  score: t.score,
                  price: t.price_at_trade,
                  trade_price: t.price_at_trade,
                  price_change_pct: t.change_pct,
                  pnl_mid_est: t.pnl_mid_est,
                  bioguide_id: r.bioguide_id,
                  photo_url: r.photo_url
                });
              });
              tb.appendChild(tr);
            });
            tbl.appendChild(tb);
            cardBody.appendChild(tbl);
          } else {
            cardBody.appendChild(el("div", { class: "pad faint", style: "font-size:9px", text: "No individual trade details available" }));
          }
          card.appendChild(cardBody);

          head.addEventListener("click", () => {
            const isOpen = cardBody.style.display !== "none";
            cardBody.style.display = isOpen ? "none" : "block";
            chev.textContent = isOpen ? "▶" : "▼";
            focusPol(r.politician);
            if (!isOpen && tradesList.length > 0) {
              const firstTrade = tradesList[0];
              focusTrade({
                id: firstTrade.id,
                ticker: firstTrade.ticker,
                politician: r.politician,
                party: r.party,
                chamber: r.chamber,
                side: firstTrade.side,
                trade_date: firstTrade.trade_date,
                filing_date: firstTrade.filing_date,
                amount: firstTrade.amount,
                score: firstTrade.score,
                price: firstTrade.price_at_trade,
                trade_price: firstTrade.price_at_trade,
                bioguide_id: r.bioguide_id,
                photo_url: r.photo_url
              });
            }
          });

          scroller.appendChild(card);
        });
      } else {
        const tbl = el("table", { class: "tbl compact" });
        tbl.innerHTML = "<thead><tr><th>#</th><th></th><th>MEMBER</th><th>SIDE</th><th>TKR</th><th>TX</th><th>PRICE</th><th>NOW</th><th>Δ%</th><th>ADJ%</th><th>PnL$</th></tr></thead>";
        const tb = el("tbody");
        data.rows.forEach((r, i) => {
          const tr = el("tr", { "data-click": "1", tabindex: "0", style: "cursor:pointer" });
          const chg = r.change_pct;
          const adj = r.return_side_adj;
          tr.appendChild(el("td", { class: "num org", style: "font-weight:800", text: String(i + 1) }));
          const tdAv = el("td");
          tdAv.appendChild(renderAvatar({
            name: r.politician, party: r.party,
            bioguide_id: r.bioguide_id, photo_url: r.photo_url
          }, 22));
          tr.appendChild(tdAv);
          tr.appendChild(el("td", { style: "text-align:left", text: (r.politician || "—").slice(0, 14) }));
          tr.appendChild(el("td", {
            class: r.side === "BUY" ? "up" : "dn", style: "font-weight:800", text: r.side || "?"
          }));
          tr.appendChild(el("td", { class: "org", style: "font-weight:800", text: r.ticker || "—" }));
          tr.appendChild(el("td", { class: "faint", text: fmtDate(r.trade_date, true) }));
          tr.appendChild(el("td", { class: "num dim", text: r.price_at_trade != null ? "$" + U.fmtNum(r.price_at_trade, 2) : "—" }));
          tr.appendChild(el("td", { class: "num dim", text: r.price_now != null ? "$" + U.fmtNum(r.price_now, 2) : "—" }));
          tr.appendChild(el("td", {
            class: "num " + (chg >= 0 ? "up" : "dn"),
            text: (chg >= 0 ? "+" : "") + (chg != null ? chg : "—")
          }));
          tr.appendChild(el("td", {
            class: "num " + (adj >= 0 ? "up" : "dn"), style: "font-weight:800",
            text: (adj >= 0 ? "+" : "") + (adj != null ? adj : "—")
          }));
          tr.appendChild(el("td", {
            class: "num dim",
            text: r.pnl_mid_est != null ? "$" + U.fmtNum(r.pnl_mid_est, 0) : "—"
          }));
          tr.addEventListener("click", () => {
            focusTrade({
              id: r.id,
              ticker: r.ticker,
              politician: r.politician,
              party: r.party,
              chamber: r.chamber,
              side: r.side,
              trade_date: r.trade_date,
              filing_date: r.filing_date,
              amount: r.amount,
              score: r.score,
              price: r.price_at_trade,
              trade_price: r.price_at_trade,
              price_change_pct: r.change_pct,
              shares_est: r.shares_est,
              pnl_mid_est: r.pnl_mid_est,
              bioguide_id: r.bioguide_id,
              photo_url: r.photo_url
            });
          });
          tb.appendChild(tr);
        });
        tbl.appendChild(tb);
        scroller.appendChild(tbl);
      }
      body.appendChild(scroller);
      body.appendChild(el("div", {
        class: "faint", style: "font-size:8px;padding:2px 8px",
        text: "> ESTIMATED · click row → chart+holders · ADJ% = outcome for that side · not actual account PnL"
      }));
    }
  };

  /* ---------- O. FOCUSED ASSET CHART (candles default) ---------- */
  W.focuschart = {
    num: "15", title: "FOCUSED ASSET · DAILY CANDLES", min: [5, 6],
    render(body) {
      const p = G.state.prefs;
      const tk = p.focusTicker || "—";
      const chart = G.datasets.focusChart;
      const prov = G.prov.focusChart;
      // default candle mode
      if (!p.chartStyle) p.chartStyle = "candle";

      const bar = el("div", { class: "toolbar" });
      bar.appendChild(el("span", { class: "org", style: "font-weight:800;font-size:13px", text: tk }));
      if (p.focusPolitician) {
        bar.appendChild(el("span", { class: "dim", style: "font-size:10px", text: p.focusPolitician.slice(0, 22) }));
      }
      if (p.focusTradeDate) {
        bar.appendChild(el("span", {
          class: "chip",
          style: "background:var(--org);color:#000;font-weight:800",
          text: "TX " + p.focusTradeDate
        }));
      } else {
        bar.appendChild(el("span", { class: "faint", style: "font-size:9px", text: "no trade date" }));
      }
      // style toggle
      bar.appendChild(btn("CANDLE", p.chartStyle === "candle", () => {
        p.chartStyle = "candle"; G.app.savePrefs(); G.app.rerender("focuschart");
      }));
      bar.appendChild(btn("LINE", p.chartStyle === "line", () => {
        p.chartStyle = "line"; G.app.savePrefs(); G.app.rerender("focuschart");
      }));
      if (prov && prov.mode) bar.appendChild(el("span", { class: "chip " + (prov.mode === "LIVE" ? "live" : "demo"), text: prov.mode }));
      body.appendChild(bar);

      const s = (chart && chart.series) || [];
      if (s.length < 2) {
        body.appendChild(el("div", { class: "pad dim", text: "> chart loading for " + tk + "…" }));
        return;
      }
      const last = s[s.length - 1], prev = s[s.length - 2];
      const chg = +(last.c - prev.c).toFixed(2);
      const chgPct = +(chg / prev.c * 100).toFixed(2);
      const styleLabel = p.chartStyle === "line" ? "LINE" : "CANDLE";
      const markDate = p.focusTradeDate;
      let tradeBar = null;
      if (markDate && s.length) {
        tradeBar = s.find(b => b.d === markDate) || s.find(b => b.d >= markDate);
      }
      const tradeType = p.focusTradeType || "BUY";
      const tradePrice = p.focusTradePrice != null ? p.focusTradePrice : (tradeBar ? tradeBar.c : null);

      let tradeChip = '';
      if (tradePrice != null && markDate) {
        const isBuy = tradeType === "BUY";
        const col = isBuy ? "#00C176" : "#FF4D4F";
        const bg = isBuy ? "rgba(0,193,118,0.15)" : "rgba(255,77,79,0.15)";
        const icon = isBuy ? "▲" : "▼";
        tradeChip = `<span class="chip" style="background:${bg};color:${col};border:1px solid ${col};font-weight:800;font-size:9px">${icon} ${tradeType} $${U.fmtNum(tradePrice, 2)} (${fmtDate(markDate)})</span>`;
      }

      const hi = el("div", { class: "toolbar", style: "gap:8px;flex-wrap:wrap" });
      hi.innerHTML =
        `<span class="num" style="font-weight:800;font-size:14px">${U.fmtNum(last.c, 2)}</span>` +
        `<span class="num ${U.cls(chg)}">${U.arrow(chg)} ${U.fmtChg(chg, 2)} (${U.fmtPct(chgPct)})</span>` +
        tradeChip +
        `<span class="dim">O ${U.fmtNum(last.o, 2)}</span>` +
        `<span class="dim">H ${U.fmtNum(last.h, 2)}</span>` +
        `<span class="dim">L ${U.fmtNum(last.l, 2)}</span>` +
        `<span class="dim">V ${U.fmtVol(last.v)}</span>` +
        `<span class="chip" style="font-size:9px">${styleLabel} · DAILY · ${s.length}</span>`;
      body.appendChild(hi);

      const box = el("div", { class: "chart-box", "aria-label": tk + " " + styleLabel + " chart" });
      body.appendChild(box);
      requestAnimationFrame(() => {
        const draw = p.chartStyle === "line" ? G.charts.lineVolume : G.charts.candlestickVolume;
        draw(box, {
          series: s, dp: 2, color: "#00C176",
          markDate: markDate,
          tradePrice: tradePrice,
          tradeType: tradeType,
          aria: tk + " daily " + styleLabel.toLowerCase(),
          onPick: (i, pt) => pt && G.inspector.open("session", { sym: tk, bar: pt, index: i, total: s.length })
        });
      });
      body.appendChild(el("div", {
        class: "faint", style: "font-size:8px;padding:2px 8px",
        html: `> ${U.esc(s[0].d)} → ${U.esc(s[s.length - 1].d)} · daily OHLC · ` +
          (markDate
            ? `<span class="org">TX marker ${U.esc(markDate)}</span>`
            : "pick a trade to mark TX on scale") +
          " · green=up / red=down candles · amber volume"
      }));
    }
  };

  G.widgets.focusTrade = focusTrade;
  G.widgets.focusPol = focusPol;
  G.widgets.focusTicker = focusTicker;
})(window.GMT);
