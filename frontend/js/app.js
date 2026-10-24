(() => {
  const pendingOperationStorageKey = 'pissa-finance-pending-investment-operation';

  function readPendingInvestmentOperation() {
    try {
      const pending = JSON.parse(sessionStorage.getItem(pendingOperationStorageKey));
      if (
        !pending || !Number.isInteger(Number(pending.investmentId))
        || !['contribution', 'withdrawal'].includes(pending.operation)
        || typeof pending.key !== 'string' || !pending.key || pending.key.length > 128
        || typeof pending.signature !== 'string' || !pending.payload || typeof pending.payload !== 'object'
      ) return null;
      return { ...pending, investmentId: Number(pending.investmentId), ambiguous: true };
    } catch (_) {
      return null;
    }
  }

  function persistPendingInvestmentOperation(pending) {
    try {
      sessionStorage.setItem(pendingOperationStorageKey, JSON.stringify(pending));
      return true;
    } catch (_) {
      return false;
    }
  }

  function clearPendingInvestmentOperation() {
    state.pendingInvestmentOperation = null;
    try {
      sessionStorage.removeItem(pendingOperationStorageKey);
    } catch (_) {
      // The in-memory state has still been cleared.
    }
  }

  function createIdempotencyKey() {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
  }

  const state = {
    filter: 'all',
    modal: null,
    transactionMode: 'create',
    editingTransactionId: null,
    goalMode: 'create',
    editingGoalId: null,
    investmentMode: 'create',
    editingInvestmentId: null,
    investmentOperationId: null,
    investmentOperationSubmitting: false,
    pendingInvestmentOperation: readPendingInvestmentOperation(),
    transactions: [],
    goals: [],
    investments: []
  };
  const money = value => value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const $ = selector => document.querySelector(selector);
  const categoryColors = ['#fe6d63', '#edb65b', '#7f72ed', '#5aa8e8', '#77dda1'];
  let notificationTimer;

  function showNotification(message, type = 'success') {
    const notification = $('#notification');
    const notificationMessage = $('#notification-message');
    const notificationType = type === 'error' ? 'error' : 'success';

    clearTimeout(notificationTimer);
    notification.className = `notification ${notificationType}`;
    notificationMessage.textContent = message;
    notification.hidden = false;

    notificationTimer = setTimeout(() => {
      hideNotification();
    }, 3000);
  }

  function hideNotification() {
    clearTimeout(notificationTimer);
    $('#notification').hidden = true;
  }

  window.showNotification = showNotification;
  window.hideNotification = hideNotification;

  function renderCurrentMonth() {
    $('#current-month').textContent = new Date().toLocaleDateString('pt-BR', {
      month: 'long',
      year: 'numeric'
    });
  }

  async function loadDashboard() { 
    const response = await fetch('/api/dashboard/');

    if (!response.ok) throw new Error('Erro ao carregar dashboard');

    return await response.json();
  }
  async function loadTransactions() { 
    const response = await fetch('/api/transactions/');

    if (!response.ok) throw new Error('Erro ao carregar transações');

    state.transactions = await response.json();
    return state.transactions;
   }
  async function loadGoals() { 
    const response = await fetch('/api/goals/');
    
    if (!response.ok){
      throw new Error('Erro ao carregar metas');}

      state.goals = await response.json();
      return state.goals;
   }

  const transactionIcon = type => ({
    income: '↓', expense: '↑', investment: '◇', investment_withdrawal: '↗'
  }[type] || '•');
  const transactionLabel = type => ({
    income: 'Entrada', expense: 'Saída', investment: 'Investimento',
    investment_withdrawal: 'Resgate de investimento'
  }[type] || String(type || 'Movimentação'));
  function transactionMarkup(item, showActions = false) {
    const transactionId = escapeHtml(item.id);
    const description = escapeHtml(item.description);
    const safeType = escapeHtml(item.type);
    const category = escapeHtml(item.category || 'Sem categoria');
    const transactionDate = escapeHtml(item.transaction_date);
    const sign = ['income', 'investment_withdrawal'].includes(item.type) ? '+' : '-';
    const actions = showActions && !item.investment_id ? `
      <div class="transaction-actions" aria-label="Ações de ${description}">
        <button class="transaction-action" type="button" data-edit-transaction="${transactionId}" aria-label="Editar ${description}" title="Editar">✎</button>
        <button class="transaction-action danger" type="button" data-delete-transaction="${transactionId}" aria-label="Excluir ${description}" title="Excluir">×</button>
      </div>` : '';
    return `
    <article class="transaction ${safeType}">
      <div class="transaction-icon">${transactionIcon(item.type)}</div>
      <div class="transaction-main">
        <strong>${description}</strong>
        <span>${escapeHtml(transactionLabel(item.type))} • ${category}</span>
      </div>
      <div class="transaction-value">
        <strong>${sign} ${money(Number(item.amount) || 0)}</strong>
        <span>${transactionDate}</span>
      </div>${actions}
    </article>`;
  }
  
  function getGoalTarget(goal) { return goal.target_amount ?? goal.target; }
  function getGoalCurrent(goal) { return goal.current_amount ?? goal.current; }

  function goalMarkup(goal, showActions = false) {
    const target = getGoalTarget(goal);
    const current = getGoalCurrent(goal);
    const percentage = Math.min(100, Math.round((current / target) * 100));
    const remaining = Math.max(0, target - current);
    const actions = showActions ? `<div class="goal-actions" aria-label="Ações de ${goal.name}"><button class="goal-action" type="button" data-edit-goal="${goal.id}" aria-label="Editar ${goal.name}" title="Editar">✎</button><button class="goal-action danger" type="button" data-delete-goal="${goal.id}" aria-label="Excluir ${goal.name}" title="Excluir">×</button></div>` : '';
    return `<article class="goal-card"><div class="goal-top"><strong>${goal.name}</strong><div class="goal-header-actions"><span>${percentage}%</span>${actions}</div></div><div class="goal-numbers"><span>Guardado <strong>${money(current)}</strong></span><span>Meta ${money(target)}</span></div><div class="progress ${goal.color}"><i style="width:${percentage}%"></i></div><div class="goal-numbers"><span>Faltam ${money(remaining)}</span><span>${percentage}% concluído</span></div></article>`;
  }
  async function renderHome() {
  const dashboard = await loadDashboard();
  const goals = await loadGoals();
  const transactions = await loadTransactions();

  $('#net-worth').textContent = money(
    dashboard.balance
  );

  $('#home-summary').innerHTML = [
    ['Total recebido', dashboard.income, 'positive'],
    ['Total investido', dashboard.invested, 'positive'],
    ['Gastos', dashboard.expenses, 'negative']
  ].map(([label, value, kind]) => `
    <article class="mini-card">
      <span>${label}</span>
      <strong class="${kind}">
        ${kind === 'negative' ? '− ' : '+ '}${money(value)}
      </strong>
    </article>
  `).join('');

  $('#home-goals').innerHTML =
    goals.map(goalMarkup).join('');

  $('#recent-transactions').innerHTML =
    transactions.slice(0, 3).map(transactionMarkup).join('');
}
  
  async function renderTransactions() {
    const items = await loadTransactions();
    const now = new Date();
    const currentMonth = now.getMonth();
    const currentYear = now.getFullYear();

    const monthlyItems = items.filter(item => {
      const date = new Date(item.transaction_date + 'T00:00:00');

      return (
        date.getMonth() === currentMonth &&
        date.getFullYear() === currentYear
      );
    });
    
    const income = monthlyItems
      .filter(x => x.type === 'income')
      .reduce((sum, x) => sum + x.amount, 0);
    const expenses = monthlyItems
      .filter(x => x.type === 'expense')
      .reduce((sum, x) => sum + x.amount, 0);
    const invested = monthlyItems
      .filter(x => x.type === 'investment')
      .reduce((sum, x) => sum + x.amount, 0);
    const withdrawn = monthlyItems
      .filter(x => x.type === 'investment_withdrawal')
      .reduce((sum, x) => sum + x.amount, 0);
    const outgoing = expenses + invested;

    $('#month-balance').textContent = money(income - expenses - invested + withdrawn);
    $('#month-income').textContent = '+ ' + money(income);
    $('#month-expense').textContent = '− ' + money(outgoing);
    $('#month-withdrawals').textContent = '+ ' + money(withdrawn);
    
    const visible  = state.filter === 'all'
      ? items
      : items.filter(x => x.type === state.filter);
    
    $('#transaction-list').innerHTML = visible.length ? visible.map(item => transactionMarkup(item, true)).join('') : '<p class="page-intro">Nenhuma movimentação encontrada.</p>';
  }
  
  async function renderGoals() { $('#goal-list').innerHTML = (await loadGoals()).map(goal => goalMarkup(goal, true)).join(''); }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, character => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[character]);
  }

  function parseInvestmentNumber(value) {
    const normalized = String(value ?? '').trim();
    if (!normalized) return null;
    const numeric = normalized.includes(',')
      ? normalized.replace(/\./g, '').replace(',', '.')
      : normalized;
    const parsed = Number(numeric);
    return Number.isFinite(parsed) ? parsed : null;
  }

  async function loadInvestments() {
    try {
      const response = await fetch('/api/investments/');
      if (!response.ok) throw new Error('Não foi possível carregar os investimentos.');
      state.investments = await response.json();
      return state.investments;
    } catch (error) {
      showNotification(error.message || 'Erro ao carregar investimentos.', 'error');
      throw error;
    }
  }

  async function prepareCreateInvestment(payload) {
    try {
      const response = await fetch('/api/investments/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        let detail = '';
        try {
          const error = await response.json();
          detail = typeof error.detail === 'string' ? error.detail : '';
        } catch (_) {
          // Keep the friendly fallback when the server response is not JSON.
        }
        throw new Error(detail || 'Não foi possível cadastrar o investimento. Confira os dados e tente novamente.');
      }
      return true;
    } catch (error) {
      showNotification(error.message || 'Falha de conexão ao cadastrar investimento.', 'error');
      return false;
    }
  }

  async function apiErrorMessage(response, fallback) {
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') return body.detail;
      if (Array.isArray(body.detail)) {
        return body.detail.map(item => item.msg).filter(Boolean).join('; ') || fallback;
      }
    } catch (_) {
      // Use the friendly fallback if the response is not JSON.
    }
    return fallback;
  }

  async function refreshInvestmentRelatedScreens() {
    const results = await Promise.allSettled([
      renderInvestments(), renderHome(), renderTransactions(), renderDashboard()
    ]);
    return results.some(result =>
      result.status === 'rejected' || result.value === false
    );
  }

  async function submitInvestmentOperation(investmentId, operation, payload, idempotencyKey) {
    const endpoint = operation === 'contribution' ? 'contributions' : 'withdrawals';
    const fallback = operation === 'contribution'
      ? 'Não foi possível registrar o aporte.'
      : 'Não foi possível registrar o resgate.';
    try {
      const response = await fetch(`/api/investments/${investmentId}/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey
        },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        return {
          success: false,
          ambiguous: response.status >= 500,
          message: await apiErrorMessage(response, fallback)
        };
      }
      try {
        return { success: true, data: await response.json() };
      } catch (_) {
        return {
          success: false,
          ambiguous: true,
          message: 'A resposta do servidor não pôde ser confirmada.'
        };
      }
    } catch (_) {
      return {
        success: false,
        ambiguous: true,
        message: 'A conexão foi interrompida; não foi possível confirmar se a operação foi registrada.'
      };
    }
  }

  function confirmDeleteInvestment(investmentId) {
    const investment = state.investments.find(item => item.id === Number(investmentId));
    if (!investment) {
      showNotification('Investimento não encontrado. Atualize a lista e tente novamente.', 'error');
      return;
    }
    const confirmed = window.confirm(
      `Excluir o cadastro de "${investment.name}"? Isso remove o investimento e todas as movimentações e transactions vinculadas. Use apenas se foi cadastrado por engano; não é um resgate nem encerra a posição.`
    );
    if (confirmed) deleteInvestment(investment.id);
  }

  async function deleteInvestment(investmentId) {
    try {
      const response = await fetch(`/api/investments/${investmentId}`, { method: 'DELETE' });
      if (!response.ok) {
        showNotification(await apiErrorMessage(response, 'Não foi possível excluir o cadastro.'), 'error');
        return;
      }
      const refreshFailed = await refreshInvestmentRelatedScreens();
      showNotification(
        refreshFailed
          ? 'Cadastro excluído, mas algumas telas não atualizaram. Recarregue a página.'
          : 'Cadastro do investimento excluído.',
        refreshFailed ? 'error' : 'success'
      );
    } catch (error) {
      showNotification(error.message || 'Falha de conexão ao excluir o cadastro.', 'error');
    }
  }

  const investmentTypeLabels = {
    fixed_income: 'Renda fixa',
    market_investment: 'Mercado'
  };
  const assetTypeLabels = {
    crypto: 'Cripto', stock: 'Ação', fii: 'FII', etf: 'ETF', other: 'Outro'
  };
  const rateTypeLabels = {
    cdi: 'CDI', selic: 'SELIC', ipca: 'IPCA', prefixed: 'Prefixada'
  };

  function investmentDetail(label, value) {
    if (value === null || value === undefined || value === '') return '';
    return `<span class="investment-detail">${escapeHtml(label)}<strong>${escapeHtml(value)}</strong></span>`;
  }

  function investmentMarkup(investment) {
    const details = investment.details || {};
    const isFixedIncome = investment.investment_type === 'fixed_income';
    const status = investment.status === 'closed' ? 'closed' : 'active';
    const investmentId = escapeHtml(investment.id);
    const investmentName = escapeHtml(investment.name);
    const pending = state.pendingInvestmentOperation;
    const hasPendingOperation = Boolean(pending);
    const pendingMatchesInvestment = pending && pending.investmentId === investment.id;
    const extraDetails = isFixedIncome
      ? [
          investmentDetail('Taxa', rateTypeLabels[details.rate_type] || details.rate_type),
          details.rate_modifier != null ? investmentDetail(
            details.rate_type === 'ipca' ? 'Adicional' : 'Percentual', `${details.rate_modifier}%`
          ) : '',
          details.fixed_rate != null ? investmentDetail('Taxa prefixada', `${details.fixed_rate}% a.a.`) : '',
          investmentDetail('Vencimento', details.maturity_date)
        ].join('')
      : [
          investmentDetail('Ativo', assetTypeLabels[details.asset_type] || details.asset_type),
          investmentDetail('Símbolo', details.symbol),
          details.quantity != null ? investmentDetail('Quantidade', Number(details.quantity).toLocaleString('pt-BR')) : '',
          details.average_price != null ? investmentDetail('Preço médio', money(Number(details.average_price))) : ''
        ].join('');
    const actions = pendingMatchesInvestment
      ? `<div class="investment-actions">
          <button class="primary-button" type="button" data-investment-action="${escapeHtml(pending.operation)}" data-investment-id="${investmentId}">Confirmar operação pendente</button>
        </div>`
      : hasPendingOperation
        ? '<div class="investment-operation-note">Resolva a operação pendente antes de iniciar outra.</div>'
      : status === 'active'
      ? `<div class="investment-actions">
          <button class="primary-button" type="button" data-investment-action="contribution" data-investment-id="${investmentId}">Novo aporte</button>
          <button class="text-button" type="button" data-investment-action="withdrawal" data-investment-id="${investmentId}">Resgatar</button>
          <button class="goal-action danger" type="button" data-delete-investment="${investmentId}" aria-label="Excluir cadastro ${investmentName}" title="Excluir cadastro">×</button>
        </div>`
      : `<div class="investment-actions">
          <button class="goal-action danger" type="button" data-delete-investment="${investmentId}" aria-label="Excluir cadastro ${investmentName}" title="Excluir cadastro">×</button>
        </div>`;

    return `<article class="investment-card ${status}">
      <div class="investment-card-header">
        <div><strong>${investmentName}</strong><p class="investment-type">${escapeHtml(investmentTypeLabels[investment.investment_type] || investment.investment_type)}</p></div>
        <span class="investment-status ${status}">${status === 'closed' ? 'Encerrado' : 'Ativo'}</span>
      </div>
      <strong class="investment-card-value">${money(Number(investment.amount_invested) || 0)}</strong>
      <div class="investment-card-meta"><span>Início</span><time datetime="${escapeHtml(investment.started_at)}">${escapeHtml(investment.started_at)}</time></div>
      ${status === 'closed' && investment.closed_at ? investmentDetail('Encerrado em', investment.closed_at) : ''}
      ${extraDetails ? `<div class="investment-details">${extraDetails}</div>` : ''}
      ${actions}
    </article>`;
  }

  async function renderInvestments() {
    const list = $('#investment-list');
    list.innerHTML = '<p class="page-intro">Carregando investimentos…</p>';
    try {
      const investments = await loadInvestments();
      if (state.pendingInvestmentOperation && !investments.some(
        item => item.id === state.pendingInvestmentOperation.investmentId
      )) {
        clearPendingInvestmentOperation();
        showNotification('A posição da operação pendente não existe mais; confirme o estado antes de registrar outra.', 'error');
      }
      const total = investments.reduce((sum, item) => sum + (Number(item.amount_invested) || 0), 0);
      $('#investment-total').textContent = money(total);
      $('#investment-count').textContent = String(investments.length);
      list.innerHTML = investments.length
        ? investments.map(investmentMarkup).join('')
        : '<p class="page-intro">Nenhum investimento cadastrado.</p>';
      return true;
    } catch (_) {
      state.investments = [];
      $('#investment-total').textContent = money(0);
      $('#investment-count').textContent = '0';
      list.innerHTML = '<p class="page-intro">Não foi possível carregar os investimentos. Tente novamente mais tarde.</p>';
      return false;
    }
  }

  function renderExpenseCategories(categories) {
    const donut = $('#expense-donut');
    const legend = $('#expense-legend');
    const total = categories.reduce((sum, category) => sum + category.value, 0);

    if (!categories.length || total <= 0) {
      donut.style.background = 'var(--border)';
      legend.innerHTML = '<span class="page-intro">Nenhum gasto registrado.</span>';
      return;
    }

    let currentPercentage = 0;
    const segments = categories.map((category, index) => {
      const nextPercentage = currentPercentage + (category.value / total) * 100;
      const color = categoryColors[index % categoryColors.length];
      const segment = `${color} ${currentPercentage}% ${nextPercentage}%`;
      currentPercentage = nextPercentage;
      return segment;
    });

    donut.style.background = `conic-gradient(${segments.join(', ')})`;
    legend.innerHTML = categories.map((category, index) => {
      const color = categoryColors[index % categoryColors.length];
      return `<div class="legend-item"><span><i style="background:${color}"></i>${category.name}</span><strong>${money(category.value)}</strong></div>`;
    }).join('');
  }

  function renderMonthlyEvolution(monthly) {
    const chart = $('#line-chart');
    const months = $('#chart-months');
    const values = monthly.map(item => Number(item.value) || 0);
    const maxValue = Math.max(0, ...values.map(value => Math.abs(value)));

    chart.innerHTML = monthly.map((item, index) => {
      const value = values[index];
      const height = maxValue ? Math.max(8, (Math.abs(value) / maxValue) * 100) : 2;
      const typeClass = value < 0 ? ' negative' : '';
      return `<i class="line-bar${typeClass}" style="height:${height}%" aria-label="${item.month}: ${money(value)}"></i>`;
    }).join('');
    months.innerHTML = monthly.map(item => `<span>${item.month}</span>`).join('');
  }

  async function renderDashboard() {
    const d = await loadDashboard();
    $('#dashboard-stats').innerHTML = [
    ['Total recebido', d.income, 'positive'],
    ['Total gasto', d.expenses, 'negative'],
    ['Total investido', d.invested, 'positive accent'],
    ['Saldo disponível', d.balance, 'positive']
  ].map(([label, value, classes]) => `
    <article class="stat-card ${classes.includes('accent') ? 'accent' : ''}">
      <span>${label}</span>
      <strong class="${classes}">
        ${money(value)}
      </strong>
    </article>
  `).join('');
    $('#expense-total').textContent = money(d.expenses);
    renderExpenseCategories(d.categories || []);
    renderMonthlyEvolution(d.monthly || []);
  }
  function navigate(screen) {
    document.querySelectorAll('.screen').forEach(item => item.classList.toggle('active', item.id === screen));
    document.querySelectorAll('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.screen === screen));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  function investmentSpecificFields(investmentType) {
    if (investmentType === 'fixed_income') return `<div class="investment-fields"><p class="investment-fields-title">Dados da renda fixa</p><label class="field">Tipo de rentabilidade<select name="rate_type"><option value="cdi">CDI</option><option value="selic">SELIC</option><option value="ipca">IPCA</option><option value="prefixed">Prefixada</option></select></label><div id="fixed-income-rate-fields"></div><label class="field">Data de vencimento<input name="maturity_date" type="date"></label></div>`;
    if (investmentType === 'market_investment') return `<div class="investment-fields"><p class="investment-fields-title">Dados do ativo</p><label class="field">Tipo de ativo<select name="asset_type" required><option value="crypto">Cripto</option><option value="stock">Ação</option><option value="fii">FII</option><option value="etf">ETF</option><option value="other">Outro</option></select></label><label class="field">Símbolo<input name="symbol" required placeholder="Ex.: BTC ou HGLG11" autocapitalize="characters"></label><div class="form-row"><label class="field">Quantidade<input name="quantity" type="number" required min="0.00000001" step="any" inputmode="decimal" placeholder="0,00"></label><label class="field">Preço médio<input name="average_price" type="number" required min="0.01" step="any" inputmode="decimal" placeholder="R$ 0,00"></label></div></div>`;
    return '';
  }

  function fixedIncomeRateFields(rateType) {
    if (rateType === 'prefixed') return '<label class="field">Taxa prefixada (% a.a.)<input name="fixed_rate" type="number" required min="0" step="any" inputmode="decimal" placeholder="Ex.: 12,5"></label>';
    const label = rateType === 'ipca' ? 'Adicional contratado (%)' : 'Percentual contratado (%)';
    const placeholder = rateType === 'ipca' ? 'Ex.: 6' : 'Ex.: 110';
    return `<label class="field">${label}<input name="rate_modifier" type="number" required min="0" step="any" inputmode="decimal" placeholder="${placeholder}"></label>`;
  }

  function updateInvestmentFormFields() {
    const form = $('#entry-form');
    const investmentType = form.elements.investment_type?.value;
    const details = $('#investment-specific-fields');
    if (!details || !investmentType) return;
    details.innerHTML = investmentSpecificFields(investmentType);
    const rateFields = $('#fixed-income-rate-fields');
    if (rateFields) rateFields.innerHTML = fixedIncomeRateFields(form.elements.rate_type.value);
  }

  function formMarkup(type) {
    if (type === 'goal') return `<div class="form-grid"><label class="field">Nome da meta<input name="name" required placeholder="Ex.: Viagem"></label><div class="form-row"><label class="field">Valor alvo<input name="target" required inputmode="decimal" placeholder="R$ 0,00"></label><label class="field">Valor inicial<input name="initial" inputmode="decimal" placeholder="R$ 0,00"></label></div><label class="field">Prazo (opcional)<input name="deadline" type="month"></label><div class="form-actions"><button class="secondary-button" type="button" data-close-modal>Cancelar</button><button class="primary-button form-submit" type="submit">Adicionar meta</button></div></div>`;
    if (type === 'investment') return `<div class="form-grid">
      <label class="field">Tipo de investimento<select name="investment_type" required><option value="fixed_income">Renda fixa</option><option value="market_investment">Mercado</option></select></label>
      <label class="field">Nome<input name="name" required maxlength="120" placeholder="Ex.: Tesouro Selic 2029"></label>
      <div class="form-row">
        <label class="field">Valor aportado<input name="amount_invested" type="number" required min="0.01" step="any" inputmode="decimal" placeholder="R$ 0,00"></label>
        <label class="field">Data do investimento<input name="started_at" type="date" required></label>
      </div>
      <div id="investment-specific-fields"></div>
      <div class="form-actions"><button class="secondary-button" type="button" data-close-modal>Cancelar</button><button class="primary-button form-submit" type="submit">Salvar investimento</button></div>
    </div>`;
    return `<div class="form-grid"><label class="field">Tipo<select name="type"><option value="income">Entrada</option><option value="expense">Saída</option></select></label><label class="field">Descrição<input name="description" required placeholder="Ex.: Mercado"></label><div class="form-row"><label class="field">Valor<input name="amount" required inputmode="decimal" placeholder="R$ 0,00"></label><label class="field">Categoria<input name="category" required placeholder="Ex.: Alimentação"></label></div><label class="field">Data<input name="date" type="date" value="2026-09-10"></label><label class="field">Observação<textarea name="note" placeholder="Opcional"></textarea></label><div class="form-actions"><button class="secondary-button" type="button" data-close-modal>Cancelar</button><button class="primary-button form-submit" type="submit">Adicionar</button></div></div>`;
  }

  function investmentOperationFormMarkup(investment, operation) {
    const isMarket = investment.investment_type === 'market_investment';
    const dateName = operation === 'contribution' ? 'contribution_date' : 'withdrawal_date';
    const amountLabel = operation === 'contribution' ? 'Valor do aporte' : 'Valor recebido';
    const amountFields = `<label class="field">${amountLabel}<input name="amount" type="number" required min="0.01" step="any" inputmode="decimal" placeholder="R$ 0,00"></label>`;
    const positionFields = operation === 'contribution'
      ? (isMarket ? '<label class="field">Quantidade adquirida<input name="quantity" type="number" required min="0.00000001" step="any" inputmode="decimal" placeholder="0,00"></label>' : '')
      : (isMarket
          ? '<label class="field">Quantidade vendida<input name="quantity" type="number" required min="0.00000001" step="any" inputmode="decimal" placeholder="0,00"></label>'
          : '<div class="investment-operation-note">Informe o dinheiro recebido e, separadamente, o principal retirado da posição.</div><label class="field">Principal retirado<input name="principal_amount" type="number" required min="0.01" step="any" inputmode="decimal" placeholder="R$ 0,00"></label>');
    const submit = operation === 'contribution' ? 'Registrar aporte' : 'Registrar resgate';

    return `<div class="form-grid">
      ${amountFields}
      ${positionFields}
      <label class="field">Data<input name="${dateName}" type="date" required></label>
      <div class="form-actions"><button class="secondary-button" type="button" data-close-modal>Cancelar</button><button class="primary-button form-submit" type="submit">${submit}</button></div>
    </div>`;
  }

  function openInvestmentOperation(investmentId, operation) {
    if (state.investmentOperationSubmitting) {
      showNotification('Aguarde a operação atual terminar.', 'error');
      return;
    }
    const investment = state.investments.find(item => item.id === Number(investmentId));
    if (!investment) {
      showNotification('Investimento não encontrado. Atualize a lista e tente novamente.', 'error');
      return;
    }
    const pending = state.pendingInvestmentOperation;
    const isPendingRetry = pending
      && pending.investmentId === investment.id
      && pending.operation === operation;
    if (pending && !isPendingRetry) {
      showNotification('Confirme a operação pendente antes de iniciar outra.', 'error');
      return;
    }
    if (investment.status !== 'active' && !isPendingRetry) {
      showNotification('Esta posição está encerrada e não aceita novas operações.', 'error');
      return;
    }
    state.modal = `investment_${operation}`;
    state.investmentOperationId = investment.id;
    $('#modal-title').textContent = operation === 'contribution' ? 'Novo aporte' : 'Resgatar investimento';
    $('#entry-form').innerHTML = investmentOperationFormMarkup(investment, operation);
    if (isPendingRetry) {
      for (const [name, value] of Object.entries(pending.payload)) {
        const field = $('#entry-form').elements[name];
        if (field) field.value = value;
      }
      $('#entry-form [type="submit"]').textContent = 'Confirmar operação pendente';
    }
    $('#modal-backdrop').hidden = false;
    setTimeout(() => $('#entry-form input')?.focus(), 50);
  }

  function openModal(type, modalMode = 'create') {
    state.modal = type;
    if (type === 'transaction') {
      state.transactionMode = modalMode;
      if (modalMode === 'create') state.editingTransactionId = null;
    }
    if (type === 'goal') {
      state.goalMode = modalMode;
      if (modalMode === 'create') state.editingGoalId = null;
    }
    if (type === 'investment') {
      state.investmentMode = modalMode;
      if (modalMode === 'create') state.editingInvestmentId = null;
    }
    $('#modal-title').textContent = type === 'goal' ? modalMode === 'edit' ? 'Editar meta' : 'Nova meta' : type === 'investment' ? modalMode === 'edit' ? 'Editar investimento' : 'Novo investimento' : modalMode === 'edit' ? 'Editar movimentação' : 'Nova movimentação';
    $('#entry-form').innerHTML = formMarkup(type);
    if (type === 'investment') updateInvestmentFormFields();
    $('#modal-backdrop').hidden = false;
    setTimeout(() => $('#entry-form input')?.focus(), 50);
  }

  function getTransactionById(id) {
    return state.transactions.find(transaction => transaction.id === Number(id));
  }

  function fillTransactionForm(transaction) {
    const form = $('#entry-form');
    form.elements.type.value = transaction.type;
    form.elements.description.value = transaction.description;
    form.elements.amount.value = transaction.amount;
    form.elements.category.value = transaction.category || '';
    form.elements.date.value = transaction.transaction_date || '';
  }

  function openEditTransaction(id) {
    const transaction = getTransactionById(id);
    if (!transaction) {
      showNotification('Movimentação não encontrada', 'error');
      return;
    }
    if (transaction.type === 'investment') {
      showNotification('Investimentos serão gerenciados pela nova área.', 'error');
      return;
    }

    state.editingTransactionId = transaction.id;
    openModal('transaction', 'edit');
    fillTransactionForm(transaction);
    $('#entry-form [type="submit"]').textContent = 'Salvar alterações';
  }

  function getGoalById(id) {
    return state.goals.find(goal => goal.id === Number(id));
  }

  function fillGoalForm(goal) {
    const form = $('#entry-form');
    form.elements.name.value = goal.name;
    form.elements.target.value = getGoalTarget(goal);
    form.elements.initial.value = getGoalCurrent(goal);
    form.elements.deadline.value = goal.deadline ? String(goal.deadline).slice(0, 7) : '';
  }

  function openEditGoal(id) {
    const goal = getGoalById(id);
    if (!goal) {
      showNotification('Meta não encontrada', 'error');
      return;
    }

    state.editingGoalId = goal.id;
    openModal('goal', 'edit');
    fillGoalForm(goal);
    $('#entry-form [type="submit"]').textContent = 'Salvar alterações';
  }

  async function prepareUpdateGoal(id, payload) {
  const response = await fetch(`/api/goals/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    showNotification('Erro ao atualizar meta', 'error');
    return false;
  }

  return true;
}

  function confirmDeleteGoal(id) {
    const goal = getGoalById(id);
    if (!goal) {
      showNotification('Meta não encontrada', 'error');
      return;
    }

    if (!window.confirm('Deseja realmente excluir esta meta?')) return;
    prepareDeleteGoal(goal.id);
  }

  async function prepareDeleteGoal(id) {
  const response = await fetch(`/api/goals/${id}`, {
    method: 'DELETE'
  });

  if (!response.ok) {
    showNotification('Erro ao excluir meta', 'error');
    return;
  }

  await renderHome();
  await renderGoals();
  await renderDashboard();

  showNotification(
    'Meta excluída com sucesso',
    'success'
  );
}

  async function prepareUpdateTransaction(id, payload) {
    const response = await fetch(`/api/transactions/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      showNotification('Erro ao atualizar movimentação', 'error');
      return false;
    }
    return true;
  }

  function confirmDeleteTransaction(id) {
  const transaction = getTransactionById(id);

  if (!transaction) {
    showNotification('Movimentação não encontrada', 'error');
    return;
  }

  if (!window.confirm(
    'Deseja realmente excluir esta movimentação?'
  )) return;

  prepareDeleteTransaction(transaction.id);
}

  async function prepareDeleteTransaction(id) {
    const response = await fetch(`/api/transactions/${id}`, {
       method: 'DELETE' 
      });
    
    if (!response.ok){
      showNotification('Erro ao excluir movimentação', 'error');
      return;
    }

    await renderHome();
    await renderTransactions();
    await renderDashboard();

    showNotification('Movimentação excluída com sucesso', 'success');
  }

  function closeModal() {
    if (state.investmentOperationSubmitting) {
      showNotification('Aguarde a operação atual terminar antes de fechar.', 'error');
      return;
    }
    $('#modal-backdrop').hidden = true;
    state.modal = null;
    state.transactionMode = 'create';
    state.editingTransactionId = null;
    state.goalMode = 'create';
    state.editingGoalId = null;
    state.investmentMode = 'create';
    state.editingInvestmentId = null;
    state.investmentOperationId = null;
  }
  document.querySelector('[data-close-modal]').addEventListener('click', closeModal);
  function parseAmount(value) { return Number(String(value).replace(/[^0-9,.-]/g, '').replace('.', '').replace(',', '.')) || 0; }
  $('#entry-form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const isGoal = state.modal === 'goal';
    const isInvestment = state.modal === 'investment';

    if (isInvestment) {
      const investmentPayload = {
        name: String(form.get('name') || '').trim(),
        amount_invested: parseInvestmentNumber(form.get('amount_invested')),
        started_at: form.get('started_at'),
        investment_type: form.get('investment_type')
      };
      if (investmentPayload.investment_type === 'fixed_income') {
        investmentPayload.rate_type = form.get('rate_type');
        investmentPayload.maturity_date = form.get('maturity_date') || null;
        if (investmentPayload.rate_type === 'prefixed') {
          investmentPayload.fixed_rate = parseInvestmentNumber(form.get('fixed_rate'));
        } else {
          investmentPayload.rate_modifier = parseInvestmentNumber(form.get('rate_modifier'));
        }
      } else {
        investmentPayload.asset_type = form.get('asset_type');
        investmentPayload.symbol = String(form.get('symbol') || '').trim();
        investmentPayload.quantity = parseInvestmentNumber(form.get('quantity'));
        investmentPayload.average_price = parseInvestmentNumber(form.get('average_price'));
      }

      const success = await prepareCreateInvestment(investmentPayload);
      if (!success) return;
      closeModal();
      const refreshResults = await Promise.allSettled([
        renderInvestments(), renderHome(), renderTransactions(), renderDashboard()
      ]);
      const refreshFailed = refreshResults.some(result =>
        result.status === 'rejected' || result.value === false
      );
      showNotification(
        refreshFailed
          ? 'Investimento cadastrado, mas algumas telas não atualizaram. Recarregue a página.'
          : 'Investimento cadastrado com sucesso',
        refreshFailed ? 'error' : 'success'
      );
      return;
    }

    if (state.modal === 'investment_contribution' || state.modal === 'investment_withdrawal') {
      if (state.investmentOperationSubmitting) return;
      const operation = state.modal === 'investment_contribution' ? 'contribution' : 'withdrawal';
      const investment = state.investments.find(item => item.id === state.investmentOperationId);
      if (!investment) {
        showNotification('Investimento não encontrado. Atualize a lista e tente novamente.', 'error');
        return;
      }
      const dateName = operation === 'contribution' ? 'contribution_date' : 'withdrawal_date';
      const payload = {
        amount: parseInvestmentNumber(form.get('amount')),
        [dateName]: form.get(dateName)
      };
      if (investment.investment_type === 'market_investment') {
        payload.quantity = parseInvestmentNumber(form.get('quantity'));
      } else if (operation === 'withdrawal') {
        payload.principal_amount = parseInvestmentNumber(form.get('principal_amount'));
      }

      const signature = JSON.stringify({ investmentId: investment.id, operation, payload });
      let pending = state.pendingInvestmentOperation;
      if (pending && (
        pending.investmentId !== investment.id
        || pending.operation !== operation
        || pending.signature !== signature
      )) {
        showNotification(
          'Há uma operação sem confirmação. Reenvie os mesmos dados antes de iniciar ou alterar outra.',
          'error'
        );
        return;
      }
      if (!pending) {
        pending = {
          investmentId: investment.id,
          operation,
          payload,
          signature,
          key: createIdempotencyKey(),
          ambiguous: true
        };
        state.pendingInvestmentOperation = pending;
      }
      if (!persistPendingInvestmentOperation(pending)) {
        showNotification(
          'A operação não foi enviada porque não foi possível guardar a chave e os dados para uma repetição segura. Habilite o armazenamento do navegador e tente novamente.',
          'error'
        );
        return;
      }

      const operationForm = event.currentTarget;
      const submitButton = operationForm.querySelector('[type="submit"]');
      const originalSubmitLabel = submitButton.textContent;
      state.investmentOperationSubmitting = true;
      submitButton.disabled = true;
      submitButton.textContent = 'Enviando…';
      operationForm.setAttribute('aria-busy', 'true');
      let result;
      try {
        result = await submitInvestmentOperation(investment.id, operation, payload, pending.key);
      } finally {
        state.investmentOperationSubmitting = false;
        operationForm.removeAttribute('aria-busy');
        submitButton.disabled = false;
        submitButton.textContent = originalSubmitLabel;
      }
      if (!result.success) {
        if (result.ambiguous) {
          pending.ambiguous = true;
          persistPendingInvestmentOperation(pending);
          await renderInvestments();
          showNotification(
            `${result.message} Reenvie os mesmos dados para confirmar sem duplicar a operação; a mesma chave será reutilizada.`,
            'error'
          );
        } else {
          clearPendingInvestmentOperation();
          await renderInvestments();
          showNotification(result.message, 'error');
        }
        return;
      }

      clearPendingInvestmentOperation();
      closeModal();
      const refreshFailed = await refreshInvestmentRelatedScreens();
      const operationResult = result.data;
      const successMessage = operation === 'contribution'
        ? operationResult.idempotent_replay
          ? 'Aporte já registrado; posição atualizada.'
          : 'Aporte registrado com sucesso.'
        : operationResult.status === 'closed'
          ? operationResult.idempotent_replay
            ? 'Resgate total já registrado; posição encerrada.'
            : 'Resgate total registrado; posição encerrada.'
          : operationResult.idempotent_replay
            ? 'Resgate já registrado; posição atualizada.'
            : 'Resgate registrado com sucesso.';
      showNotification(
        refreshFailed
          ? `${successMessage} Algumas telas não atualizaram; recarregue a página.`
          : successMessage,
        refreshFailed ? 'error' : 'success'
      );
      return;
    }

    if (isGoal) {
      const goalPayload = {
        name: form.get('name'),
        target_amount: parseAmount(form.get('target')),
        current_amount: parseAmount(form.get('initial')),
        deadline: form.get('deadline') || null
      };

      if (state.goalMode === 'edit') {
        const success = await prepareUpdateGoal(
        state.editingGoalId,
        goalPayload
        );

      if (!success) return;

      await renderHome();
      await renderGoals();
      await renderDashboard();

      closeModal();

      showNotification(
        'Meta atualizada com sucesso',
        'success'
      );

  return;
}

      const response = await fetch('/api/goals/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(goalPayload)
      });

      if (!response.ok) {
        showNotification('Erro ao adicionar meta', 'error');
        return;
      }

    } else {
      const payload = {
        description: form.get('description'),
        amount: parseAmount(form.get('amount')),
        type: form.get('type'),
        category: form.get('category'),
        transaction_date: form.get('date')
      };

      if (state.transactionMode === 'edit') {
        const success = await prepareUpdateTransaction(
          state.editingTransactionId,
          payload
        );

        if (!success) return;

        await renderHome();
        await renderTransactions();
        await renderDashboard();

        closeModal();
        showNotification('Movimentação atualizada com sucesso', 'success');
        return;
      }

      const response = await fetch('/api/transactions/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        showNotification('Erro ao adicionar movimentação', 'error');
        return;
      }
    }

    renderHome();
    renderTransactions();
    renderGoals();
    renderDashboard();

    closeModal();

    showNotification(
      isGoal ? 'Meta adicionada com sucesso' : 'Movimentação adicionada com sucesso',
      'success'
    );
  });
  
  document.addEventListener('click', event => {
    const nav = event.target.closest('[data-screen]'); if (nav) navigate(nav.dataset.screen);
    const link = event.target.closest('[data-navigate]'); if (link) navigate(link.dataset.navigate);
    const modal = event.target.closest('[data-open-modal]'); if (modal) openModal(modal.dataset.openModal);
    const investmentAction = event.target.closest('[data-investment-action]');
    if (investmentAction) openInvestmentOperation(investmentAction.dataset.investmentId, investmentAction.dataset.investmentAction);
    const deleteInvestmentButton = event.target.closest('[data-delete-investment]');
    if (deleteInvestmentButton) confirmDeleteInvestment(deleteInvestmentButton.dataset.deleteInvestment);
    const editTransaction = event.target.closest('[data-edit-transaction]'); if (editTransaction) openEditTransaction(editTransaction.dataset.editTransaction);
    const deleteTransaction = event.target.closest('[data-delete-transaction]'); if (deleteTransaction) confirmDeleteTransaction(deleteTransaction.dataset.deleteTransaction);
    const editGoal = event.target.closest('[data-edit-goal]'); if (editGoal) openEditGoal(editGoal.dataset.editGoal);
    const deleteGoal = event.target.closest('[data-delete-goal]'); if (deleteGoal) confirmDeleteGoal(deleteGoal.dataset.deleteGoal);
    if (event.target.matches('[data-close-modal], .modal-backdrop')) closeModal();
    if (event.target.closest('[data-close-notification]')) hideNotification();
    const notification = event.target.closest('[data-notification-message]'); if (notification) showNotification(notification.dataset.notificationMessage, notification.dataset.notificationType);
    const filter = event.target.closest('[data-filter]'); if (filter) { state.filter = filter.dataset.filter; document.querySelectorAll('.filter').forEach(x => x.classList.toggle('active', x === filter)); renderTransactions(); }
  });
  $('#entry-form').addEventListener('change', event => {
    if (state.modal !== 'investment') return;
    if (event.target.name === 'investment_type') updateInvestmentFormFields();
    if (event.target.name === 'rate_type') {
      const rateFields = $('#fixed-income-rate-fields');
      if (rateFields) rateFields.innerHTML = fixedIncomeRateFields(event.target.value);
    }
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    if (!$('#modal-backdrop').hidden) closeModal();
    else if (!$('#notification').hidden) hideNotification();
  });
  renderCurrentMonth();
  renderHome(); renderTransactions(); renderGoals(); renderInvestments(); renderDashboard();
})();
