# Pissa Finance

Sistema pessoal de controle financeiro, mobile-first, pensado para rodar localmente em Docker e ser acessado pelo celular via rede privada/Tailscale. Transactions já possuem integração entre interface, FastAPI e SQLite; metas e dashboard ainda usam dados mockados.

## Stack

- Python 3.12, FastAPI e Uvicorn
- SQLite
- HTML5, CSS3 e JavaScript vanilla
- Docker e Docker Compose

## Arquitetura

```text
iPhone / navegador
        ↓
Frontend: HTML + CSS + JavaScript
        ↓
FastAPI / Uvicorn
        ↓
SQLite
```

Frontend e API são servidos pela mesma aplicação FastAPI, permitindo chamadas relativas como `/api/transactions/`.

## Estrutura do projeto

```text
PissaFinance/
├── app/
│   ├── database.py                 # SQLite e criação da tabela
│   ├── main.py                     # FastAPI, lifespan, health e StaticFiles
│   └── routes/transactions.py      # Models e CRUD de transactions
├── data/pissa_finance.db           # Banco persistido (ignorado pelo Git)
├── frontend/
│   ├── index.html                  # SPA, telas, navegação, modal e avisos
│   ├── css/{style,responsive,notification}.css
│   └── js/{app,mock-data}.js
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── PROJECT_STATE.md                # Inventário técnico detalhado
└── README.md
```

## Como executar

```bash
docker compose up -d --build
```

| Serviço | Endereço |
|---|---|
| Interface | `http://HOST:8001` |
| Documentação OpenAPI | `http://HOST:8001/docs` |
| Health check | `http://HOST:8001/health` |

Exemplo local: `http://localhost:8001`. O contêiner usa a porta `8000`; o Compose publica `8001:8000`.

## Persistência

```text
Container: /app/data/pissa_finance.db
Host:      /home/gabriel/PissaFinance/data/pissa_finance.db
Volume:    ./data:/app/data
```

O bind mount preserva o banco fora do contêiner. `.gitignore` ignora `data/*.db`, `.venv/`, bytecode Python e `.env`.

## Estado atual

- [x] Backend FastAPI, Uvicorn e health check.
- [x] SQLite persistente e tabela `transactions` inicializada no lifespan.
- [x] Docker/Docker Compose.
- [x] Frontend vanilla servido pelo FastAPI via `StaticFiles`.
- [x] CRUD de transactions no backend: GET, POST, PUT e DELETE.
- [x] `id` gerado por SQLite com `AUTOINCREMENT`.
- [x] `created_at` criado pelo backend usando `America/Sao_Paulo`.
- [x] GET e POST de transactions integrados à interface.
- [x] Transactions reais renderizadas na Home e em Movimentações.
- [x] Saldo, entradas e saídas calculados pela lista carregada.
- [x] Navegação, modais, cancelamento e notificações locais.
- [x] Inclusão local/em memória de metas.

## Transactions

### Campos

| Campo | Descrição |
|---|---|
| `id` | Gerado automaticamente pelo SQLite. |
| `description` | Descrição da movimentação. |
| `amount` | Valor numérico. |
| `type` | A UI oferece `income`, `expense` e `investment`. |
| `category` | Categoria opcional. |
| `transaction_date` | Data financeira escolhida pelo usuário. |
| `created_at` | Timestamp ISO gerado pelo backend em America/Sao_Paulo. |

### Rotas

| Método | Rota | Função | Resultado |
|---|---|---|---|
| GET | `/api/transactions/` | `list_transactions()` | Lista por `id DESC`. |
| POST | `/api/transactions/` | `create_transaction()` | Persiste e retorna `id` e mensagem. |
| PUT | `/api/transactions/{transaction_id}` | `update_transaction()` | Atualiza descrição, valor, tipo e categoria. |
| DELETE | `/api/transactions/{transaction_id}` | `delete_transaction()` | Remove a transaction indicada. |

A barra final faz parte do contrato: o frontend usa `/api/transactions/`.

### Fluxo integrado

```text
Formulário frontend
        ↓
POST /api/transactions/
        ↓
FastAPI
        ↓
SQLite
        ↓
GET /api/transactions/
        ↓
Home e tela Movimentações
```

O formulário envia `description`, `amount`, `type`, `category` e `transaction_date`. Após POST bem-sucedido, a interface recarrega a lista pelo GET. A Home exibe as três primeiras transactions; Movimentações usa a lista completa e filtros locais.

## Dados reais e mocks

| Área | Fonte atual | Detalhe |
|---|---|---|
| Transactions | Backend/SQLite | `loadTransactions()` faz GET; o formulário faz POST. |
| Goals | Mock | `loadGoals()` retorna `state.data.goals`; novas metas se perdem ao recarregar. |
| Cards do dashboard | Mock | `state.data.dashboard`. |
| Gastos por categoria | Mock | `state.data.categories`. |
| Evolução mensal | Mock | `state.data.monthly`. |
| `window.MockData.transactions` | Mock residual | Está definido, mas não alimenta a renderização atual. |

O estado começa assim:

```js
const state = { data: window.MockData, filter: 'all', modal: null };
```

Portanto, dashboard, goals, categories e monthly ainda dependem de `window.MockData`; transactions usam a API.

## Limitações atuais

- Não existe UI de edição ou remoção, embora PUT e DELETE existam no backend.
- PUT não recebe nem atualiza `transaction_date`.
- Não há estado visual dedicado de loading para GET/POST.
- Falhas de GET lançam erro sem `try/catch` de apresentação ao usuário.
- POST mostra erro para resposta HTTP não bem-sucedida, mas não trata rejeição de rede do `fetch`.
- O backend não valida um conjunto fechado de valores para `type`.
- O campo `note` aparece no formulário, mas não é enviado, persistido ou modelado.
- `transaction_date` é exibida sem formatação.
- Goals, dashboard, categorias e evolução mensal não têm endpoints nem persistência.

## TODO / Roadmap

- [x] Backend FastAPI.
- [x] SQLite persistente.
- [x] Docker.
- [x] Frontend servido pelo FastAPI.
- [x] CRUD backend de transactions.
- [x] POST e GET de transactions integrados à UI.
- [x] Renderização de transactions reais e cálculo de saldo.

- [ ] Integrar DELETE de transaction à UI.
- [ ] Integrar PUT de transaction à UI.
- [ ] Decidir se `transaction_date` deve ser editável no PUT.
- [ ] Adicionar tratamento visual de loading e erro.
- [ ] Validar tipos de transaction no backend.
- [ ] Definir o contrato do campo `note`.
- [ ] Implementar backend e integração para goals.
- [ ] Implementar dashboard com dados reais.
- [ ] Calcular gastos por categoria e evolução mensal reais.
- [ ] Remover ou reaproveitar mocks restantes.

## Observações técnicas

- `app/main.py` registra API e `/health` antes de montar `StaticFiles` em `/`; frontend, API e `/docs` coexistem.
- A imagem é `python:3.12-slim` e inicia com `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- Não há runtime Node.js, framework frontend nem dependência frontend externa.
- Para acesso por outro dispositivo, substitua `HOST` pelo IP/nome do servidor e mantenha a porta `8001`.
- Para detalhes de arquivos, contratos e fluxos, consulte [PROJECT_STATE.md](PROJECT_STATE.md).
