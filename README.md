# 🏛️ CongressQuantTracker

**Rastreador quantitativo de disclosures financeiros do Congresso dos EUA**

Monitora **todos** os trades de ações e opções de deputados (House) e senadores (Senate) dos Estados Unidos, com análise profunda por político, partido, setor e empresa.

---

## 🎯 Perguntas que o Sistema Responde

| Pergunta | Análise |
|---|---|
| Quais deputados compram mais Tech? | `party_analyzer` + `sector_analyzer` |
| Democratas vs Republicanos: quem compra mais energia? | `party_analyzer.get_party_sector_exposure()` |
| Quais políticos estão comprando NVDA? | `sector_analyzer.get_top_buyers_of_ticker("NVDA")` |
| Qual partido tem mais calls que puts? | `options_analyzer.get_call_put_ratio_by_party()` |
| Setores mais comprados por cada partido? | `party_analyzer.get_party_behavior_diff()` |
| Quais opções estão expirando em breve? | `options_analyzer.get_options_expiring_soon()` |

---

## 📁 Estrutura do Projeto

```
congress-quant-tracker/
├── src/
│   └── congress_quant_tracker/
│       ├── config.py                    # Configuração central
│       ├── database/
│       │   └── models.py                # Modelos SQLAlchemy
│       ├── fetchers/
│       │   ├── house_fetcher.py         # Download de PDFs da House
│       │   └── senate_fetcher.py        # Download de PDFs do Senate
│       ├── parsers/
│       │   └── pdf_parser.py            # Extração via Claude 3.5 Sonnet
│       ├── enrichers/
│       │   └── company_enricher.py      # Enriquecimento com yfinance
│       ├── analyzers/
│       │   ├── politician_analyzer.py   # Análise por político
│       │   ├── party_analyzer.py        # Democrat vs Republican
│       │   ├── sector_analyzer.py       # Análise setorial
│       │   └── options_analyzer.py      # Análise de opções
│       └── services/
│           └── data_updater.py          # Pipeline completo
├── dashboard/
│   └── app.py                           # Streamlit dashboard
├── scripts/
│   └── daily_update.py                  # Script de atualização diária
├── pyproject.toml
├── README.md
└── .env.example
```

---

## 🚀 Instalação

### Pré-requisitos

- Python 3.12+
- `uv` (gerenciador de pacotes)
- PostgreSQL (opcional, SQLite funciona para desenvolvimento)
- Chave da API Anthropic (Claude 3.5 Sonnet)

### Passos

```bash
# 1. Clone o repositório
git clone <seu-repo>
cd congress-quant-tracker

# 2. Instale dependências com uv
uv sync

# 3. Configure variáveis de ambiente
cp .env.example .env
# Edite .env com sua chave da API Anthropic

# 4. Inicialize o banco de dados
uv run python -c "
from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import init_db
init_db(settings.DATABASE_URL)
print('Banco de dados criado!')
"

# 5. Execute a primeira atualização de dados
uv run python scripts/daily_update.py --once

# 6. Inicie o dashboard
uv run streamlit run dashboard/app.py
```

### Configuração da API do Claude

1. Crie uma conta em [console.anthropic.com](https://console.anthropic.com)
2. Gere uma chave de API
3. Adicione no arquivo `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx
   ```

---

## 🖥️ Dashboard Streamlit

O dashboard possui **6 abas** interativas:

### 🏠 Overview
- Métricas gerais (total de trades, políticos, opções)
- Tickers mais quentes
- Resumo por partido

### 👤 Políticos
- Busca por nome com autocomplete
- Histórico completo de trades
- Exposição setorial individual
- Ratio compras/vendas

### 🐘🫏 Partidos
- Comparação Democratas vs Republicanos
- Volume de compras/vendas por partido
- Setores mais comprados por cada partido
- Heatmap: Partido vs Setor
- Top tickers por partido

### 🏭 Setores
- Treemap de atividade setorial
- Drilldown por setor com breakdown partidário

### 🏢 Empresas
- Busca por ticker (ex: NVDA, TSLA, AAPL)
- Resumo do ticker (compras/vendas/políticos)
- Top compradores do ticker
- Opções do ticker

### 📊 Opções
- Calls vs Puts por partido
- Strikes mais populares
- Top traders de opções
- Opções com vencimento próximo

### Exemplo de Comando

```bash
uv run streamlit run dashboard/app.py
```

Acesse `http://localhost:8501` no navegador.

---

## 🔄 Atualização Diária Automática

### Execução Manual

```bash
# Atualização única
uv run python scripts/daily_update.py --once

# Modo agendado (9:00 AM diário)
uv run python scripts/daily_update.py --schedule
```

### Agendamento no Windows (Task Scheduler)

```powershell
# Criar tarefa agendada (PowerShell como Admin)
$action = New-ScheduledTaskAction -Execute "uv" -Argument "run python scripts/daily_update.py --once" -WorkingDirectory "D:\congress-quant-tracker"
$trigger = New-ScheduledTaskTrigger -Daily -At "09:00"
Register-ScheduledTask -TaskName "CongressQuantDaily" -Action $action -Trigger $trigger
```

### Agendamento no Linux/macOS (cron)

```bash
# Adicione ao crontab: 
0 9 * * * cd /path/to/congress-quant-tracker && uv run python scripts/daily_update.py --once
```

---

## 📊 Modelo de Dados

### `politicians`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | INTEGER PK | ID único |
| name | VARCHAR(255) | Nome completo |
| chamber | ENUM(house, senate) | Câmara |
| party | ENUM(D, R, I) | Partido |
| state | VARCHAR(2) | Estado (sigla) |
| district | VARCHAR(10) | Distrito (House) |
| committees | TEXT | Comitês |
| active | BOOLEAN | Ativo? |

### `trades`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | INTEGER PK | ID único |
| politician_id | INTEGER FK | Político |
| ticker | VARCHAR(10) | Símbolo da ação |
| transaction_type | ENUM(buy, sell, exchange) | Tipo |
| trade_date | DATE | Data do trade |
| value_min / value_max | INTEGER | Range de valor ($) |
| filing_date | DATE | Data de filing |

### `options_trades`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | INTEGER PK | ID único |
| trade_id | INTEGER FK | Trade pai |
| option_type | ENUM(call, put) | Tipo de opção |
| strike | FLOAT | Strike price |
| expiration_date | DATE | Data de vencimento |
| contracts_min / max | INTEGER | Número de contratos |

### `companies`
| Coluna | Tipo | Descrição |
|---|---|---|
| ticker | VARCHAR(10) | Símbolo (PK lógica) |
| name | VARCHAR(255) | Nome da empresa |
| sector | VARCHAR(100) | Setor (yfinance) |
| industry | VARCHAR(100) | Indústria (yfinance) |
| market_cap | FLOAT | Capitalização de mercado |
| beta | FLOAT | Beta |

### `updates_log`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | INTEGER PK | ID único |
| update_type | VARCHAR(50) | Tipo de atualização |
| status | ENUM | Status (started/completed/failed) |
| records_processed | INTEGER | Registros processados |

---

## 🔧 Stack Tecnológica

| Componente | Tecnologia | Propósito |
|---|---|---|
| Linguagem | Python 3.12+ | Core |
| Gerenciador | `uv` | Dependências |
| Banco | PostgreSQL / SQLite | Armazenamento |
| ORM | SQLAlchemy 2.0 | Modelos |
| Dashboard | Streamlit | Visualização |
| Parsing PDF | pdfplumber + Claude 3.5 Sonnet | Extração |
| Enriquecimento | yfinance | Dados de mercado |
| Agendamento | APScheduler | Updates diários |
| Gráficos | Plotly | Visualizações |
| HTTP | httpx | Requisições |

---

## 🧪 Exemplos de Uso Programático

```python
from congress_quant_tracker.config import settings
from congress_quant_tracker.database.models import get_engine, get_session
from congress_quant_tracker.analyzers.party_analyzer import PartyAnalyzer
from congress_quant_tracker.analyzers.sector_analyzer import SectorAnalyzer

engine = get_engine(settings.DATABASE_URL)
session = get_session(engine)

# Democratas vs Republicanos por setor
party = PartyAnalyzer(session)
print(party.get_party_sector_exposure())

# Quem está comprando NVDA?
sector = SectorAnalyzer(session)
print(sector.get_top_buyers_of_ticker("NVDA"))
```

---

## 📝 Notas

- A API da House (`disclosures-clerk.house.gov`) pode ter rate limits. O sistema usa retry com exponential backoff.
- A API do Senate (`efdsearch.senate.gov`) requer headers específicos.
- O parsing via Claude 3.5 Sonnet é o ponto de maior custo ($3/M input tokens, $15/M output tokens). Aprox. 800-2000 tokens por PDF.
- Use `DATABASE_URL=sqlite:///...` para desenvolvimento local.

---

## 📄 Licença

MIT
