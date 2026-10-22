# Pissa Finance — estado técnico

Estado do código após o bloco de resgates de investimentos. Este arquivo descreve o repositório; não afirma implantação em nenhuma máquina externa.

## Arquitetura e execução

FastAPI (Python 3.12 no Docker) serve `/api/*`, `/docs`, `/health` e frontend estático. SQLite fica em `/app/data/pissa_finance.db` no container, persistido em `./data/pissa_finance.db` no host. `init_db()` roda no lifespan. Porta 8001 do host → 8000 do container. Dashboard é leitura agregada de `transactions`, sem tabela própria.

## Schema (colunas relevantes)

- `transactions`: `id`, `description`, `amount`, `type`, `category`, `investment_id` nullable, `transaction_date`, `created_at`. Os tipos usados são `income`, `expense`, `investment` e `investment_withdrawal` (a coluna type continua TEXT livre).
- `goals`: `id`, `name`, `target_amount`, `current_amount`, `deadline`, `created_at`.
- `investments`: `id`, `name`, `investment_type`, `amount_invested`, `status TEXT NOT NULL DEFAULT 'active'`, `closed_at TEXT` nullable, `started_at`, `created_at`. Estados controlados pelo backend: `active` e `closed`.
- `fixed_income_details`: `investment_id` UNIQUE, `rate_type`, `rate_modifier`, `fixed_rate`, `maturity_date`.
- `market_investment_details`: `investment_id` UNIQUE, `asset_type`, `symbol`, `quantity`, `average_price`.
- `investment_movements`: `id`, `investment_id`, `transaction_id`, `movement_type`, `amount`, `principal_amount REAL` nullable, `quantity`, `movement_date`, `created_at`. Movimentos: `initial_contribution`, `contribution`, `withdrawal`.

`amount` do withdrawal é o dinheiro recebido no caixa; `principal_amount` é o custo removido da posição; `quantity` é a quantidade vendida em mercado. O `principal_amount` dos movimentos antigos de aporte permanece NULL. `created_at` é ISO 8601 em `America/Sao_Paulo`.

As tabelas são criadas se ausentes. Para bancos existentes, `init_db()` consulta `PRAGMA table_info` e adiciona apenas as colunas ausentes (`status`, `closed_at`, `principal_amount`), depois faz commit. Executá-lo novamente não duplica colunas; registros antigos ficam `active`, com `closed_at` e `principal_amount` NULL. A tabela transactions deste repositório já possui `investment_id`; esta migração não modifica versões ainda mais antigas que não o possuam.

## Rotas e regras

| Método | Rota | Efeito |
|---|---|---|
| GET/POST | `/api/investments/` | Listar com `details` / criar posição, movimento inicial e transaction de aporte. |
| PUT/DELETE | `/api/investments/{id}` | Atualizar investimento (sem withdrawals) / excluir investimento e todas as transactions vinculadas; movimentos e detalhes são removidos por cascade. |
| POST | `/api/investments/{id}/contributions` | Aportar em posição active. |
| PUT/DELETE | `/api/investments/{id}/contributions/{movement_id}` | Alterar/remover aporte posterior, somente se ainda não houver withdrawal. |
| POST | `/api/investments/{id}/withdrawals` | Resgatar parcialmente ou totalmente. |
| GET/POST | `/api/transactions/` | Listar/criar transactions avulsas; POST não aceita `investment_withdrawal`. |
| PUT/DELETE | `/api/transactions/{id}` | Operar transaction avulsa; 409 quando `investment_id` não é NULL; PUT avulso não pode definir `investment_withdrawal`. |
| GET/POST/PUT/DELETE | `/api/goals/`, `/api/goals/{id}` | CRUD de metas. |
| GET | `/api/dashboard/` | Agregações. |

Withdrawal recebe `amount` (positivo), `withdrawal_date` (`YYYY-MM-DD`, não anterior aos movimentos existentes), `quantity` opcional e `principal_amount` opcional. Em renda fixa, `principal_amount > 0` é obrigatório e não excede `amount_invested`; `quantity` não se aplica. Em mercado, `quantity > 0` é obrigatória e não excede a quantidade em carteira; o cliente não fornece principal, calculado como `average_price × quantity`. Antes do resgate, o backend confere consistência entre custo total, quantidade e preço médio (tolerância relativa de ponto flutuante); uma posição inconsistente recebe 409 para que o custo não desapareça no encerramento. Ela deve ser corrigida pelo PUT de investments **antes** do primeiro withdrawal. Resgate parcial reduz custo e unidades sem mudar preço médio; total zera principal, unidades e preço médio. Resgates cujo principal/unidades forem menores que a precisão de `REAL` para reduzir efetivamente a posição são rejeitados (400). Ao zerar posição, define `status=closed` e `closed_at=withdrawal_date`. Resgate fechado ou aporte novo em fechado retorna 409; investimento ausente retorna 404; valores ou datas fora das regras retornam 400 (payload incompleto: 422 do Pydantic). Aportes posteriores a um withdrawal só aceitam data válida igual ou posterior ao último resgate.

O resgate registra movement `withdrawal` (`amount`, `principal_amount`, `quantity`, `movement_date`) e transaction `investment_withdrawal` (`amount` recebido, `investment_id`, descrição `Resgate de <nome>`, data do resgate). São feitas as alterações da posição, detalhes, transaction e movement numa única transação SQLite (`BEGIN IMMEDIATE`, commit/rollback/finally), para não persistir estado parcial e serializar operações concorrentes. O PUT/DELETE genérico de transactions vinculadas é bloqueado; o backend das rotas de investments ainda manipula suas próprias transactions diretamente.

O PUT de investment e PUT/DELETE de contributions após **qualquer** withdrawal foram bloqueados para não reconstruir erroneamente posição/custo a partir de aportes sem considerar saídas; não existe edição/exclusão individual de withdrawal neste bloco. A exclusão da posição inteira é destrutiva e remove todas as transactions com o respectivo `investment_id`, inclusive saídas.

## Dashboard e frontend

O contrato mantém `income`, `expenses`, `invested`, `balance`, `categories`, `monthly`. `income` soma só `income`; `expenses`, só `expense`; `invested`, só `investment`; resgates entram **positivamente** em `balance` e `monthly`, sem virar `income`. Saldo = income − expenses − invested + withdrawals. `categories` agrupa apenas expenses; `monthly` apresenta os últimos seis meses por `transaction_date`.

A UI da aba Investments ainda usa funções placeholder (sem integração com a API). Home/Dashboard consomem a API; Transactions e Goals possuem fluxos integrados. Não houve alteração de frontend: a tela de Transactions considera qualquer tipo diferente de `income` como saída em seu resumo local e exibirá um withdrawal com sinal incorreto, enquanto o Dashboard calcula corretamente. As ações visuais de edição/exclusão de transaction vinculada recebem 409. Essa lacuna de UI ficou deliberadamente para um bloco posterior.

## Verificação e limites

`tests/test_investment_withdrawals.py` usa FastAPI TestClient e SQLite temporário. Cobre migração repetida, resgates parciais/totais de renda fixa e mercado, Dashboard, rejeições e imutabilidade de transactions vinculadas, fechamento, impedimento de reescrita histórica, exclusão da posição e rollback sob falha SQL. Executar com `python -m unittest discover -s tests -v` em Python 3.12 com dependências e `httpx2`; roteiro manual com payloads no [README.md](README.md).

Limites preexistentes: payloads de criação/edição de investimentos não fazem validação financeira completa; `transactions.type` é texto livre; não há valor de mercado atualizado, rentabilidade/projeções, autenticação, nem service layer. Posições preexistentes com `movement_date` inválida recebem 409 ao resgatar até que os dados sejam corrigidos com cuidado; a migração não reescreve dados históricos. O schema atual não declara FK para `transactions.investment_id` nem `investment_movements.transaction_id`; a integridade desses pares é mantida nas rotas. Cálculos monetários são `REAL` (ponto flutuante); moeda decimal exata e reconciliação de bases antigas inconsistentes exigiriam migração própria.
