/* GMT Inspector (widget J): provenance for every datum. Hover previews, click pins.
   Close via ✕, Escape; focus returns to the invoking element. Bottom sheet on mobile. */
window.GMT = window.GMT || {};
(function (G) {
  "use strict";
  const U = G.util, el = U.el;
  let lastFocus = null;

  function kv(k, v) {
    return el("div", { class: "kv" }, [el("div", { class: "k", text: k }), el("div", { class: "v num", text: v == null ? "—" : String(v) })]);
  }
  function head(t, sub) {
    return el("div", { style: "margin-bottom:6px" }, [
      el("div", { style: "font-weight:800;color:var(--org);font-size:13px", text: t }),
      sub ? el("div", { class: "dim", style: "font-size:10px", text: sub }) : null
    ]);
  }
  function provBlock(prov) {
    const d = el("div", { style: "margin-top:8px;border-top:1px solid var(--line2);padding-top:6px" });
    d.appendChild(el("div", { class: "org", style: "font-size:9px;font-weight:800;letter-spacing:1px", text: "PROVENANCE" }));
    d.appendChild(kv("adapter", prov.adapter));
    d.appendChild(kv("source", prov.source));
    d.appendChild(kv("mode", prov.mode));
    d.appendChild(kv("as-of", prov.asof));
    d.appendChild(kv("latency", prov.latencyMs != null ? prov.latencyMs + " ms" : "—"));
    d.appendChild(kv("error", prov.error || "none"));
    d.appendChild(kv("fallback", prov.fallback || "none"));
    if (prov.convention) d.appendChild(kv("convention", prov.convention));
    return d;
  }
  function fieldsBlock(obj) {
    const d = el("div", { style: "margin-top:6px" });
    d.appendChild(el("div", { class: "org", style: "font-size:9px;font-weight:800;letter-spacing:1px", text: "AVAILABLE FIELDS" }));
    d.appendChild(el("div", { class: "dim", style: "font-size:10px;word-break:break-word", text: Object.keys(obj).join(", ") }));
    return d;
  }

  const BUILDERS = {
    stock(s) {
      const prov = G.prov.stocks;
      const d = el("div");
      d.appendChild(head(s.t + " — " + s.name, s.sector + " · " + s.sub));
      d.appendChild(kv("last", U.fmtNum(s.last, 2) + " USD"));
      d.appendChild(kv("change", U.fmtChg(s.chg, 2) + " (" + U.fmtPct(s.chgPct) + ") " + U.arrow(s.chgPct)));
      d.appendChild(kv("open", U.fmtNum(s.open, 2)));
      d.appendChild(kv("prev close", U.fmtNum(s.prevClose, 2)));
      d.appendChild(kv("high", U.fmtNum(s.high, 2)));
      d.appendChild(kv("low", U.fmtNum(s.low, 2)));
      d.appendChild(kv("volume", s.volume.toLocaleString("en-US") + " sh"));
      d.appendChild(kv("market cap", "$" + U.fmtBig(s.mktCap)));
      d.appendChild(kv("turnover", "$" + U.fmtVol(s.last * s.volume)));
      d.appendChild(kv("currency", "USD"));
      d.appendChild(provBlock(prov));
      d.appendChild(fieldsBlock(s));
      return d;
    },
    instrument(r) {
      const d = el("div");
      d.appendChild(head(r.sym + " — " + r.name, r.kind + " · " + r.region));
      d.appendChild(kv("last", U.fmtNum(r.last, 2) + " " + r.ccy));
      d.appendChild(kv("change", U.fmtChg(r.chg, 2) + " (" + U.fmtPct(r.chgPct) + ") " + U.arrow(r.chgPct)));
      d.appendChild(kv("prev close", U.fmtNum(r.prevClose, 2)));
      d.appendChild(kv("market state", r.state));
      d.appendChild(kv("venue tz", r.tz));
      d.appendChild(kv("source", r.src));
      d.appendChild(provBlock(G.prov.tape));
      d.appendChild(fieldsBlock(r));
      return d;
    },
    metal(m) {
      const d = el("div");
      d.appendChild(head(m.sym + " — " + m.name, "spot · " + m.unit));
      d.appendChild(kv("last", U.fmtNum(m.last, m.sym === "XAG" ? 3 : 2) + " " + m.unit));
      d.appendChild(kv("change", U.fmtChg(m.chg, 3) + " (" + U.fmtPct(m.chgPct) + ") " + U.arrow(m.chgPct)));
      d.appendChild(kv("prev close", U.fmtNum(m.prevClose, 3)));
      const lo = Math.min.apply(null, m.series.map(x => x.l)), hi = Math.max.apply(null, m.series.map(x => x.h));
      d.appendChild(kv("60d range", U.fmtNum(lo, 2) + " – " + U.fmtNum(hi, 2) + " " + m.unit));
      d.appendChild(kv("definition", "spot, USD/t oz, single demo desk — homogeneous across XAU/XAG/XPT/XPD"));
      d.appendChild(provBlock(G.prov.metals));
      d.appendChild(fieldsBlock({ sym: 0, name: 0, unit: 0, ccy: 0, last: 0, chg: 0, chgPct: 0, prevClose: 0, asof: 0, series: "[60 bars]" }));
      return d;
    },
    news(n) {
      const d = el("div");
      d.appendChild(head(n.headline, "[" + n.cat + "] · " + n.source + " · " + n.time.replace("T", " ")));
      d.appendChild(el("div", { class: "chip demo", text: "DEMO HEADLINE — illustrative fixture, not a real report" }));
      d.appendChild(el("p", { style: "margin:6px 0;font-size:11px", text: n.summary }));
      d.appendChild(kv("published", n.time + " (ET)"));
      d.appendChild(kv("affected tickers", n.tickers.join(", ") || "—"));
      d.appendChild(kv("linked move", n.linkedMove));
      d.appendChild(kv("original link", n.link + " (internal demo reference — no external URL in DEMO mode)"));
      d.appendChild(provBlock(G.prov.news));
      return d;
    },
    session(x) {
      const d = el("div");
      d.appendChild(head(x.sym + " · session " + x.bar.d, "bar " + (x.index + 1) + " of " + x.total));
      if (x.bar.o != null) {
        d.appendChild(kv("open", U.fmtNum(x.bar.o, 2)));
        d.appendChild(kv("high", U.fmtNum(x.bar.h, 2)));
        d.appendChild(kv("low", U.fmtNum(x.bar.l, 2)));
      }
      d.appendChild(kv("close", U.fmtNum(x.bar.c, 2) + (x.unit ? " " + x.unit : " USD")));
      if (x.bar.v) d.appendChild(kv("volume", x.bar.v.toLocaleString("en-US") + " sh"));
      d.appendChild(kv("convention", "valid weekday session; no weekend/holiday filling; DEMO unadjusted"));
      d.appendChild(provBlock(x.sym === "AAPL" ? G.prov.aapl60 : G.prov.metals));
      return d;
    },
    market(x) {
      const m = x.mkt, st = x.st;
      const d = el("div");
      d.appendChild(head(m.name, m.id + " · " + m.tz));
      d.appendChild(kv("state", st.state));
      d.appendChild(kv("local date", `${st.date.y}-${String(st.date.mo).padStart(2, "0")}-${String(st.date.d).padStart(2, "0")}`));
      d.appendChild(kv("regular session", G.sessions.sessionHoursLabel(m) + " local"));
      if (m.pre) d.appendChild(kv("pre-market", "04:00–09:30 local"));
      if (m.lunch) d.appendChild(kv("lunch break", "yes (see session)"));
      d.appendChild(kv("next transition", st.nextVerb + (st.nextState ? " → " + st.nextState : "")));
      d.appendChild(kv("countdown", G.sessions.fmtCountdown(st.countdownMs)));
      d.appendChild(kv("holiday status", "UNVERIFIED — no holiday calendar bundled; holidays never reported as open"));
      d.appendChild(kv("dst handling", "IANA tz via Intl (" + m.tz + ") — offset resolves per instant"));
      d.appendChild(provBlock({ adapter: "session engine (live clock)", source: "client Intl/IANA tz database", mode: "LIVE (time-of-day only)", asof: x.now, latencyMs: 0, error: null, fallback: null }));
      return d;
    },
    breadth(b) {
      const d = el("div");
      d.appendChild(head("MARKET BREADTH", "computed from currently filtered universe"));
      d.appendChild(kv("sample size n", b.n));
      d.appendChild(kv("advancers", b.adv));
      d.appendChild(kv("decliners", b.dec));
      d.appendChild(kv("unchanged", b.unch));
      d.appendChild(kv("A/D ratio", b.dec ? (b.adv / b.dec).toFixed(3) : "∞"));
      d.appendChild(kv("universe", "heatmap filter = " + G.state.prefs.heatFilter + (G.state.prefs.heatQuery ? " · q=" + G.state.prefs.heatQuery : "")));
      d.appendChild(kv("note", "sample breadth, NOT whole-market breadth"));
      d.appendChild(provBlock(G.prov.stocks));
      return d;
    },
    trade(t) {
      const d = el("div");
      d.appendChild(head(
        (t.side || "?") + " " + (t.ticker || "—"),
        (t.politician || "") + " · " + (t.chamber || "") + " · " + (t.party || "")
      ));
      if (t.demo) d.appendChild(el("div", { class: "chip demo", text: "DEMO DISCLOSURE — fixture, not a real PTR" }));
      d.appendChild(kv("politician", t.politician));
      d.appendChild(kv("chamber / party", (t.chamber || "—") + " / " + (t.party || "—")));
      d.appendChild(kv("state", t.state_district));
      d.appendChild(kv("ticker", t.ticker));
      d.appendChild(kv("asset", t.asset));
      d.appendChild(kv("side", t.side));
      d.appendChild(kv("TRADE DATE (TX)", t.trade_date || "—"));
      d.appendChild(kv("FILING DATE", t.filing_date || "—"));
      d.appendChild(kv("amount range", t.amount || ((t.amount_min || "") + "–" + (t.amount_max || ""))));
      d.appendChild(kv("score / tag", (t.score != null ? t.score : "—") + " / " + (t.tag || "—")));
      d.appendChild(kv("sector", t.sector));
      d.appendChild(kv("Δ% since trade (est)", t.price_change_pct != null ? U.fmtPct(t.price_change_pct) : "—"));
      d.appendChild(kv("shares est", t.shares_est != null ? t.shares_est : "—"));
      d.appendChild(kv("note", "TX = when the trade happened. FILED = when disclosed. Chart marker uses TX date."));
      if (t.pdf_url) d.appendChild(kv("source pdf", t.pdf_url));
      d.appendChild(provBlock(G.prov.cwire || { adapter: "congress", source: "sqlite", mode: "LIVE", asof: t.filing_date || t.trade_date }));
      d.appendChild(fieldsBlock(t));
      return d;
    },
    politician(p) {
      const d = el("div");
      const book = G.datasets.polbook;
      const name = p.name || (book && book.name);
      d.appendChild(head(name || "Politician", (book && book.chamber) || ""));
      if (book && book.name === name) {
        d.appendChild(kv("party", book.party));
        d.appendChild(kv("chamber", book.chamber));
        d.appendChild(kv("state", book.state_district));
        d.appendChild(kv("trades", book.trades_total));
        d.appendChild(kv("unique tickers", book.unique_tickers));
        const tops = (book.tickers || []).slice(0, 8).map(x =>
          x.ticker + (x.last_trade_date ? " @" + x.last_trade_date : "")
        );
        d.appendChild(kv("top tickers + last TX", tops.join(", ") || "—"));
        const recent = (book.recent_trades || []).slice(0, 5);
        if (recent.length) {
          d.appendChild(el("div", { class: "org", style: "font-size:9px;font-weight:800;margin-top:6px", text: "RECENT TRADES" }));
          recent.forEach(t => {
            d.appendChild(kv(
              (t.trade_date || "?") + " " + (t.side || ""),
              (t.ticker || "—") + " · filed " + (t.filing_date || "—")
            ));
          });
        }
      } else {
        d.appendChild(kv("name", name));
        d.appendChild(el("div", { class: "dim", text: "book loading or partial payload" }));
      }
      d.appendChild(provBlock(G.prov.polbook || { adapter: "congress", mode: "LIVE", source: "sqlite" }));
      return d;
    }
  };

  G.inspector = {
    open(type, payload) {
      const ins = U.$("#inspector");
      const body = U.$("#ins-body");
      lastFocus = document.activeElement && document.activeElement !== document.body ? document.activeElement : lastFocus;
      body.innerHTML = "";
      const b = BUILDERS[type];
      body.appendChild(b ? b(payload) : el("div", { text: "no inspector for " + type }));
      U.$("#ins-type").textContent = "INSPECTOR · " + type.toUpperCase();
      ins.classList.add("open");
      ins.setAttribute("aria-hidden", "false");
      U.$("#ins-close").focus();
    },
    close() {
      const ins = U.$("#inspector");
      ins.classList.remove("open");
      ins.setAttribute("aria-hidden", "true");
      if (lastFocus && document.contains(lastFocus)) { try { lastFocus.focus(); } catch (e) {} }
    },
    isOpen() { return U.$("#inspector").classList.contains("open"); }
  };
})(window.GMT);
