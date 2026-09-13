(() => {
  const state = {
    data: window.MockData,
    filter: 'all',
    modal: null,
    transactionMode: 'create',
    editingTransactionId: null,
    goalMode: 'create',
    editingGoalId: null,
    transactions: [],
    goals: []
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
    dashboard.available_balance
  );
  $('#balance-trend').textContent = '';
  $('#balance-trend').hidden = true;
  $('#balance-caption').textContent = '';

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
  }
  
  async function renderGoals() { $('#goal-list').innerHTML = (await loadGoals()).map(goal => goalMarkup(goal, true)).join(''); }
  async function renderDashboard() {
    const d = await loadDashboard();
    $('#dashboard-stats').innerHTML = [
    ['Total recebido', d.income, 'positive'],
    ['Total gasto', d.expenses, 'negative'],
    ['Total investido', d.invested, 'positive accent'],
    ['Saldo disponível', d.available_balance, 'positive']
  ].map(([label, value, classes]) => `
    <article class="stat-card ${classes.includes('accent') ? 'accent' : ''}">
      <span>${label}</span>
      <strong class="${classes}">
        ${money(value)}
      </strong>
    </article>
  `).join('');
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
    $('#modal-title').textContent = type === 'goal' ? modalMode === 'edit' ? 'Editar meta' : 'Nova meta' : modalMode === 'edit' ? 'Editar movimentação' : 'Nova movimentação';
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

    showNotification('Movimentação excluída com sucesso', 'success');
  }

  function closeModal() {
    $('#modal-backdrop').hidden = true;
    state.modal = null;
    state.transactionMode = 'create';
    state.editingTransactionId = null;
    state.goalMode = 'create';
    state.editingGoalId = null;
  }
  document.querySelector('[data-close-modal]').addEventListener('click', closeModal);
  function parseAmount(value) { return Number(String(value).replace(/[^0-9,.-]/g, '').replace('.', '').replace(',', '.')) || 0; }
  $('#entry-form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const isGoal = state.modal === 'goal';

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
    const editGoal = event.target.closest('[data-edit-goal]'); if (editGoal) openEditGoal(editGoal.dataset.editGoal);
    const deleteGoal = event.target.closest('[data-delete-goal]'); if (deleteGoal) confirmDeleteGoal(deleteGoal.dataset.deleteGoal);
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
  renderCurrentMonth();
  renderHome(); renderTransactions(); renderGoals(); renderDashboard();
})();
