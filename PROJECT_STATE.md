# Pissa Finance — estado técnico atual

Data da análise: 13 de setembro de 2026. Este documento registra o código atual para continuidade técnica.

## Visão e arquitetura

Pissa Finance é uma aplicação pessoal de finanças em uma única aplicação FastAPI. O navegador recebe o frontend estático via `StaticFiles`; a mesma origem atende as rotas `/api/*`, `/docs` e `/health`.

```text
Navegador → frontend vanilla → FastAPI → SQLite
                         ↘ dashboard.py agrega transactions
```

Não existe tabela `dashboard`: cards e gráficos são calculados sob demanda a partir de `transactions`.

## Infraestrutura

| Item | Estado |
|---|---|
| Runtime | Python 3.12, FastAPI, Uvicorn, Pydantic, SQLite |
| Container | `pissa-finance`, imagem `python:3.12-slim` |
| Porta | host 8001 → container 8000 |
| Comando | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| Persistência | `./data:/app/data` |
| Banco no container | `/app/data/pissa_finance.db` |
| Banco no host atual | `/home/gabriel/PissaFinance/data/pissa_finance.db` |

`init_db()`, chamado no lifespan, cria as tabelas `transactions` e `goals` se não existirem. `.gitignore` exclui o banco, `.venv`, bytecode e `.env`.

## Estrutura relevante

```text
app/
├── main.py
├── database.py
└── routes/
    ├── transactions.py
    ├── goals.py
    └── dashboard.py
frontend/
├── index.html
├── css/{style,responsive,notification}.css
└── js/{app,mock-data}.js
data/pissa_finance.db
Dockerfile
docker-compose.yml
README.md
PROJECT_STATE.md
```

## Dados e schemas

### transactions

```text
id INTEGER PRIMARY KEY AUTOINCREMENT
description TEXT NOT NULL
amount REAL NOT NULL
type TEXT NOT NULL
category TEXT
transaction_date TEXT NOT NULL
created_at TEXT NOT NULL
```

`created_at` é ISO 8601 criado com `America/Sao_Paulo`. `transaction_date` representa a data financeira.

### goals

```text
id INTEGER PRIMARY KEY AUTOINCREMENT
name TEXT NOT NULL
target_amount REAL NOT NULL
current_amount REAL NOT NULL DEFAULT 0
deadline TEXT
created_at TEXT NOT NULL
```

## Rotas e integrações

| Recurso | Rotas | Frontend atual |
|---|---|---|
| Transactions | GET/POST `/api/transactions/`; PUT/DELETE `/api/transactions/{id}` | Leitura, criação, edição e exclusão integradas por fetch. |
| Goals | GET/POST `/api/goals/`; PUT/DELETE `/api/goals/{id}` | Leitura, criação, edição e exclusão integradas por fetch. |
| Dashboard | GET `/api/dashboard/` | Home e Dashboard usam o retorno real. |
| Health | GET `/health` | Retorna `{"status":"healthy"}`. |

POST e PUT de transactions recebem `description`, `amount`, `type`, `category`, `transaction_date`. POST e PUT de goals recebem `name`, `target_amount`, `current_amount`, `deadline`. DELETE/PUT retornam 404 quando não encontram o ID; bodies inválidos recebem 422 via Pydantic.

## Dashboard

### Contrato atual

```json
{
  "income": 3200,
  "expenses": 900,
  "invested": 300,
  "balance": 2000,
  "categories": [{"name": "Alimentação", "value": 450}],
  "monthly": [{"month": "Abr", "value": 1200}]
}
```

### Cálculos

- `income`: soma de `amount` onde `type == "income"`.
- `expenses`: soma onde `type == "expense"`.
- `invested`: soma onde `type == "investment"`.
- `balance`: `income - expenses - invested`.
- `categories`: somente expenses, agrupadas por `category`; valores nulos/brancos tornam-se `Sem categoria`; ordenação decrescente por valor.
- `monthly`: últimos seis meses do calendário, do mais antigo ao atual, sempre presentes. Cada valor é entradas menos saídas menos investimentos do mês, usando `transaction_date`, nunca `created_at`.

Sem transactions, o endpoint retorna os quatro totais zerados, `categories: []` e seis valores mensais zero.

### Frontend do Dashboard

`loadDashboard()` faz GET de `/api/dashboard/`. `renderDashboard()` usa exclusivamente `income`, `expenses`, `invested`, `balance`, `categories` e `monthly`.

- `renderExpenseCategories(d.categories)` atualiza `#expense-total`, `#expense-donut` e `#expense-legend`; a paleta é fixa apenas no JS.
- `renderMonthlyEvolution(d.monthly)` atualiza `#line-chart` e `#chart-months`; usa altura mínima segura quando tudo é zero e cor distinta para valor negativo.
- Não há referências de Dashboard a `state.data.dashboard`, `state.data.categories` ou `state.data.monthly`.

A Home usa `balance` para “Saldo disponível”, `income`, `invested` e `expenses`; o mês é gerado no navegador em pt-BR. Não usa mais `netWorth`, `saved`, `earnings` ou `available_balance`.

## Estado do frontend

`app.js` ainda carrega `mock-data.js` e mantém `data: window.MockData` em `state`, mas nenhum consumidor ativo do Dashboard usa esses valores. Transactions e goals são carregadas via API e mantidas em `state.transactions` e `state.goals` para edição/exclusão.

O arquivo `mock-data.js` permanece no projeto por decisão de escopo; seu conteúdo é residual e deve ser removido somente após uma revisão específica.

## Fluxos de UI concluídos

- Navegação Home, Movimentações, Metas e Dashboard.
- Modal reutilizado para criar/editar transactions e goals.
- Confirmação visual antes de exclusão.
- Notificações de sucesso/erro e fechamento automático.
- Filtros locais de transactions.

## Limitações e bugs conhecidos

- Não há estados visuais globais de loading.
- Falhas de rede de `fetch` não têm tratamento global uniforme.
- `type` é `str` livre no backend; o select restringe apenas a UI.
- Datas de transactions são exibidas sem formatação pt-BR.
- O campo `note` existe visualmente no formulário de transaction, mas não integra payload/schema.
- Barras mensais negativas são exibidas para cima em vermelho; não há eixo zero dedicado.
- Não há investimentos reais, valor de mercado, rentabilidade ou projeções.

## Roadmap

### Fase 1 — Core financeiro

- [done] FastAPI, SQLite persistente, Docker e frontend via StaticFiles.
- [done] CRUD de transactions e goals com integração ponta a ponta.
- [done] Home real com income, expenses, invested e balance.
- [done] Dashboard agregado: cards, categories/donut/legenda e monthly/seis meses.
- [done] Remoção dos mocks ativos do Dashboard.

### Fase 2 — Investimentos reais

- [ ] Definir modelo e tabela de investments.
- [ ] Relacionar aportes do tipo investment a posições.
- [ ] Diferenciar aporte de valor atual.
- [ ] Criar service layer.

### Fase 3 — Dados externos

- [ ] Fontes de mercado, preço de criptoativos, CDI, Selic e eventualmente ações/ETFs.
- [ ] Cache e tratamento de falha de APIs externas.

### Fase 4 — Rentabilidade

- [ ] Valor atual, aportado, lucro/prejuízo e rentabilidade percentual.
- [ ] Patrimônio financeiro real e separação de saldo disponível.

### Fase 5 — Projeções

- [ ] Projeções matemáticas, aportes recorrentes e horizontes de 6 meses, 1 ano e múltiplos anos.
- [ ] Cenários conservador/base/otimista.

Projeções devem depender de matemática e dados reais, nunca de números inventados.

### Fase 6 — UX e qualidade

- [ ] Loading, erros globais, validações, datas pt-BR, acessibilidade e revisão mobile.
- [ ] Remover mock-data.js após revisão de consumidores.

### Fase 7 — Futuro

- [ ] Autenticação, múltiplos usuários, exportação, backups e relatórios.
- [ ] Avaliar AI-SERVER se for útil.

## Próximo passo recomendado

Projetar a camada de investimentos reais antes de integrar APIs externas. Isso inclui definir o modelo de dados e separar aporte financeiro de valor atual do ativo.
