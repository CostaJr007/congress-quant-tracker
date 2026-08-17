# CongressQuantTracker

**Congressional trading intelligence + Bloomberg-style market desk**

Rastreador de disclosures financeiros (PTR) da **House** e do **Senate** dos EUA, com scores, fotos, performance estimada via **yfinance**, UI Next.js e um terminal **CI://TERMINAL** (visual Bloomberg × ASCII) para acompanhar deputados/senadores, ativos em comum, setores e ranking de retornos.

> Repositório **privado**. Não commitar `.env`, chaves de API, nem o banco SQLite.

---

## O que o sistema faz

| Área | Capacidade |
|------|------------|
| **Disclosures** | House FD (zip/PDF) + Senate eFD / fallbacks |
| **Scoring** | Score 0–100 e tags (routine → high_alert) |
| **Mercado** | Preço desde o trade, shares est., sparklines (yfinance + cache) |
| **UI web** | Dashboard, politicians, trades por mês, stocks, signals, leaderboard |
| **CI://TERMINAL** | Desk denso: wire por mês, fotos, holders, setores, velas diárias, **returns leaderboard** |

---

## Arquitetura

```
┌─────────────────────┐     ┌──────────────────────────┐
│  web_fused (Next.js)│────▶│  FastAPI :8000           │
│  :3000              │     │  SQLite + pipelines      │
└─────────────────────┘     │  yfinance market data    │
                            │  /terminal/  (static)    │
┌─────────────────────┐     │  /politicians/*.jpg      │
│  CI://TERMINAL      │────▶│  /api/terminal/*         │
│  ci_terminal/       │     └──────────────────────────┘
└─────────────────────┘
```

| Componente | Path | Porta |
|------------|------|-------|
| API | `server/api_server.py` | **8000** |
| UI fused | `web_fused/` | **3000** |
| Terminal | `ci_terminal/` → servido em `/terminal/` | via 8000 |
| Domain | `src/congress_quant_tracker/` | — |
| Fotos | `web_fused/public/politicians/` | `/politicians/{bioguide}.jpg` |

---

## Início rápido

### Pré-requisitos

- Python **3.12+** e [uv](https://github.com/astral-sh/uv)
- Node.js **20+** (para `web_fused`)
- Windows / macOS / Linux

### 1. Clone e dependências

```bash
git clone https://github.com/CostaJr007/congress-quant-tracker.git
cd congress-quant-tracker
uv sync
cd web_fused && npm install && cd ..
```

### 2. Ambiente

```bash
# crie .env a partir do exemplo (não versionado)
copy .env.example .env   # Windows
# cp .env.example .env   # Unix
```

Variáveis úteis:

| Variável | Default | Função |
|----------|---------|--------|
| `MARKET_DATA_ENABLED` | `1` | yfinance (charts, returns, enrich) |
| `NO_YF` | `0` | desliga yfinance no scorer (mercado pode continuar com MARKET_DATA) |
| `GROQ_API_KEY` | — | extração LLM de PDFs + Copilot (opcional) |
| `OPENAI_API_KEY` | — | Copilot GPT (opcional) |
| `TAVILY_API_KEY` | — | busca / resolve (opcional) |
| `DISCORD_WEBHOOK_URL` | — | alerta de trades novos / flagged |
| `HTTP_PROXY` | — | proxy HTTPS p/ Senate eFD se bloqueado |
| `DATABASE_URL` | SQLite local | URL do banco |

### 3. Subir API + UI

```bash
# API (market data ON)
set MARKET_DATA_ENABLED=1
uv run python server\api_server.py

# outro terminal — Next.js
cd web_fused
echo NEXT_PUBLIC_API_URL=http://localhost:8000 > .env.local
npm run dev -- -p 3000
```

- **Dashboard:** http://localhost:3000  
- **CI://TERMINAL:** http://localhost:8000/terminal/  
- **API docs:** http://localhost:8000/docs  

### 4. Pipelines (dados)

```bash
# House official
uv run python scripts/update_official.py

# Senate (pode precisar proxy; se o proxy cair, tenta direto)
uv run python scripts/update_senate.py

# Setores + fotos + opções + re-score (sem yfinance)
uv run python scripts/enrich_all.py

# Re-score apenas
uv run python scripts/rescore.py
```

Endpoints de pipeline também existem em `POST /api/pipeline/*`.

---

## CI://TERMINAL

Desk monoespaçado preto + barras laranja (estilo Bloomberg **sem** marcas protegidas).

### Widgets principais (preset CONGRESS)

| Widget | Função |
|--------|--------|
| **MEMBERS · BY MONTH** | Browser por mês (filed/traded), cards com foto, blocos colapsados se muitos trades |
| **RETURNS LEADERBOARD** | Ranking por Δ% / ADJ% (BUY:+Δ, SELL:−Δ) e PnL$ est. |
| **FOCUSED ASSET** | Velas diárias (ou linha) + marcador TX na data do trade |
| **ASSET HOLDERS** | Quem mais operou o mesmo ticker (House/Senate) |
| **POLITICIAN BOOK** | Tickers + datas TX/FILED do membro |
| **SECTOR DESK** | Overlap House×Senate por setor |

Presets: `CGS` (default) · `GLB` · `EQ` · `MET` · `NWS`  
Layout editável (EDIT / drag) salvo em `localStorage` (`layout.v3`).

### API do terminal

| Endpoint | Descrição |
|----------|-----------|
| `GET /api/terminal/dataset?dataset=tape\|stocks\|…` | Mercado yfinance |
| `GET /api/terminal/congress/wire` | Disclosures (+ filtros mês, chamber, party, side, q) |
| `GET /api/terminal/congress/months` | Meses com trades |
| `GET /api/terminal/congress/holders/{ticker}` | Co-holders |
| `GET /api/terminal/congress/sector` | Setor desk |
| `GET /api/terminal/congress/politician?name=` | Book do membro |
| `GET /api/terminal/congress/returns` | Leaderboard de retornos |
| `GET /api/terminal/market/{ticker}?from_date=` | OHLCV diário p/ chart |
| `GET /api/analyze/overview` | Party / setor / opções / suspicious |
| `POST /api/pipeline/enrich` | Setores + fotos + rescore |

Config LIVE do front: `ci_terminal/js/live.config.js` (same-origin).

### Definições de dados (importante)

- Disclosures usam **faixas de valor**, não shares exatos → shares/PnL são **estimativas** (midpoint).
- `change_pct` = movimento do ativo desde a data do trade (yfinance, `auto_adjust`).
- `return_side_adj` = BUY:+Δ% / SELL:−Δ% (outcome do lado da operação).
- Metais no tape usam futuros Yahoo (`GC=F` etc.) como proxy de spot.
- News wire DEMO não é feed licenciado; não fabricar notícias “live”.

Detalhes: `ci_terminal/DATA_DEFINITIONS.md` e `ci_terminal/README.md`.

---

## UI web_fused

- **Trades** — filtro por mês, grouping de filers pesados (`TradeGroupList`)
- **Politicians / Stocks / Signals / Leaderboard**
- Link **CI Terminal** na sidebar → abre o desk

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Estrutura de pastas (resumo)

```
congress-quant-tracker/
├── server/api_server.py          # FastAPI (trades, market, terminal, pipelines)
├── src/congress_quant_tracker/
│   ├── enrichers/
│   │   ├── market_data.py        # yfinance cache / trade performance
│   │   ├── terminal_market.py    # feed LIVE do heatmap/tape
│   │   └── terminal_congress.py  # wire, holders, returns, setores
│   ├── fetchers/ parsers/ scoring/ services/ …
├── ci_terminal/            # CI://TERMINAL (HTML/CSS/JS offline-capable)
├── web_fused/                    # Next.js UI principal
├── scripts/                      # update_official, update_senate, rescore
├── dashboard/                    # Streamlit legado (opcional)
├── pyproject.toml
└── README.md
```

---

## Segurança e privacidade

- **Não** commitar: `.env`, `*.db`, `data/`, chaves API, proxies com credenciais.
- `.gitignore` já cobre secrets, cache de preços, `node_modules`, PDFs.
- Fotos de políticos: `web_fused/public/politicians/` (bioguide); API monta em `/politicians/`.
- Repo deve permanecer **private** se contiver dados operacionais ou configs internas.

```bash
gh repo edit CostaJr007/congress-quant-tracker --visibility private
```

---

## Scripts úteis

| Comando | Ação |
|---------|------|
| `uv run python server/api_server.py` | API :8000 |
| `cd web_fused && npm run dev` | UI :3000 |
| `uv run python scripts/update_official.py` | House |
| `uv run python scripts/update_senate.py` | Senate |
| `uv run python scripts/rescore.py` | Re-score trades |
| `uv run python scripts/enrich_all.py` | Setores + fotos + opções + rescore |
| `uv run pytest` | Testes unitários |

---

## Limitações conhecidas

- Yahoo/yfinance: atraso e rate limit; 1ª carga do returns leaderboard pode demorar.
- Senate eFD: Akamai/403 — use proxy HTTPS se necessário.
- Setores no SQLite muitas vezes vazios → mapa estático ticker→setor no terminal.
- Holiday calendar de bolsas: sessão do clock pode marcar OPEN sem feriados oficiais.
- Estimativas de shares/PnL **não** são posições oficiais.

---

## Licença / uso

Uso interno / pesquisa. Fontes oficiais de disclosure (House/Senate) e cotações Yahoo (não oficiais).  
Não é aconselhamento de investimento. Não copiar marcas/logos Bloomberg.

---

## Changelog (merge terminal)

- **web_fused** Next.js (dashboard, trades, politicians, stocks, signals, leaderboard, analyze)  
- Analyzers ligados em `/api/analyze/*` + Discord opcional após pipelines  
- Setores estáticos + rescore + fotos; Senate eFD tenta direto se o proxy cair  
- Integração **CI://TERMINAL** Bloomberg × ASCII + adapters LIVE/DEMO  
- yfinance bulk (tape, heatmap, metals, chart diário)  
- Wire por mês + cards de membros com **fotos**  
- Holders / sector desk / politician book + datas TX/FILED  
- Candlestick diário + marcador de trade  
- **Returns leaderboard** (trade / member, ADJ%, PnL est.)  
- Link na sidebar do `web_fused`  
