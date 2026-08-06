# Congress Trade Tracker - Guia Completo 🏛️📈

## ✅ Tudo Pronto!

### O que foi criado:

**📁 Projeto Completo:**
```
D:\congress-quant-tracker\
├── scripts/
│   ├── daily_update.py    # Pipeline de dados
│   └── seed_database.py   # Popular database (NOVO!)
├── dashboard/
│   ├── app.py             # Dashboard principal
│   └── pages/             # 18 páginas!
│       ├── 1_Politicians.py
│       ├── 2_Leaderboard.py
│       ├── 3_Parties.py
│       ├── 4_Sectors.py
│       ├── 5_Tickers.py
│       ├── 6_Options.py
│       ├── 7_Recent_Trades.py
│       ├── 8_Compare.py
│       ├── 9_Suspicious.py
│       ├── 10_Committee.py
│       ├── 11_Radar.py
│       ├── 12_XRay.py
│       ├── 13_Heatmap.py
│       ├── 14_Treemap.py
│       ├── 15_Smart_Money.py
│       ├── 16_Late_Filers.py
│       ├── 17_Notable_Trades.py
│       └── 18_Conflicts.py
├── src/congress_quant_tracker/
│   ├── config.py
│   ├── database/models.py
│   ├── fetchers/           # Senate + House
│   ├── parsers/            # PDF parser (Claude)
│   ├── enrichers/          # yfinance
│   ├── analyzers/          # Análises
│   └── services/           # Pipeline
├── setup_windows.bat       # Setup (NOVO!)
└── run_dashboard.bat       # Rodar dashboard (NOVO!)
```

---

## 🚀 Como Usar

### Opção 1: Rápido (com dados de exemplo)

1. **Abra o PowerShell** como administrador

2. **Navegue até o projeto:**
   ```powershell
   cd D:\congress-quant-tracker
   ```

3. **Execute:**
   ```powershell
   .\run_dashboard.bat
   ```

4. **Abra o navegador:** `http://localhost:8501`

### Opção 2: Dados Reais

1. **Configure a API do Claude** no `.env`:
   ```
   ANTHROPIC_API_KEY=sua_chave_aqui
   ```

2. **Execute o pipeline:**
   ```powershell
   python scripts\daily_update.py --once
   ```

3. **Inicie o dashboard:**
   ```powershell
   streamlit run dashboard\app.py
   ```

---

## 📊 Dashboard Features

### 🏠 Home (app.py)
- Hero stats (total trades, políticos, volume)
- Comparação Democratas vs Republicanos
- Feed de trades recentes
- Top performers
- Tickers em alta

### 👤 Páginas (18 total!)

| Página | Descrição |
|--------|-----------|
| 1_Politicians | Busca por político com histórico |
| 2_Leaderboard | Ranking de top traders |
| 3_Parties | Comparação D vs R |
| 4_Sectors | Análise setorial |
| 5_Tickers | Busca por ticker (NVDA, TSLA, etc) |
| 6_Options | Calls vs Puts, strikes |
| 7_Recent_Trades | Trades mais recentes |
| 8_Compare | Comparar políticos |
| 9_Suspicious | Atividade suspeita |
| 10_Committee | Análise por comitê |
| 11_Radar | Radar de oportunidades |
| 12_XRay | Análise profunda |
| 13_Heatmap | Mapa de calor |
| 14_Treemap | Treemap setorial |
| 15_Smart_Money | Smart money tracking |
| 16_Late_Filers | Filers atrasados |
| 17_Notable_Trades | Trades notáveis |
| 18_Conflicts | Conflitos de interesse |

---

## 🎨 Design System

### Dark Theme (inspirado no Capitol Trades)
- Background: `#0a0a0a`
- Cards: `#1a1a1a`
- Text: `#ffffff`
- Accent: `#3b82f6` (azul)
- Buy: `#22c55e` (verde)
- Sell: `#ef4444` (vermelho)
- Border: `#27272a`

---

## 📈 Dados de Exemplo

O `seed_database.py` cria:
- **15 políticos** (Pelosi, Tuberville, Cruz, AOC, etc.)
- **25 empresas** (AAPL, MSFT, NVDA, TSLA, etc.)
- **~300 trades** aleatórios
- **~90 opções** (calls e puts)

---

## 🔧 Configuração

### .env
```env
DATABASE_URL=sqlite:///D:/congress-quant-tracker/congress_quant_tracker.db
ANTHROPIC_API_KEY=sua_chave
ANTHROPIC_BASE_URL=https://api.doxio.ai/v1
LLM_MODEL=claude-3-5-sonnet-20241022
```

---

## 📝 Próximos Passos

1. **Rodar com dados de exemplo** (agora!)
2. **Configurar API do Claude** (opcional)
3. **Rodar pipeline real** (quando API configurada)
4. **Personalizar dashboard**
5. **Adicionar alertas Telegram**

---

## 🆘 Troubleshooting

### Erro: "Module not found"
```powershell
pip install -r requirements.txt
```

### Erro: "Database locked"
Feche outros programas que usam o SQLite

### Dashboard não abre
Verifique se a porta 8501 está livre

---

## 💡 Dica

O projeto já tem **tudo** que você precisa:
- ✅ Fetchers (Senate + House)
- ✅ PDF Parser (Claude)
- ✅ Enrichment (yfinance)
- ✅ Analyzers (5 tipos)
- ✅ Dashboard (18 páginas!)
- ✅ API Server (FastAPI)

É só rodar! 🎲
