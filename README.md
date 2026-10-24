# Pissa Finance

Aplicação pessoal de finanças com FastAPI, SQLite, frontend estático (HTML/CSS/JS) e Docker. O backend serve a UI e a API na mesma origem. O Dashboard agrega `transactions`; não existe tabela de dashboard.

## Executar

```bash
docker compose up -d --build
```

- Interface: `http://HOST:8001`
- OpenAPI interativo: `http://HOST:8001/docs`
- Health: `http://HOST:8001/health`
- Persistência: `./data/pissa_finance.db` (bind mount `./data:/app/data`); host 8001 → container 8000.

## API

| Recurso | Rotas |
|---|---|
| Transactions | GET/POST `/api/transactions/`; PUT/DELETE `/api/transactions/{id}` |
| Goals | GET/POST `/api/goals/`; PUT/DELETE `/api/goals/{id}` |
| Investments | GET/POST `/api/investments/`; PUT/DELETE `/api/investments/{id}` |
| Contributions | POST `/api/investments/{id}/contributions`; PUT/DELETE `/api/investments/{id}/contributions/{movement_id}` |
| Withdrawals | POST `/api/investments/{id}/withdrawals` |
| Dashboard | GET `/api/dashboard/` |

Investments aceitam `fixed_income` e `market_investment`. A criação grava `initial_contribution`, um lançamento `investment` e os detalhes específicos. Aportes posteriores gravam `contribution` e outra transaction `investment`. Movimentos financeiros e transactions correspondentes são gravados juntos. Transactions com `investment_id` não podem ser editadas/excluídas pelas rotas genéricas (409); transactions sem vínculo continuam editáveis. O tipo `investment_withdrawal` representa dinheiro recebido num resgate, **não** receita operacional: não pode ser criado nem atribuído por POST/PUT genérico de transactions (400).

Aporte posterior e resgate aceitam o header opcional `Idempotency-Key` (1–128 caracteres). O frontend gera uma chave por operação e a guarda em `sessionStorage` até confirmar sucesso ou rejeição definitiva; após resposta ambígua, repete o mesmo payload com a mesma chave. Se não puder armazenar chave e payload, bloqueia o POST para não criar um lançamento sem retry seguro. O backend registra a chave no movimento numa coluna nullable com índice único parcial. Repetir a mesma chave com o mesmo payload devolve o movimento já registrado, mesmo se a posição foi encerrada depois; reutilizar a chave com outro investimento/tipo/valor/data/quantidade/principal retorna 409. O header é opcional para compatibilidade com clientes antigos; sem ele, o backend não deduplica repetições.

Cada investimento começa `active` (`closed_at: null`). Resgates só aceitam posições ativas, `amount > 0`, `withdrawal_date` no formato `YYYY-MM-DD` e data não anterior a movimentos existentes. Em renda fixa, `principal_amount` é obrigatório, positivo e no máximo o principal disponível; pode diferir do `amount` recebido. Em mercado, `quantity` é obrigatória, positiva e no máximo a posição atual; não envie `principal_amount`: o backend calcula `average_price × quantity`. Se `amount_invested`, `quantity` e `average_price` de uma posição de mercado estiverem inconsistentes, o resgate é recusado (409), sem descartar custo: corrija a posição antes do primeiro withdrawal pela rota PUT de investments. Resgate parcial preserva o preço médio; resgate total zera posição e fecha o investimento na `withdrawal_date`. Operações tão pequenas que não reduzem efetivamente o custo ou as unidades em SQLite REAL são rejeitadas (400), sem gerar entrada de caixa. A transaction gerada tem o mesmo valor recebido (`amount`) e a mesma data do movimento. Bancos existentes ganham as colunas novas por migração idempotente no startup.

Investimentos fechados não recebem novos aportes ou resgates (409). Aportes novos em posição parcialmente resgatada são permitidos apenas com `contribution_date` em `YYYY-MM-DD` igual ou posterior ao último withdrawal; aportes retroativos são rejeitados (400). Para não recalcular incorretamente o custo histórico após resgate, PUT de investment e PUT/DELETE de contributions ficam bloqueados (409) se a posição já tiver um withdrawal. A exclusão do investment, quando solicitada pela rota de investments, remove também **todo** o histórico e suas transactions vinculadas; é destrutiva. Não há PUT/DELETE de withdrawals neste bloco.

O Dashboard mantém o contrato `income`, `expenses`, `invested`, `balance`, `categories`, `monthly`. Agora `balance = income - expenses - invested + resgates`; cada resgate soma no mês de `transaction_date`, sem aumentar `income` ou `invested`. `categories` inclui apenas expenses.

**Frontend:** Home, Dashboard, Transactions, Goals e Investments estão integrados ao backend. A aba Investments lista/cria posições, registra aportes/resgates e exclui cadastros por engano; posições fechadas não oferecem aporte/resgate. `investment_withdrawal` aparece como entrada de caixa positiva em Movimentações sem aumentar `income`; resgates são detalhados na transaction ligada, sem interface de histórico de movements. O browser gera/reutiliza `Idempotency-Key` durante tentativas ambíguas; o backend mantém a chave em `investment_movements` para deduplicar retry do mesmo payload. O frontend não implementa edição de posição/movimentos nem integra fontes externas ou rentabilidade.

## Roteiro manual em `/docs`

Use **Try it out** em cada endpoint (datas e valores de exemplo; crie investimentos de teste em banco descartável). O `id` da criação substitui `{id}` nas chamadas seguintes. Use GET `/api/investments/` para conferir `amount_invested`, `status`, `closed_at` e `details`; GET `/api/transactions/` para achar `transaction_id` e conferir o lançamento. Os movimentos ainda não têm endpoint GET: para inspecionar `principal_amount`/`movement_type`, consulte `SELECT * FROM investment_movements WHERE investment_id = <id> ORDER BY id;` diretamente no SQLite de teste. As etapas b e d usam o mesmo ID criado nas etapas a e c respectivamente.

1. **a) Fixed parcial:** POST `/api/investments/` com `{"name":"CDB teste","investment_type":"fixed_income","amount_invested":1000,"started_at":"2026-10-01","rate_type":"CDI"}`. Depois POST `/api/investments/{id}/withdrawals` com `{"amount":450,"withdrawal_date":"2026-10-22","principal_amount":400}`. Confira principal restante 600, `status=active`, movement `withdrawal` e transaction `investment_withdrawal` de 450.
2. **b) Fixed total:** no mesmo `{id}`, POST withdrawals com `{"amount":620,"withdrawal_date":"2026-10-23","principal_amount":600}`. Confira principal 0, `status=closed`, `closed_at=2026-10-23`.
3. **c) Market parcial:** POST `/api/investments/` com `{"name":"Bitcoin teste","investment_type":"market_investment","amount_invested":1000,"started_at":"2026-10-01","asset_type":"crypto","symbol":"BTC","quantity":10,"average_price":100}`. POST withdrawals com `{"amount":350,"withdrawal_date":"2026-10-22","quantity":3}`. Confira principal 700, quantidade 7, preço médio 100; movimento com `principal_amount=300` e transaction de 350.
4. **d) Market total:** no ID de c, POST withdrawals com `{"amount":750,"withdrawal_date":"2026-10-23","quantity":7}`. Confira principal, quantidade e preço médio em 0, `status=closed` e `closed_at=2026-10-23`.
5. **e) Aporte em closed:** POST `/api/investments/{id}/contributions` (ID da etapa b ou d) com `{"amount":50,"contribution_date":"2026-10-24"}`. Esperado: **409**, sem movimento/transaction novos.
6. **f) Transaction vinculada:** GET `/api/transactions/`, copie um `id` com `investment_id` não nulo; PUT `/api/transactions/{id}` com `{"description":"Tentativa","amount":1,"type":"income","transaction_date":"2026-10-24"}` e DELETE `/api/transactions/{id}`. Ambos devem devolver **409**, mantendo o lançamento intacto.

## Testes automatizados

Com Python 3.12 e `requirements.txt` instalados, adicione `httpx2` no ambiente **de teste** (requerido pelo TestClient desta versão do Starlette) e execute `python -m unittest discover -s tests -v` (os testes usam bancos SQLite temporários). Alternativa isolada com Docker:

```bash
docker build -t pissa-finance-test-local .
docker run --rm -v "$PWD:/workspace" -w /workspace pissa-finance-test-local \
  sh -c 'pip install -q httpx2 && python -m unittest discover -s tests -v'
```

Consulte [PROJECT_STATE.md](PROJECT_STATE.md) para schema, limites atuais e decisões técnicas.
