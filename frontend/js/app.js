(() => {
  const state = {
    data: window.MockData,
    filter: 'all',
    modal: null,
    transactionMode: 'create',
    editingTransactionId: null,
    transactions: []
  };
  const money = value => value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const $ = selector => document.querySelector(selector);
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

  // Futuramente, estas funções podem usar fetch('/api/dashboard'), fetch('/api/transactions') e fetch('/api/goals').
  async function loadDashboard() { return state.data.dashboard; }
  async function loadTransactions() { 
    const response = await fetch('/api/transactions/');

    if (!response.ok) throw new Error('Erro ao carregar transações');

    state.transactions = await response.json();
    return state.transactions;
   }
  async function loadGoals() { return state.data.goals; }

  const transactionIcon = type => ({ income: '↓', expense: '↑', investment: '◇' }[type]);
  const transactionLabel = type => ({ income: 'Entrada', expense: 'Saída', investment: 'Investimento' }[type]);
  function transactionMarkup(item, showActions = false) {
    const sign = item.type === 'income' ? '+' : '-';
    const actions = showActions ? `
      <div class="transaction-actions" aria-label="Ações de ${item.description}">
        <button class="transaction-action" type="button" data-edit-transaction="${item.id}" aria-label="Editar ${item.description}" title="Editar">✎</button>
        <button class="transaction-action danger" type="button" data-delete-transaction="${item.id}" aria-label="Excluir ${item.description}" title="Excluir">×</button>
      </div>` : '';
    return `
    <article class="transaction ${item.type}">
      <div class="transaction-icon">${transactionIcon(item.type)}</div>
      <div class="transaction-main">
        <strong>${item.description}</strong>
        <span>${transactionLabel(item.type)} • ${item.category || 'Sem categoria'}</span>
      </div>
      <div class="transaction-value">
        <strong>${sign} ${money(item.amount)}</strong>
        <span>${item.transaction_date}</span>
      </div>${actions}
    </article>`;
  }
  
  function goalMarkup(goal) {
    const percentage = Math.min(100, Math.round((goal.current / goal.target) * 100));
    const remaining = Math.max(0, goal.target - goal.current);
    return `<article class="goal-card"><div class="goal-top"><strong>${goal.name}</strong><span>${percentage}%</span></div><div class="goal-numbers"><span>Guardado <strong>${money(goal.current)}</strong></span><span>Meta ${money(goal.target)}</span></div><div class="progress ${goal.color}"><i style="width:${percentage}%"></i></div><div class="goal-numbers"><span>Faltam ${money(remaining)}</span><span>${percentage}% concluído</span></div></article>`;
  }
  async function renderHome() {
    const dashboard = await loadDashboard(), goals = await loadGoals(), transactions = await loadTransactions();
    $('#net-worth').textContent = money(dashboard.netWorth);
    $('#home-summary').innerHTML = [ ['Total guardado', dashboard.saved, 'positive'], ['Rendimento', dashboard.earnings, 'positive'], ['Gastos do mês', dashboard.expenses, 'negative'] ].map(([label, value, kind]) => `<article class="mini-card"><span>${label}</span><strong class="${kind}">${kind === 'negative' ? '− ' : '+ '}${money(value)}</strong></article>`).join('');
    $('#home-goals').innerHTML = goals.map(goalMarkup).join('');
    $('#recent-transactions').innerHTML = transactions.slice(0, 3).map(transactionMarkup).join('');
  }
  
  async function renderTransactions() {
    const dashboard = await loadDashboard(), items = await loadTransactions();
    
    const income = items
      .filter(x => x.type === 'income')
      .reduce((sum, x) => sum + x.amount, 0);
    
    const outgoing = items
      .filter(x => x.type !== 'income')
      .reduce((sum, x) => sum + x.amount, 0);
    
    $('#month-balance').textContent = money(income - outgoing);
    $('#month-income').textContent = '+ ' + money(income);
    $('#month-expense').textContent = '− ' + money(outgoing);
    
    const visible = state.filter === 'all' ? items : items.filter(x => x.type === state.filter);
    
    $('#transaction-list').innerHTML = visible.length ? visible.map(item => transactionMarkup(item, true)).join('') : '<p class="page-intro">Nenhuma movimentação encontrada.</p>';
    void dashboard;
  }
  
  async function renderGoals() { $('#goal-list').innerHTML = (await loadGoals()).map(goalMarkup).join(''); }
  function renderDashboard() {
    const d = state.data.dashboard;
    $('#dashboard-stats').innerHTML = [['Total recebido', d.income, 'positive'], ['Total gasto', d.expenses, 'negative'], ['Total guardado', d.saved, 'positive accent'], ['Taxa de economia', d.savingRate + '%', 'positive']].map(([label, value, classes]) => `<article class="stat-card ${classes.includes('accent') ? 'accent' : ''}"><span>${label}</span><strong class="${classes}">${typeof value === 'number' ? money(value) : value}</strong></article>`).join('');
    $('#expense-total').textContent = money(d.expenses);
    $('#expense-legend').innerHTML = state.data.categories.map(c => `<div class="legend-item"><span><i style="background:${c.color}"></i>${c.name}</span><strong>${money(c.value)}</strong></div>`).join('');
    const max = Math.max(...state.data.monthly.map(x => x.value));
    $('#line-chart').innerHTML = state.data.monthly.map(x => `<i class="line-bar" style="height:${Math.max(18, x.value / max * 100)}%" aria-label="${x.label}: ${money(x.value)}"></i>`).join('');
    $('#chart-months').innerHTML = state.data.monthly.map(x => `<span>${x.label}</span>`).join('');
  }
  function navigate(screen) {
    document.querySelectorAll('.screen').forEach(item => item.classList.toggle('active', item.id === screen));
    document.querySelectorAll('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.screen === screen));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  function formMarkup(type) {
    if (type === 'goal') return `<div class="form-grid"><label class="field">Nome da meta<input name="name" required placeholder="Ex.: Viagem"></label><div class="form-row"><label class="field">Valor alvo<input name="target" required inputmode="decimal" placeholder="R$ 0,00"></label><label class="field">Valor inicial<input name="initial" inputmode="decimal" placeholder="R$ 0,00"></label></div><label class="field">Prazo (opcional)<input name="deadline" type="month"></label><div class="form-actions"><button class="secondary-button" type="button" data-close-modal>Cancelar</button><button class="primary-button form-submit" type="submit">Adicionar meta</button></div></div>`;
    return `<div class="form-grid"><label class="field">Tipo<select name="type"><option value="income">Entrada</option><option value="expense">Saída</option><option value="investment">Investimento</option></select></label><label class="field">Descrição<input name="description" required placeholder="Ex.: Mercado"></label><div class="form-row"><label class="field">Valor<input name="amount" required inputmode="decimal" placeholder="R$ 0,00"></label><label class="field">Categoria<input name="category" required placeholder="Ex.: Alimentação"></label></div><label class="field">Data<input name="date" type="date" value="2026-09-10"></label><label class="field">Observação<textarea name="note" placeholder="Opcional"></textarea></label><div class="form-actions"><button class="secondary-button" type="button" data-close-modal>Cancelar</button><button class="primary-button form-submit" type="submit">Adicionar</button></div></div>`;
  }
  function openModal(type, transactionMode = 'create') {
    state.modal = type;
    if (type === 'transaction') {
      state.transactionMode = transactionMode;
      if (transactionMode === 'create') state.editingTransactionId = null;
    }
    $('#modal-title').textContent = type === 'goal' ? 'Nova meta' : transactionMode === 'edit' ? 'Editar movimentação' : 'Nova movimentação';
    $('#entry-form').innerHTML = formMarkup(type);
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

    state.editingTransactionId = transaction.id;
    openModal('transaction', 'edit');
    fillTransactionForm(transaction);
    $('#entry-form [type="submit"]').textContent = 'Salvar alterações';
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

    showNotification('Movimentação excluída com sucesso', 'success');
  }

  function closeModal() {
    $('#modal-backdrop').hidden = true;
    state.modal = null;
    state.transactionMode = 'create';
    state.editingTransactionId = null;
  }
  document.querySelector('[data-close-modal]').addEventListener('click', closeModal);
  function parseAmount(value) { return Number(String(value).replace(/[^0-9,.-]/g, '').replace('.', '').replace(',', '.')) || 0; }
  $('#entry-form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const isGoal = state.modal === 'goal';

    if (isGoal) {
    state.data.goals.unshift({
      id: Date.now(),
      name: form.get('name'),
      current: parseAmount(form.get('initial')),
      target: parseAmount(form.get('target')),
      color: 'green'
    });

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
    const editTransaction = event.target.closest('[data-edit-transaction]'); if (editTransaction) openEditTransaction(editTransaction.dataset.editTransaction);
    const deleteTransaction = event.target.closest('[data-delete-transaction]'); if (deleteTransaction) confirmDeleteTransaction(deleteTransaction.dataset.deleteTransaction);
    if (event.target.matches('[data-close-modal], .modal-backdrop')) closeModal();
    if (event.target.closest('[data-close-notification]')) hideNotification();
    const notification = event.target.closest('[data-notification-message]'); if (notification) showNotification(notification.dataset.notificationMessage, notification.dataset.notificationType);
    const filter = event.target.closest('[data-filter]'); if (filter) { state.filter = filter.dataset.filter; document.querySelectorAll('.filter').forEach(x => x.classList.toggle('active', x === filter)); renderTransactions(); }
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    if (!$('#modal-backdrop').hidden) closeModal();
    else if (!$('#notification').hidden) hideNotification();
  });
  renderHome(); renderTransactions(); renderGoals(); renderDashboard();
})();
