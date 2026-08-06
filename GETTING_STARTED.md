# Getting Started

## 1. Ambiente

```bash
uv sync
cd web_fused && npm install && cd ..
copy .env.example .env   # preencher chaves se precisar
```

`web_fused/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 2. Subir

```bash
# Terminal A
set MARKET_DATA_ENABLED=1
uv run python server\api_server.py

# Terminal B
cd web_fused
npm run dev -- -p 3000
```

| URL | App |
|-----|-----|
| http://localhost:3000 | CongressInvests UI |
| http://localhost:8000/terminal/ | CI://TERMINAL |
| http://localhost:8000/docs | OpenAPI |

## 3. Dados

Se o SQLite já existir no teu disco de trabalho, a API usa-o.  
Para popular de novo: `scripts/update_official.py` e `scripts/update_senate.py`.

## 4. Terminal — primeiro uso

1. Abre `/terminal/`
2. Se o layout antigo não mostrar **RETURNS**, clica **RESET**
3. Escolhe um mês no wire → cards de membros com fotos
4. Clica trade → velas + TX marker
5. **RETURNS LEADERBOARD** pode demorar na 1ª carga (yfinance)

## 5. Não commitar

- `.env`, `*.db`, `data/`, caches de preço, secrets
