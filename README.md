# Pissa Finance

Sistema pessoal de finanças, mobile-first, destinado a rodar localmente em Docker no Samsunguinho e ser acessado pelo navegador — especialmente por iPhone em rede privada/Tailscale.

Transactions, goals e Dashboard usam dados reais do FastAPI/SQLite. O Dashboard é uma camada de leitura que agrega transactions; ele não possui tabela própria.

## Stack

- Python 3.12
- FastAPI, Uvicorn e Pydantic
- SQLite
- HTML5, CSS3 e JavaScript vanilla
- Docker e Docker Compose

## Arquitetura

```text
iPhone / navegador
        ↓
Frontend estático (HTML + CSS + JS)
        ↓
FastAPI / Uvicorn
        ↓
SQLite
```

O FastAPI serve tanto API quanto frontend via `StaticFiles`, portanto a UI usa rotas relativas como `/api/transactions/`.

## Executar

```bash
docker compose up -d --build
```

| Serviço | Endereço |
|---|---|
| Interface | `http://HOST:8001` |
| Docs OpenAPI | `http://HOST:8001/docs` |
| Health check | `http://HOST:8001/health` |

O host usa a porta 8001 e o Uvicorn roda na porta 8000 do container. O SQLite persiste em `./data/pissa_finance.db` pelo bind mount `./data:/app/data`.

## Estrutura

```text
app/
├── main.py                    # FastAPI, routers, lifespan e StaticFiles
├── database.py                # SQLite e schema inicial
└── routes/
    ├── transactions.py        # CRUD de transactions
    ├── goals.py               # CRUD de goals
    └── dashboard.py           # Agregações de leitura do Dashboard
frontend/
├── index.html
├── css/
└── js/
    ├── app.js                 # Integrações HTTP e renderização
    └── mock-data.js           # Arquivo legado, sem uso ativo no Dashboard
data/pissa_finance.db
Dockerfile
docker-compose.yml
```

## API e modelos

### Transactions

Campos: `id`, `description`, `amount`, `type`, `category`, `transaction_date`, `created_at`.

| Método | Rota |
|---|---|
| POST | `/api/transactions/` |
| GET | `/api/transactions/` |
| PUT | `/api/transactions/{id}` |
| DELETE | `/api/transactions/{id}` |

`id` é SQLite AUTOINCREMENT. `transaction_date` é a data financeira escolhida; `created_at` é criado pelo backend no fuso `America/Sao_Paulo`. Tipos usados pela UI: `income`, `expense` e `investment`.

### Goals

Campos: `id`, `name`, `target_amount`, `current_amount`, `deadline`, `created_at`.

| Método | Rota |
|---|---|
| POST | `/api/goals/` |
| GET | `/api/goals/` |
| PUT | `/api/goals/{id}` |
| DELETE | `/api/goals/{id}` |

### Dashboard

`GET /api/dashboard/` deriva dados exclusivamente da tabela `transactions`:

```text
transactions → dashboard.py → cálculos agregados → frontend
```

Contrato:

```json
{
  "income": 0,
  "expenses": 0,
  "invested": 0,
  "balance": 0,
  "categories": [{"name": "Alimentação", "value": 0}],
  "monthly": [{"month": "Abr", "value": 0}]
}
```

`balance = income - expenses - invested`. `categories` agrupa somente `expense` por categoria; categorias nulas/vazias viram `Sem categoria`. `monthly` retorna os últimos seis meses, incluindo o atual, com saldo líquido mensal baseado em `transaction_date`.

## Estado de implementação

- [x] FastAPI, SQLite persistente e Docker Compose.
- [x] Frontend servido pelo FastAPI.
- [x] CRUD e integração UI/API de transactions.
- [x] CRUD e integração UI/API de goals.
- [x] Home com `income`, `expenses`, `invested` e `balance` reais.
- [x] Dashboard com cards, donut/legenda de categorias e evolução mensal reais.
- [x] Estados vazios do Dashboard: categorias vazias e seis meses com zero.

## Roadmap

### Fase 2 — Investimentos reais

- [ ] Definir modelo e tabela `investments`.
- [ ] Relacionar aportes com posições.
- [ ] Separar valor aportado de valor atual.
- [ ] Criar service layer de investimentos.

### Fase 3 — Dados externos

- [ ] Fontes externas de mercado, cripto e renda fixa.
- [ ] CDI, Selic e eventualmente ações/ETFs.
- [ ] Cache e tratamento de falhas de APIs externas.

### Fase 4 — Rentabilidade

- [ ] Valor atual, total aportado, lucro/prejuízo e rentabilidade.
- [ ] Patrimônio financeiro real e separação de saldo disponível.

### Fase 5 — Projeções

- [ ] Aportes recorrentes e projeções para 6 meses, 1 ano e múltiplos anos.
- [ ] Cenários conservador/base/otimista.

Projeções devem usar matemática e dados reais, nunca números inventados.

### Fase 6 — UX e qualidade

- [ ] Loading, erros globais e validações melhores.
- [ ] Datas em pt-BR, acessibilidade e revisão mobile.
- [ ] Limpar o arquivo/mock residual após confirmar que não há consumidores.

### Fase 7 — Futuro

- [ ] Autenticação, múltiplos usuários, exportação, backups e relatórios.
- [ ] Avaliar integração com AI-SERVER somente se fizer sentido.

Para detalhes técnicos e decisões de continuidade, consulte [PROJECT_STATE.md](PROJECT_STATE.md).
