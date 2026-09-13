/* Dados temporários: substitua os retornos destas estruturas por fetch('/api/...') futuramente. */
window.MockData = {
  dashboard: { netWorth: 327.50, monthlyChange: 82, saved: 200, earnings: 1.83, expenses: 547, income: 947, savingRate: 42 },
  goals: [
    { id: 1, name: 'Dragão Chinês', current: 640, target: 2000, color: 'purple' },
    { id: 2, name: 'Reserva de emergência', current: 700, target: 5000, color: 'green' }
  ],
  transactions: [
    { id: 1, description: 'Guardado', category: 'Reserva', amount: 100, type: 'investment', date: '08 set' },
    { id: 2, description: 'Guardinha', category: 'Lazer', amount: 80, type: 'expense', date: '06 set' },
    { id: 3, description: 'Tela celular', category: 'Tecnologia', amount: 367, type: 'expense', date: '03 set' },
    { id: 4, description: 'Freelance', category: 'Trabalho', amount: 947, type: 'income', date: '02 set' }
  ],
  categories: [
    { name: 'Tecnologia', value: 367, color: '#fe6d63' }, { name: 'Lazer', value: 80, color: '#edb65b' }, { name: 'Outros', value: 100, color: '#7f72ed' }
  ],
  monthly: [{ label: 'Abr', value: 110 }, { label: 'Mai', value: 185 }, { label: 'Jun', value: 165 }, { label: 'Jul', value: 270 }, { label: 'Ago', value: 245 }, { label: 'Set', value: 327.5 }]
};
