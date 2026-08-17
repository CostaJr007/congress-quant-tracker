/* CI://TERMINAL data architecture:
   1) LIVE MARKET  — yfinance via /api/terminal/dataset
   2) LIVE CONGRESS — SQLite disclosures via /api/terminal/congress/*
   3) DEMO adapters — bundled fixtures (market + congress)
   Independent fallback: market can be LIVE while congress is DEMO and vice-versa. */
window.GMT = window.GMT || {};
(function (G) {
  "use strict";
  const U = G.util;

  const status = {
    demo: {
      name: "DEMO MARKET ADAPTER", state: "OK", lastSuccess: null, latencyMs: 0, error: null, fallback: null,
      note: "bundled fixtures v" + (G.GMT_FIXTURES ? G.GMT_FIXTURES.meta.fixturesVersion : "?")
    },
    live: {
      name: "LIVE MARKET (yfinance)", state: "UNCONFIGURED", lastSuccess: null, latencyMs: null, error: null,
      fallback: "no live.config.js — DEMO primary", note: "see live.config.js"
    },
    congressDemo: {
      name: "DEMO CONGRESS ADAPTER", state: "OK", lastSuccess: null, latencyMs: 0, error: null, fallback: null,
      note: "fixtures-congress.js"
    },
    congressLive: {
      name: "LIVE CONGRESS (sqlite)", state: "UNCONFIGURED", lastSuccess: null, latencyMs: null, error: null,
      fallback: "no API — DEMO congress", note: "/api/terminal/congress/*"
    }
  };
  const listeners = [];
  function emit() { listeners.forEach(f => { try { f(); } catch (e) {} }); }

  function liveCfg() {
    return (typeof window.GMT_LIVE_CONFIG === "object" && window.GMT_LIVE_CONFIG) || null;
  }
  function canHttp() {
    return location.protocol !== "file:";
  }

  const DemoAdapter = {
    id: "demo",
    get(dataset) {
      const t0 = performance.now();
      const F = G.GMT_FIXTURES;
      const map = {
        tape: F.tape, stocks: F.stocks, aapl60: F.aapl60,
        metals: F.metals, sectors: F.sectors, news: F.news, meta: [F.meta]
      };
      if (!map[dataset]) throw new Error("unknown dataset " + dataset);
      const asof = dataset === "metals" ? F.meta.metalsAsOf : F.meta.demoAsOf;
      status.demo.state = "OK";
      status.demo.lastSuccess = U.nowIso();
      status.demo.latencyMs = Math.round(performance.now() - t0);
      return {
        data: map[dataset],
        prov: {
          adapter: "demo", source: "bundled market fixtures v" + F.meta.fixturesVersion,
          asof: asof, mode: "DEMO", latencyMs: status.demo.latencyMs, error: null,
          fallback: null, convention: F.meta.convention
        }
      };
    }
  };

  const LiveAdapter = {
    id: "live",
    available() {
      const c = liveCfg();
      if (!canHttp()) {
        status.live.state = "DISABLED";
        status.live.fallback = "file:// — DEMO market";
        return false;
      }
      if (!c || !c.endpoints || !c.endpoints.quotes) {
        status.live.state = "UNCONFIGURED";
        status.live.fallback = "no endpoints — DEMO market";
        return false;
      }
      return true;
    },
    get(dataset) {
      const c = liveCfg();
      const url = c && c.endpoints ? c.endpoints[dataset] || c.endpoints.quotes : null;
      if (!url) return Promise.reject(new Error("no endpoint for " + dataset));
      const t0 = performance.now();
      const sep = url.indexOf("?") >= 0 ? "&" : "?";
      return U.fetchJson(url + sep + "dataset=" + encodeURIComponent(dataset), (c && c.timeoutMs) || 12000)
        .then(j => {
          status.live.state = "OK";
          status.live.lastSuccess = U.nowIso();
          status.live.latencyMs = Math.round(performance.now() - t0);
          status.live.error = null; status.live.fallback = null; emit();
          return {
            data: j.data,
            prov: {
              adapter: "live", source: (c && c.sourceName) || "yfinance",
              asof: j.asof || U.nowIso(), mode: "LIVE",
              latencyMs: status.live.latencyMs, error: null, fallback: null,
              convention: j.convention || "live yfinance"
            }
          };
        })
        .catch(err => {
          status.live.state = "ERROR";
          status.live.error = String(err && err.message || err);
          status.live.fallback = "live market failed → DEMO";
          status.live.latencyMs = Math.round(performance.now() - t0);
          emit();
          throw err;
        });
    }
  };

  /* ---------- Congress ---------- */
  const CongressDemo = {
    wire() {
      const F = G.GMT_CONGRESS_FIXTURES;
      return {
        data: F.wire.slice(),
        prov: { adapter: "congress-demo", source: "fixtures-congress", asof: F.meta.demoAsOf, mode: "DEMO", convention: F.meta.convention }
      };
    },
    summary() {
      const F = G.GMT_CONGRESS_FIXTURES;
      return {
        data: F.summary,
        prov: { adapter: "congress-demo", source: "fixtures-congress", asof: F.meta.demoAsOf, mode: "DEMO" }
      };
    },
    holders(ticker) {
      const F = G.GMT_CONGRESS_FIXTURES;
      const t = (ticker || "NVDA").toUpperCase();
      const h = F.holders[t] || F.holders.NVDA;
      return {
        data: h,
        prov: { adapter: "congress-demo", source: "fixtures-congress", asof: F.meta.demoAsOf, mode: "DEMO" }
      };
    },
    sectors() {
      const F = G.GMT_CONGRESS_FIXTURES;
      return {
        data: F.sectors,
        prov: { adapter: "congress-demo", source: "fixtures-congress", asof: F.meta.demoAsOf, mode: "DEMO" }
      };
    },
    sector(sector) {
      const F = G.GMT_CONGRESS_FIXTURES;
      const s = sector || "Technology";
      const d = F.sectorDesk[s] || F.sectorDesk.Technology;
      return {
        data: d,
        prov: { adapter: "congress-demo", source: "fixtures-congress", asof: F.meta.demoAsOf, mode: "DEMO" }
      };
    },
    politician(name) {
      const F = G.GMT_CONGRESS_FIXTURES;
      const n = name || "Demo House A";
      let d = F.politicians[n];
      if (!d) {
        const keys = Object.keys(F.politicians);
        d = F.politicians[keys[0]];
      }
      return {
        data: d,
        prov: { adapter: "congress-demo", source: "fixtures-congress", asof: F.meta.demoAsOf, mode: "DEMO" }
      };
    },
    chart(ticker) {
      // reuse AAPL 60 demo series as placeholder for any ticker offline
      const s = (G.GMT_FIXTURES && G.GMT_FIXTURES.aapl60) || [];
      return {
        data: { ticker: (ticker || "AAPL").toUpperCase(), series: s, sessions: s.length },
        prov: { adapter: "demo", source: "fixtures aapl60 proxy", asof: G.GMT_FIXTURES.meta.demoAsOf, mode: "DEMO" }
      };
    }
  };

  const CongressLive = {
    available() {
      const c = liveCfg();
      if (!canHttp()) {
        status.congressLive.state = "DISABLED";
        status.congressLive.fallback = "file:// — DEMO congress";
        return false;
      }
      if (!c || !c.endpoints || !c.endpoints.congressWire) {
        status.congressLive.state = "UNCONFIGURED";
        status.congressLive.fallback = "no congress endpoints";
        return false;
      }
      return true;
    },
    fetch(path, timeout) {
      const t0 = performance.now();
      return U.fetchJson(path, timeout || 12000).then(j => {
        status.congressLive.state = "OK";
        status.congressLive.lastSuccess = U.nowIso();
        status.congressLive.latencyMs = Math.round(performance.now() - t0);
        status.congressLive.error = null;
        status.congressLive.fallback = null;
        emit();
        return j;
      }).catch(err => {
        status.congressLive.state = "ERROR";
        status.congressLive.error = String(err && err.message || err);
        status.congressLive.fallback = "congress live failed → DEMO";
        status.congressLive.latencyMs = Math.round(performance.now() - t0);
        emit();
        throw err;
      });
    },
    months(by) {
      const c = liveCfg();
      let url = c.endpoints.congressMonths || "/api/terminal/congress/months";
      url += (url.indexOf("?") >= 0 ? "&" : "?") + "by=" + encodeURIComponent(by || "filing");
      return this.fetch(url).then(j => ({
        data: j.data,
        by: j.by,
        prov: { adapter: "congress-live", source: j.source || "sqlite", asof: j.asof || U.nowIso(), mode: "LIVE" }
      }));
    },
    wire(params) {
      const c = liveCfg();
      let url = c.endpoints.congressWire;
      const q = [];
      if (params) {
        if (params.chamber && params.chamber !== "ALL") q.push("chamber=" + encodeURIComponent(params.chamber));
        if (params.party && params.party !== "ALL") q.push("party=" + encodeURIComponent(params.party));
        if (params.side && params.side !== "ALL") q.push("side=" + encodeURIComponent(params.side));
        if (params.month) q.push("month=" + encodeURIComponent(params.month));
        if (params.date_field) q.push("date_field=" + encodeURIComponent(params.date_field));
        if (params.q) q.push("q=" + encodeURIComponent(params.q));
        if (params.tag && params.tag !== "ALL") q.push("tag=" + encodeURIComponent(params.tag));
        if (params.min_score != null && params.min_score !== "") q.push("min_score=" + encodeURIComponent(params.min_score));
        if (params.limit) q.push("limit=" + params.limit);
        if (params.offset) q.push("offset=" + params.offset);
        if (params.enrich === false) q.push("enrich=false");
        if (params.enrich === true) q.push("enrich=true");
      }
      if (q.length) url += (url.indexOf("?") >= 0 ? "&" : "?") + q.join("&");
      return this.fetch(url).then(j => ({
        data: j.data,
        meta: {
          total: j.total, count: j.count, month: j.month, date_field: j.date_field,
          group_counts: j.group_counts || {}, offset: j.offset, limit: j.limit
        },
        prov: {
          adapter: "congress-live", source: j.source || "sqlite",
          asof: j.asof || U.nowIso(), mode: "LIVE", convention: j.convention
        }
      }));
    },
    summary() {
      const c = liveCfg();
      return this.fetch(c.endpoints.congressSummary).then(j => ({
        data: j.data,
        prov: { adapter: "congress-live", source: j.source || "sqlite", asof: j.asof || U.nowIso(), mode: "LIVE" }
      }));
    },
    returns(params) {
      const c = liveCfg();
      let url = c.endpoints.congressReturns || "/api/terminal/congress/returns";
      const q = [];
      if (params) {
        if (params.month) q.push("month=" + encodeURIComponent(params.month));
        if (params.date_field) q.push("date_field=" + encodeURIComponent(params.date_field));
        if (params.side && params.side !== "ALL") q.push("side=" + encodeURIComponent(params.side));
        if (params.chamber && params.chamber !== "ALL") q.push("chamber=" + encodeURIComponent(params.chamber));
        if (params.mode) q.push("mode=" + encodeURIComponent(params.mode));
        if (params.limit) q.push("limit=" + params.limit);
      }
      if (q.length) url += (url.indexOf("?") >= 0 ? "&" : "?") + q.join("&");
      // longer timeout — yfinance pricing pool
      return this.fetch(url, 60000).then(j => ({
        data: j.data,
        prov: {
          adapter: "congress-live", source: j.source || "sqlite+yfinance",
          asof: j.asof || U.nowIso(), mode: "LIVE", convention: j.convention
        }
      }));
    },
    holders(ticker) {
      const c = liveCfg();
      const base = c.endpoints.congressHolders || "/api/terminal/congress/holders";
      return this.fetch(base.replace(/\/$/, "") + "/" + encodeURIComponent((ticker || "AAPL").toUpperCase())).then(j => ({
        data: j.data,
        prov: { adapter: "congress-live", source: j.source || "sqlite", asof: j.asof || U.nowIso(), mode: "LIVE", convention: j.convention }
      }));
    },
    sectors() {
      const c = liveCfg();
      return this.fetch(c.endpoints.congressSectors || "/api/terminal/congress/sectors").then(j => ({
        data: j.data,
        prov: { adapter: "congress-live", source: j.source || "sqlite", asof: j.asof || U.nowIso(), mode: "LIVE" }
      }));
    },
    sector(sector) {
      const c = liveCfg();
      let url = c.endpoints.congressSector || "/api/terminal/congress/sector";
      if (sector) url += (url.indexOf("?") >= 0 ? "&" : "?") + "sector=" + encodeURIComponent(sector);
      return this.fetch(url).then(j => ({
        data: j.data,
        prov: { adapter: "congress-live", source: j.source || "sqlite", asof: j.asof || U.nowIso(), mode: "LIVE", convention: j.convention }
      }));
    },
    politician(name) {
      const c = liveCfg();
      let url = c.endpoints.congressPol || "/api/terminal/congress/politician";
      if (name) url += (url.indexOf("?") >= 0 ? "&" : "?") + "name=" + encodeURIComponent(name);
      return this.fetch(url).then(j => ({
        data: j.data,
        prov: { adapter: "congress-live", source: j.source || "sqlite", asof: j.asof || U.nowIso(), mode: "LIVE" }
      }));
    },
    chart(ticker, fromDate) {
      const c = liveCfg();
      const base = c.endpoints.marketChart || "/api/terminal/market";
      let url = base.replace(/\/$/, "") + "/" + encodeURIComponent((ticker || "AAPL").toUpperCase()) + "?sessions=180";
      if (fromDate) url += "&from_date=" + encodeURIComponent(String(fromDate).slice(0, 10));
      return this.fetch(url).then(j => ({
        data: j.data,
        prov: { adapter: "live", source: j.source || "yfinance", asof: j.asof || U.nowIso(), mode: j.mode || "LIVE", convention: j.convention }
      }));
    }
  };

  const cache = {};
  const congressCache = {};

  function withFallback(key, liveFn, demoFn) {
    if (CongressLive.available()) {
      return liveFn()
        .then(r => { congressCache[key] = r; return r; })
        .catch(() => {
          if (congressCache[key] && congressCache[key].prov.mode === "LIVE") {
            const stale = {
              data: congressCache[key].data,
              prov: Object.assign({}, congressCache[key].prov, { mode: "STALE", fallback: "last LIVE congress cache" })
            };
            return stale;
          }
          status.congressDemo.lastSuccess = U.nowIso();
          return demoFn();
        });
    }
    status.congressDemo.lastSuccess = U.nowIso();
    return Promise.resolve(demoFn());
  }

  const Hub = {
    mode: "DEMO",
    congressMode: "DEMO",
    get(dataset) {
      if (LiveAdapter.available()) {
        return LiveAdapter.get(dataset)
          .then(r => { cache[dataset] = r; Hub.mode = "LIVE"; emit(); return r; })
          .catch(() => {
            const r = cache[dataset] && cache[dataset].prov.mode === "LIVE"
              ? { data: cache[dataset].data, prov: Object.assign({}, cache[dataset].prov, { mode: "STALE", fallback: "stale LIVE market cache" }) }
              : DemoAdapter.get(dataset);
            Hub.mode = r.prov.mode === "STALE" ? "STALE" : "DEMO";
            emit();
            return r;
          });
      }
      const r = DemoAdapter.get(dataset);
      Hub.mode = "DEMO";
      return Promise.resolve(r);
    },
    getCongress(kind, arg, params) {
      /* LIVE-first: no offline DEMO for congress when API is configured.
         file:// still gets demo fixtures so static open doesn't hard-crash. */
      const liveOnly = CongressLive.available();
      const key = kind + ":" + (arg || "") + ":" + JSON.stringify(params || {});

      function failLive(err) {
        status.congressLive.state = "ERROR";
        status.congressLive.error = String(err && err.message || err);
        emit();
        return Promise.reject(err);
      }

      if (kind === "months") {
        if (liveOnly) return CongressLive.months(arg || (params && params.by) || "filing").then(r => { Hub.congressMode = "LIVE"; return r; }).catch(failLive);
        return Promise.resolve({ data: [], by: "filing", prov: { mode: "OFFLINE", source: "none" } });
      }
      if (kind === "wire") {
        if (liveOnly) {
          return CongressLive.wire(params || {}).then(r => {
            congressCache[key] = r; Hub.congressMode = "LIVE"; emit(); return r;
          }).catch(err => {
            if (congressCache[key]) {
              const stale = { data: congressCache[key].data, meta: congressCache[key].meta, prov: Object.assign({}, congressCache[key].prov, { mode: "STALE" }) };
              Hub.congressMode = "STALE"; return stale;
            }
            return failLive(err);
          });
        }
        // file:// only
        let rows = CongressDemo.wire().data;
        return Promise.resolve({ data: rows, meta: { total: rows.length, count: rows.length }, prov: CongressDemo.wire().prov });
      }
      if (kind === "summary") {
        if (liveOnly) return CongressLive.summary().then(r => { Hub.congressMode = "LIVE"; return r; }).catch(failLive);
        return Promise.resolve(CongressDemo.summary());
      }
      if (kind === "holders") {
        if (liveOnly) return CongressLive.holders(arg).then(r => { Hub.congressMode = "LIVE"; return r; }).catch(failLive);
        return Promise.resolve(CongressDemo.holders(arg));
      }
      if (kind === "sectors") {
        if (liveOnly) return CongressLive.sectors();
        return Promise.resolve(CongressDemo.sectors());
      }
      if (kind === "sector") {
        if (liveOnly) return CongressLive.sector(arg);
        return Promise.resolve(CongressDemo.sector(arg));
      }
      if (kind === "politician") {
        if (liveOnly) return CongressLive.politician(arg);
        return Promise.resolve(CongressDemo.politician(arg));
      }
      if (kind === "returns") {
        if (liveOnly) {
          return CongressLive.returns(params || arg || {}).then(r => {
            Hub.congressMode = "LIVE"; emit(); return r;
          });
        }
        return Promise.resolve({
          data: { mode: "trade", rows: [], scored: 0, skipped: 0 },
          prov: { mode: "OFFLINE", source: "none" }
        });
      }
      if (kind === "chart") {
        // getCongress("chart", ticker, { from_date })
        const tk = arg;
        const fd = (params && params.from_date) || null;
        if (LiveAdapter.available() || CongressLive.available()) {
          return CongressLive.chart(tk, fd);
        }
        return Promise.resolve(CongressDemo.chart(tk));
      }
      return Promise.reject(new Error("unknown congress kind " + kind));
    },
    status() { return status; },
    cache() { return cache; },
    adapters() { return [status.demo, status.live, status.congressDemo, status.congressLive]; },
    onChange(fn) { listeners.push(fn); },
    refreshLiveProbe() {
      const jobs = [];
      if (LiveAdapter.available()) jobs.push(LiveAdapter.get("tape").then(() => true).catch(() => false));
      if (CongressLive.available()) jobs.push(CongressLive.summary().then(() => true).catch(() => false));
      return Promise.all(jobs).then(rs => rs.some(Boolean));
    }
  };

  G.data = { Hub, DemoAdapter, LiveAdapter, CongressDemo, CongressLive, status };
})(window.GMT);
