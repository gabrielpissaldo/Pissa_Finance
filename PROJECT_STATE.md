# Pissa Finance — estado atual do projeto

Data da análise: 13 de setembro de 2026. Este documento descreve o código e o banco presentes no repositório neste momento; não propõe que o estado atual esteja funcional em todos os fluxos.

## 1. Estrutura do projeto

\`\`\`text
PissaFinance/
├── .gitignore                         # Ignora .venv, bytecode, .env e data/*.db
├── Dockerfile                         # Imagem Python/FastAPI
├── README.md                          # Instruções iniciais (a porta citada ainda é 8080)
├── docker-compose.yml                 # Serviço e persistência local do banco
├── requirements.txt                   # Dependências Python fixadas
├── data/
│   └── pissa_finance.db               # Banco SQLite local persistido (ignorado pelo Git)
├── app/
│   ├── __init__.py                    # Marca o pacote Python
│   ├── database.py                    # Conexão e criação da tabela SQLite
│   ├── main.py                        # Aplicação FastAPI, lifespan e StaticFiles
│   └── routes/
│       ├── __init__.py                # Marca o subpacote de rotas
│       └── transactions.py            # Models Pydantic e CRUD de transactions
└── frontend/
    ├── index.html                     # Página única, telas, navegação, modal e aviso
    ├── css/
    │   ├── style.css                  # Tema dark, layout, cards, listas, gráficos e modal
    │   ├── responsive.css             # Breakpoints mobile/desktop
    │   └── notification.css           # Toast, ações do formulário e regra hidden do modal
    └── js/
        ├── mock-data.js               # window.MockData: dashboard, goals, transações e gráficos
        └── app.js                     # Estado, renderização, eventos e fetch parcial
\`\`\`

## 2. Backend atual

O backend usa **FastAPI 0.141.1**, SQLite da biblioteca padrão e Pydantic 2.13.5. A entrada é \`app/main.py\`.

\`main.py\` instancia \`FastAPI(title="Pissa Finance", lifespan=lifespan)\`. O lifespan chama \`init_db()\` antes de a aplicação aceitar requisições e não tem ação após \`yield\`. O router de transactions é incluído antes do mount de arquivos estáticos.

Em \`app/database.py\`, \`DATABASE_PATH\` é fixo em \`/app/data/pissa_finance.db\`. Esse é o caminho **dentro do container**. Pelo Compose, ele corresponde a \`/home/gabriel/PissaFinance/data/pissa_finance.db\` no host atual (ou \`./data/pissa_finance.db\` relativo à raiz do projeto).

Funções de banco:

| Função | Responsabilidade |
|---|---|
| \`get_connection()\` | Abre conexão SQLite em \`DATABASE_PATH\` e configura \`sqlite3.Row\`, permitindo converter linhas com \`dict(row)\`. |
| \`init_db()\` | Cria \`transactions\` se ainda não existir, confirma a transação e fecha a conexão. |

### Schema real atual

O arquivo \`data/pissa_finance.db\` foi inspecionado com \`PRAGMA table_info(transactions)\`:

\`\`\`sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    type TEXT NOT NULL,
    category TEXT,
    created_at TEXT NOT NULL
);
\`\`\`

| Campo | Tipo | Obrigatório | Origem atual |
|---|---:|---:|---|
| \`id\` | INTEGER | chave primária | Gerado por SQLite (\`AUTOINCREMENT\`) |
| \`description\` | TEXT | sim | Request de create/update |
| \`amount\` | REAL | sim | Request de create/update |
| \`type\` | TEXT | sim | Request de create/update |
| \`category\` | TEXT | não | Request de create/update |
| \`created_at\` | TEXT | sim | Gerado no create com ISO 8601 em America/Sao_Paulo |

Não há \`transaction_date\` na tabela real nem no SQL de \`init_db()\`.

### Router e models

Há um router, declarado em \`app/routes/transactions.py\`, com prefixo \`/api/transactions\` e tag OpenAPI \`transactions\`.

\`\`\`text
TransactionCreate
  description: str
  amount: float
  type: str
  category: str | None = None
  transaction_date: str

TransactionUpdate
  description: str
  amount: float
  type: str
  category: str | None = None
\`\`\`

Não há enum/validação de domínio para \`type\`; qualquer string aceita pelo Pydantic é válida.

### Endpoints implementados

#### GET /health

\`\`\`text
Função: health()
Request: nenhum
Response atual: {"status": "healthy"}
\`\`\`

#### POST /api/transactions/

\`\`\`text
Função: create_transaction(transaction: TransactionCreate)
Body esperado:
{
  "description": "Mercado",
  "amount": 120.5,
  "type": "expense",
  "category": "Alimentação",
  "transaction_date": "2026-09-13"
}

Resposta prevista pelo código:
{
  "id": 1,
  "message": "Transaction created"
}
\`\`\`

A função gera \`created_at\` com \`datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()\`, executa INSERT, usa \`cursor.lastrowid\`, confirma e fecha a conexão.

**Estado observável importante:** o INSERT lista seis colunas (\`description\`, \`amount\`, \`type\`, \`category\`, \`transaction_date\`, \`created_at\`), mas contém somente cinco placeholders no \`VALUES\`. Além disso, o schema real não possui \`transaction_date\`. Portanto o POST não está operacional contra o banco atual; o erro SQLite não é capturado pela rota e tende a virar resposta 500.

#### GET /api/transactions/

\`\`\`text
Função: list_transactions()
Request: nenhum
Response atual: array de objetos de linha
\`\`\`

Exemplo de formato para uma linha existente:

\`\`\`json
[
  {
    "id": 1,
    "description": "Mercado",
    "amount": 120.5,
    "type": "expense",
    "category": "Alimentação",
    "created_at": "2026-09-13T10:00:00-03:00"
  }
]
\`\`\`

Executa \`SELECT * FROM transactions ORDER BY id DESC\`, converte cada \`sqlite3.Row\` em dicionário e retorna a lista. Não há paginação, filtro, ordenação escolhida pelo cliente nem tratamento local de erro.

#### PUT /api/transactions/{transaction_id}

\`\`\`text
Função: update_transaction(transaction_id: int, transaction: TransactionUpdate)
Path: transaction_id inteiro
Body esperado:
{
  "description": "Mercado mensal",
  "amount": 130.0,
  "type": "expense",
  "category": "Alimentação"
}

Resposta de sucesso:
{ "message": "Transaction updated" }

Resposta se nenhum id for atualizado:
HTTP 404
{ "detail": "Transaction not found" }
\`\`\`

Atualiza apenas \`description\`, \`amount\`, \`type\` e \`category\`. Não atualiza \`created_at\` e não aceita nem atualiza \`transaction_date\`.

#### DELETE /api/transactions/{transaction_id}

\`\`\`text
Função: delete_transaction(transaction_id: int)
Path: transaction_id inteiro
Body: nenhum
Resposta de sucesso:
{ "message": "Transaction deleted" }

Resposta se nenhum id for removido:
HTTP 404
{ "detail": "Transaction not found" }
\`\`\`

Executa DELETE por \`id\`, confirma a transação e só então testa \`cursor.rowcount\`. Em ambos os ramos a conexão é fechada.

### Tratamento de erros

- Pydantic/FastAPI devolve 422 automaticamente para body ausente, campos obrigatórios ausentes ou tipos inválidos nos models.
- PUT e DELETE convertem id inexistente em 404 com \`HTTPException\`.
- Erros de SQLite, conexão ou SQL inválido não são capturados e resultam em erro interno padrão.
- GET não possui tratamento de erro próprio.

## 3. Fluxo atual de transactions

### CREATE

O backend pretende receber \`description\`, \`amount\`, \`type\`, \`category\` e \`transaction_date\`; gera \`created_at\`; e depende do SQLite para gerar \`id\`. Na implementação presente, o INSERT está divergente do banco e não completa.

No frontend, o submit **não faz POST**. Ele insere apenas no array em memória:

\`\`\`js
state.data.transactions.unshift({
  id: Date.now(),
  description: form.get('description'),
  category: form.get('category'),
  amount: parseAmount(form.get('amount')),
  type: form.get('type'),
  date: 'Hoje'
});
\`\`\`

Esse objeto local não tem \`created_at\` e não usa os valores de \`date\` ou \`note\` do formulário.

### READ

O backend lista todas as linhas por \`id DESC\`. O frontend já chama GET por meio de \`loadTransactions()\`, que usa \`fetch('/api/transactions')\`. Home e tela Movimentações usam esse resultado; portanto a listagem não usa \`state.data.transactions\` na renderização atual.

### UPDATE

Existe endpoint PUT e model \`TransactionUpdate\`, mas não há UI, fetch ou botão de edição no frontend. A data de criação não é alterada.

### DELETE

Existe endpoint DELETE, mas não há UI, fetch ou botão de remoção no frontend.

### Campos, geração e divergências

| Conceito | Frontend/form atual | Frontend em memória | Backend/model | Banco real |
|---|---|---|---|---|
| Identificador | nenhum input | \`Date.now()\` | path \`transaction_id\` para PUT/DELETE | \`id AUTOINCREMENT\` |
| Descrição | \`description\` | \`description\` | \`description\` | \`description\` |
| Valor | \`amount\` texto, convertido | \`amount\` number | \`amount\` float | \`amount\` REAL |
| Tipo | \`type\` | \`type\` | \`type\` | \`type\` TEXT |
| Categoria | \`category\` | \`category\` | \`category\` opcional | \`category\` nullable |
| Data financeira | input \`date\` | descartada; objeto usa \`date: "Hoje"\` | \`transaction_date\` obrigatório no create | inexistente |
| Data de criação | nenhum input | inexistente | \`created_at\` gerado | \`created_at\` TEXT NOT NULL |
| Observação | \`note\` | descartada | inexistente | inexistente |

Outras diferenças:

- \`transactionMarkup()\` exibe \`item.created_at\`; os mocks têm \`date\`. Assim, se algum mock fosse entregue diretamente à função, a data renderizada seria \`undefined\`.
- O GET real retorna \`created_at\`, compatível com a função de marcação, porém seu texto é ISO completo, sem formatação para leitura.
- \`transaction_date\` é exigido pelo model de create, mas não existe no schema e é ignorado pelo update.

## 4. Frontend atual

### HTML e CSS

\`frontend/index.html\` é uma SPA estática com quatro \`section.screen\`: \`home\`, \`transactions\`, \`goals\` e \`dashboard\`. Há uma única navegação inferior mobile, um toast inicialmente \`hidden\`, e um único modal/backdrop inicialmente \`hidden\`. O formulário dentro de \`#entry-form\` é preenchido dinamicamente por JavaScript.

\`style.css\` contém o tema dark mobile-first, cards, listas, indicadores, barras de progresso, gráficos CSS, navegação fixa e o bottom sheet. \`responsive.css\` adapta em \`min-width:700px\` para navegação lateral e modal centralizado; também contém pequeno ajuste abaixo de 350 px. \`notification.css\` contém aparência de sucesso/erro, botão de fechar aviso, ações Cancelar/Adicionar e a regra \`.modal-backdrop[hidden] { display: none !important; }\`.

As metas de viewport e Apple web app estão em \`index.html\`; o padding usa \`env(safe-area-inset-bottom)\` nos estilos principais para iPhone.

### Dados e estado

\`mock-data.js\` declara \`window.MockData\` com:

- \`dashboard\`: \`netWorth\`, \`monthlyChange\`, \`saved\`, \`earnings\`, \`expenses\`, \`income\`, \`savingRate\`;
- \`goals\`: metas com \`id\`, \`name\`, \`current\`, \`target\`, \`color\`;
- \`transactions\`: exemplos com \`id\`, \`description\`, \`category\`, \`amount\`, \`type\`, \`date\`;
- \`categories\`: valores e cores do donut;
- \`monthly\`: pontos para o gráfico de evolução.

No início de \`app.js\`:

\`\`\`js
const state = { data: window.MockData, filter: 'all', modal: null };
\`\`\`

\`state.data.dashboard\`, \`state.data.goals\`, \`state.data.categories\` e \`state.data.monthly\` são efetivamente mocks usados pela interface. \`state.data.transactions\` é mutado pelo formulário local, mas não é usado por \`loadTransactions()\` atualmente.

| Função de carga | Fonte atual | Consumidores |
|---|---|---|
| \`loadDashboard()\` | \`state.data.dashboard\` mockado | \`renderHome()\`, \`renderTransactions()\` (valor descartado), \`renderDashboard()\` lê state direto |
| \`loadTransactions()\` | GET \`/api/transactions\` | \`renderHome()\`, \`renderTransactions()\` |
| \`loadGoals()\` | \`state.data.goals\` mockado | \`renderHome()\`, \`renderGoals()\` |

### Renderização

- \`renderHome()\`: atualiza patrimônio e cards pelo dashboard mock; metas pelos mocks; últimas três transactions pelo GET.
- \`renderTransactions()\`: calcula recebimentos, saídas e saldo a partir do GET; aplica \`state.filter\`; escreve \`#transaction-list\`.
- \`renderGoals()\`: renderiza metas mockadas em \`#goal-list\`.
- \`renderDashboard()\`: renderiza cards, donut/legenda e gráfico de barras exclusivamente dos mocks.
- \`goalMarkup(goal)\`: cria card de meta e calcula porcentagem e restante.
- \`transactionMarkup(item)\`: cria cada item de movimentação.

O código chama \`renderHome()\`, \`renderTransactions()\`, \`renderGoals()\` e \`renderDashboard()\` no carregamento. As duas primeiras são async e seus retornos não são aguardados nem possuem \`try/catch\` no chamador.

### Navegação, filtros, modal e botões

- \`navigate(screen)\` mostra somente a section cujo \`id\` coincide e atualiza \`.nav-item.active\`.
- Os botões \`data-navigate\` da Home chamam \`navigate()\`; os botões \`data-screen\` da barra inferior fazem o mesmo.
- Os filtros possuem \`data-filter\`; o handler atribui \`state.filter\`, troca a classe ativa e chama \`renderTransactions()\`.
- \`openModal(type)\` define \`state.modal\`, troca título, monta o form e remove \`hidden\` de \`#modal-backdrop\`.
- \`closeModal()\` adiciona \`hidden\` de volta e limpa \`state.modal\`. X, Cancelar dinâmico, backdrop e Escape podem fechá-lo.
- O botão de configurações possui \`data-notification-message="Configurações em breve"\` e abre um aviso local.

### Notificações

\`showNotification(message, type = 'success')\` é exposta como \`window.showNotification\`. Ela aceita \`success\` e \`error\` (outros valores se tornam \`success\`), atualiza texto e classe, torna o toast visível e agenda ocultação em 3 segundos. \`clearTimeout(notificationTimer)\` impede timers concorrentes. \`hideNotification()\`, exposta como \`window.hideNotification\`, limpa o timer e oculta o componente. O botão X do toast e Escape chamam essa função.

## 5. Fluxo de estado do frontend

\`\`\`text
window.MockData
       ↓
state.data
       ↓                         ┌───────────────────────────────────────┐
loadDashboard() ────────────────→│ state.data.dashboard (mock)           │
loadGoals() ────────────────────→│ state.data.goals (mock)               │
loadTransactions() ─────────────→│ fetch('/api/transactions')            │
       ↓                         └───────────────────────────────────────┘
renderHome / renderTransactions / renderGoals / renderDashboard
       ↓
DOM
\`\`\`

Leem \`state.data\`: \`loadDashboard\`, \`loadGoals\`, \`renderDashboard\`, \`formMarkup\` indiretamente não lê dados, e o handler de submit lê/muta coleções.

Mutações diretas encontradas:

| Alvo | Onde | Quando |
|---|---|---|
| \`state.data.transactions\` | handler de submit | Ao submeter uma movimentação: \`unshift\` |
| \`state.data.goals\` | handler de submit | Ao submeter uma meta: \`unshift\` |
| \`state.data.dashboard\` | nenhuma | Não há alteração atual |
| \`state.filter\` | handler de clique de filtro | Ao escolher filtro |
| \`state.modal\` | \`openModal\` / \`closeModal\` | Abertura/fechamento |

Como \`loadTransactions()\` busca a API em toda renderização, o \`unshift\` local de transactions não é a fonte usada para a lista imediatamente após o submit. Já goals recém-inseridas são renderizadas porque \`loadGoals()\` lê o array em memória.

## 6. Formulário de movimentação

O modal é único; \`formMarkup('transaction')\` produz:

| Campo | Name | Tipo HTML | Uso atual no submit |
|---|---|---|---|
| Tipo | \`type\` | select: income/expense/investment | usado |
| Descrição | \`description\` | input | usado |
| Valor | \`amount\` | input decimal | usado após \`parseAmount()\` |
| Categoria | \`category\` | input | usado |
| Data | \`date\` | date, default 2026-09-10 | não usado |
| Observação | \`note\` | textarea | não usado |
| Cancelar | sem name | button | fecha modal |
| Adicionar | submit | button | insere localmente |

No submit, \`FormData\` é criado, \`isGoal\` é determinado, e para transaction o objeto local mostrado na seção 3 é adicionado. Depois são chamadas as quatro funções de renderização, o modal fecha e há toast de sucesso. Não existe \`fetch\` POST, payload JSON nem comunicação de erro com o backend nesse handler.

## 7. Renderização de transactions

\`transactionMarkup(item)\` espera este formato mínimo:

\`\`\`js
{
  description: string,
  type: 'income' | 'expense' | 'investment',
  category: string | null | undefined,
  amount: number,
  created_at: string
}
\`\`\`

- \`money(value)\` chama \`toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })\`.
- Para \`income\`, o sinal é \`+\`; para qualquer outro tipo, \`-\`.
- \`transactionIcon()\` retorna ↓, ↑ ou ◇; \`transactionLabel()\` retorna Entrada, Saída ou Investimento.
- A categoria usa \`item.category || 'Sem categoria'\`.
- A data exibida é literalmente \`item.created_at\`; não há conversão de ISO.
- \`renderHome()\` usa \`transactions.slice(0, 3)\`; como o GET ordena id descendente, mostra as três linhas de id mais alto.

## 8. Integração existente com backend

Há um único fetch:

\`\`\`text
Arquivo: frontend/js/app.js
Função: loadTransactions()
Endpoint: /api/transactions
Método: GET (padrão do fetch)
Tratamento: se response.ok for falso, lança Error('Erro ao carregar transações');
Uso: retorno é consumido por renderHome() e renderTransactions()
\`\`\`

Não há \`try/catch\` nessa função nem nos renders. Não existem fetches POST, PUT ou DELETE no frontend. Logo, a integração de transactions é somente leitura parcial; dashboard e goals não possuem integração.

## 9. StaticFiles e coexistência de rotas

O mount ocorre em \`main.py\`:

\`\`\`py
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
\`\`\`

O diretório \`frontend/\` é servido na raiz. Com \`html=True\`, a raiz pode entregar \`frontend/index.html\`. Como router de transactions e \`/health\` são registrados antes do mount catch-all, \`/api/transactions/... \` e \`/health\` são resolvidos antes dos arquivos estáticos. A documentação automática do FastAPI (\`/docs\`, e rotas associadas) é registrada pela inicialização do FastAPI e também coexistirá com o mount raiz.

## 10. Docker

| Item | Estado |
|---|---|
| Imagem base | \`python:3.12-slim\` |
| WORKDIR | \`/app\` |
| Dependências | Copia \`requirements.txt\` e roda \`pip install --no-cache-dir -r requirements.txt\` |
| Código copiado | \`app/\` para \`/app/app\`; \`frontend/\` para \`/app/frontend\` |
| Banco no build | \`RUN mkdir -p /app/data\` |
| Comando | \`uvicorn app.main:app --host 0.0.0.0 --port 8000\` |
| Porta interna | 8000 |
| Porta publicada | host 8001 → container 8000 |
| Serviço/contêiner | serviço \`pissa-finance\`; \`container_name: pissa-finance\` |
| Volume | bind \`./data:/app/data\` |
| Persistência | SQLite fica no host em \`data/\`; não é volume nomeado |
| Rede | rede padrão do Compose, efetivamente \`pissafinance_default\` |
| Caminho real analisado | \`/home/gabriel/PissaFinance\` |

O README ainda instrui acesso na porta 8080, o que diverge do Compose presente (8001).

## 11. Pontos pendentes para remover mocks

1. Resolver a divergência de schema/model/INSERT de \`transaction_date\` e placeholders do POST.
2. Definir contrato único para data: \`transaction_date\`, \`created_at\` e/ou nome \`date\`.
3. Ligar formulário a POST e renderizar a resposta ou recarregar a lista.
4. Implementar UI e fetch para DELETE.
5. Implementar UI e fetch para PUT.
6. Adicionar loading, erro e empty state para o GET de transactions.
7. Decidir fonte de verdade de \`state.data.transactions\` após integração.
8. Implementar backend e endpoints de goals, substituindo \`state.data.goals\`.
9. Implementar dashboard derivado de dados reais e substituir \`dashboard\`, \`categories\` e \`monthly\` mockados.
10. Definir uso ou remoção de \`note\`, hoje existente apenas no formulário.
11. Ajustar README para porta 8001 e servidor FastAPI atual.

## 12. Plano de integração sugerido

1. Corrigir e estabilizar o contrato/schema de transaction, antes de qualquer novo fetch.
2. Validar GET com lista vazia, lista real e formato de \`created_at\`.
3. Definir a conversão do formulário (\`date\`/nota) para o contrato final.
4. Conectar POST e atualizar a UI a partir do objeto retornado ou de um novo GET.
5. Criar feedback de loading/erro para GET e POST.
6. Adicionar ação e confirmação visual para DELETE, então integrar DELETE.
7. Criar tela/form de edição e integrar PUT.
8. Só depois definir endpoints e contratos para goals.
9. Por fim, derivar dashboard de transactions/goals ou criar endpoint específico.

## 13. Trechos relevantes atuais

### app/main.py

\`\`\`py
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Pissa Finance", lifespan=lifespan)
app.include_router(transactions_router)

@app.get("/health")
def health():
    return {"status": "healthy"}

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
\`\`\`

### app/database.py

\`\`\`py
DATABASE_PATH = Path("/app/data/pissa_finance.db")

def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection

def init_db():
    connection = get_connection()
    connection.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            category TEXT,
            created_at TEXT NOT NULL
        )
    """)
    connection.commit()
    connection.close()
\`\`\`

### app/routes/transactions.py — CRUD

\`\`\`py
@router.post("/")
def create_transaction(transaction: TransactionCreate):
    created_at = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()
    cursor = connection.execute("""
        INSERT INTO transactions (
            description, amount, type, category, transaction_date, created_at
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        transaction.description, transaction.amount, transaction.type,
        transaction.category, transaction.transaction_date, created_at
    ))
    return {"id": cursor.lastrowid, "message": "Transaction created"}

@router.get("/")
def list_transactions():
    rows = connection.execute(
        "SELECT * FROM transactions ORDER BY id DESC"
    ).fetchall()
    return [dict(row) for row in rows]
\`\`\`

PUT atualiza \`description\`, \`amount\`, \`type\` e \`category\`; DELETE remove pela chave \`id\`; ambos retornam 404 com \`{"detail": "Transaction not found"}\` quando \`cursor.rowcount == 0\`.

### Estado e carregamento de transactions

\`\`\`js
const state = { data: window.MockData, filter: 'all', modal: null };

async function loadTransactions() {
  const response = await fetch('/api/transactions');
  if (!response.ok) throw new Error('Erro ao carregar transações');
  return await response.json();
}
\`\`\`

### transactionMarkup

\`\`\`js
function transactionMarkup(item) {
  const sign = item.type === 'income' ? '+' : '-';
  return \`
  <article class="transaction \${item.type}">
    <div class="transaction-icon">\${transactionIcon(item.type)}</div>
    <div class="transaction-main">
      <strong>\${item.description}</strong>
      <span>\${transactionLabel(item.type)} • \${item.category || 'Sem categoria'}</span>
    </div>
    <div class="transaction-value">
      <strong>\${sign} \${money(item.amount)}</strong>
      <span>\${item.created_at}</span>
    </div>
  </article>\`;
}
\`\`\`

### Handler de submit

\`\`\`js
$('#entry-form').addEventListener('submit', event => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const isGoal = state.modal === 'goal';

  if (isGoal) {
    state.data.goals.unshift({ /* dados do formulário */ });
  } else {
    state.data.transactions.unshift({
      id: Date.now(),
      description: form.get('description'),
      category: form.get('category'),
      amount: parseAmount(form.get('amount')),
      type: form.get('type'),
      date: 'Hoje'
    });
  }

  renderHome(); renderTransactions(); renderGoals(); renderDashboard();
  closeModal();
  showNotification(isGoal ? 'Meta adicionada com sucesso' : 'Movimentação adicionada com sucesso', 'success');
});
\`\`\`

### Configuração Docker relevante

\`\`\`dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY frontend ./frontend
RUN mkdir -p /app/data
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
\`\`\`

\`\`\`yaml
services:
  pissa-finance:
    build: .
    container_name: pissa-finance
    ports:
      - "8001:8000"
    volumes:
      - ./data:/app/data
\`\`\`
