# Pissa Finance — estado técnico

Estado do código após o bloco de valorização e rentabilidade de investimentos. Este arquivo descreve o repositório; não afirma implantação em nenhuma máquina externa.

## Arquitetura e execução

FastAPI (Python 3.12 no Docker) serve `/api/*`, `/docs`, `/health` e frontend estático. SQLite fica em `/app/data/pissa_finance.db` no container, persistido em `./data/pissa_finance.db` no host. `init_db()` roda no lifespan. Porta 8001 do host → 8000 do container. Dashboard é leitura agregada de `transactions`, sem tabela própria.

## Schema (colunas relevantes)

- `transactions`: `id`, `description`, `amount`, `type`, `category`, `investment_id` nullable, `transaction_date`, `created_at`. Os tipos usados são `income`, `expense`, `investment` e `investment_withdrawal` (a coluna type continua TEXT livre).
- `goals`: `id`, `name`, `target_amount`, `current_amount`, `deadline`, `created_at`.
- `investments`: `id`, `name`, `investment_type`, `amount_invested`, `status TEXT NOT NULL DEFAULT 'active'`, `closed_at TEXT` nullable, `started_at`, `created_at`. Estados controlados pelo backend: `active` e `closed`.
- `fixed_income_details`: `investment_id` UNIQUE, `rate_type`, `rate_modifier`, `fixed_rate`, `maturity_date`.
- `market_investment_details`: `investment_id` UNIQUE, `asset_type`, `symbol`, `quantity`, `average_price`.
- `investment_movements`: `id`, `investment_id`, `transaction_id`, `movement_type`, `amount`, `principal_amount REAL` nullable, `quantity`, `idempotency_key TEXT` nullable, `movement_date`, `created_at`. Movimentos: `initial_contribution`, `contribution`, `withdrawal`; índice único parcial em `idempotency_key` (NULL permitido para históricos/clientes antigos).

`amount` do withdrawal é o dinheiro recebido no caixa; `principal_amount` é o custo removido da posição; `quantity` é a quantidade vendida em mercado. O `principal_amount` dos movimentos antigos de aporte permanece NULL. `created_at` é ISO 8601 em `America/Sao_Paulo`.

As tabelas são criadas se ausentes. Para bancos existentes, `init_db()` consulta `PRAGMA table_info` e adiciona apenas as colunas ausentes (`status`, `closed_at`, `principal_amount`, `idempotency_key`), depois cria o índice único parcial idempotente e faz commit. Executá-lo novamente não duplica colunas/índice; registros antigos ficam `active`, com `closed_at`, `principal_amount` e `idempotency_key` NULL. A tabela transactions deste repositório já possui `investment_id`; esta migração não modifica versões ainda mais antigas que não o possuam.

`GET /api/investments/` calcula e anexa `current_value`, `unrealized_profit_loss`, `unrealized_return_percent`, `realized_profit_loss`, `total_profit_loss`, `total_return_percent`, `valuation_status` e `valuation_as_of`; não há nova tabela nem escrita no GET. `amount_invested` continua sendo o custo/principal líquido. Para `prefixed`, cada aporte rende desde a data do movimento, com taxa efetiva anual ACT/365 e accrual limitado a `maturity_date`; o principal resgatado e o valor de caixa recebido são reduzidos proporcionalmente nos lotes. `realized_profit_loss` soma `amount - principal_amount` dos withdrawals. `unrealized_profit_loss = current_value - amount_invested`; `total_profit_loss = realized + unrealized`; `total_return_percent = total_profit_loss / gross_contributions × 100` (retorno acumulado simples, não anualizado). Posição encerrada tem valor atual estimado 0 e P/L não realizado 0. CDI, SELIC e IPCA sem série externa retornam `pending_external_index` e valores dependentes nulos; mercado aberto sem preço retorna `pending_quote` e não inventa current value.

## Rotas e regras

| Método | Rota | Efeito |
|---|---|---|
| GET/POST | `/api/investments/` | Listar com `details` / criar posição, movimento inicial e transaction de aporte. |
| PUT/DELETE | `/api/investments/{id}` | Atualizar investimento (sem withdrawals) / excluir investimento e todas as transactions vinculadas; movimentos e detalhes são removidos por cascade. |
| POST | `/api/investments/{id}/contributions` | Aportar em posição active; aceita header `Idempotency-Key` opcional. |
| PUT/DELETE | `/api/investments/{id}/contributions/{movement_id}` | Alterar/remover aporte posterior, somente se ainda não houver withdrawal. |
| POST | `/api/investments/{id}/withdrawals` | Resgatar parcialmente ou totalmente; aceita header `Idempotency-Key` opcional. |
| GET/POST | `/api/transactions/` | Listar/criar transactions avulsas; POST não aceita `investment_withdrawal`. |
| PUT/DELETE | `/api/transactions/{id}` | Operar transaction avulsa; 409 quando `investment_id` não é NULL; PUT avulso não pode definir `investment_withdrawal`. |
| GET/POST/PUT/DELETE | `/api/goals/`, `/api/goals/{id}` | CRUD de metas. |
| GET | `/api/dashboard/` | Agregações. |

Withdrawal recebe `amount` (positivo), `withdrawal_date` (`YYYY-MM-DD`, não anterior aos movimentos existentes), `quantity` opcional e `principal_amount` opcional. Em renda fixa, `principal_amount > 0` é obrigatório e não excede `amount_invested`; `quantity` não se aplica. Em mercado, `quantity > 0` é obrigatória e não excede a quantidade em carteira; o cliente não fornece principal, calculado como `average_price × quantity`. Antes do resgate, o backend confere consistência entre custo total, quantidade e preço médio (tolerância relativa de ponto flutuante); uma posição inconsistente recebe 409 para que o custo não desapareça no encerramento. Ela deve ser corrigida pelo PUT de investments **antes** do primeiro withdrawal. Resgate parcial reduz custo e unidades sem mudar preço médio; total zera principal, unidades e preço médio. Resgates cujo principal/unidades forem menores que a precisão de `REAL` para reduzir efetivamente a posição são rejeitados (400). Ao zerar posição, define `status=closed` e `closed_at=withdrawal_date`. Resgate fechado ou aporte novo em fechado retorna 409; investimento ausente retorna 404; valores ou datas fora das regras retornam 400 (payload incompleto: 422 do Pydantic). Aportes posteriores a um withdrawal só aceitam data válida igual ou posterior ao último resgate.

O resgate registra movement `withdrawal` (`amount`, `principal_amount`, `quantity`, `movement_date`) e transaction `investment_withdrawal` (`amount` recebido, `investment_id`, descrição `Resgate de <nome>`, data do resgate). São feitas as alterações da posição, detalhes, transaction e movement numa única transação SQLite (`BEGIN IMMEDIATE`, commit/rollback/finally), para não persistir estado parcial e serializar operações concorrentes. O header `Idempotency-Key` opcional é validado (1–128 caracteres) e gravado no movimento; uma repetição com a mesma chave e payload retorna sucesso sem nova mutation, inclusive se a operação original encerrou a posição. Reutilizar a chave com payload diferente retorna 409. O PUT/DELETE genérico de transactions vinculadas é bloqueado; o backend das rotas de investments ainda manipula suas próprias transactions diretamente.

O PUT de investment e PUT/DELETE de contributions após **qualquer** withdrawal foram bloqueados para não reconstruir erroneamente posição/custo a partir de aportes sem considerar saídas; não existe edição/exclusão individual de withdrawal neste bloco. A exclusão da posição inteira é destrutiva e remove todas as transactions com o respectivo `investment_id`, inclusive saídas.

## Dashboard e frontend

O contrato mantém `income`, `expenses`, `invested`, `balance`, `categories`, `monthly`. `income` soma só `income`; `expenses`, só `expense`; `invested`, só `investment`; resgates entram **positivamente** em `balance` e `monthly`, sem virar `income`. Saldo = income − expenses − invested + withdrawals. `categories` agrupa apenas expenses; `monthly` apresenta os últimos seis meses por `transaction_date`.

A UI de Investments lista/cria posições, registra aportes/resgates, exibe custo atual, valor estimado, rendimentos realizados/não realizados e rentabilidade total somente quando disponíveis. Para CDI/SELIC/IPCA sem índice e mercado sem cotação, mostra status pendente sem tratar ausência como zero. Posições `closed` não oferecem aporte/resgate e permitem excluir cadastro sob confirmação explícita. Home/Dashboard/Transactions/Goals permanecem integrados. `investment_withdrawal` é apresentado como resgate com sinal positivo; não entra em income nem no cálculo local do saldo. Aporte/resgate usam chave idempotente guardada com o payload em `sessionStorage` até confirmação; se o armazenamento falhar, o POST é bloqueado. A UI não oferece edição de investimentos/movimentos, histórico de movements, cotações, APIs de índice externo, dividendos ou projeções.

## Verificação e limites

`tests/test_investment_withdrawals.py` usa FastAPI TestClient e SQLite temporário. `tests/test_investment_valuation.py` cobre prefixado sem resgate, contribuições em datas distintas com resgate parcial e P/L realizado, encerramento, teto de vencimento, lucro realizado de mercado sem cotação, estados pendentes de CDI/SELIC/IPCA e invariância do Dashboard/ledger. A suíte também cobre migração idempotente, replay de operações, conflitos de chave, resgates parciais/totais, rejeições, proteção de transactions vinculadas, exclusão e rollback. Executar com `python -m unittest discover -s tests -v` em Python 3.12 com dependências e `httpx2`; roteiro manual com payloads no [README.md](README.md).

Limites preexistentes: payloads de criação/edição não fazem validação financeira completa; `transactions.type` é TEXT livre; não há autenticação nem service layer. Posições antigas com `movement_date` inválida exigem correção cuidadosa; migrações não reescrevem histórico. Não há FK declarada para `transactions.investment_id` nem `investment_movements.transaction_id`; as rotas mantêm esses vínculos. Também não há série externa de CDI/SELIC/IPCA nem preços de mercado; esses current values permanecem indisponíveis. A renda fixa prefixada é uma estimativa matemática efetiva ACT/365, sem IR, taxas, cupons, carência, convenções específicas do produto ou reconciliação com extrato. `total_return_percent` é ROI simples acumulado sobre aportes brutos, não TIR nem taxa anualizada. O custo dos resgates é alocado proporcionalmente entre os aportes para manter o modelo agregado; revisar essa política se o produto passar a representar títulos/lotes individualizados. Cálculos monetários usam `REAL`/float; moeda decimal exata requer migração própria.
