# Pissa Finance — interface inicial

Interface estática, mobile-first, criada com HTML, CSS e JavaScript puro.

## Estrutura

`frontend/index.html` contém a estrutura semântica; `frontend/css/` contém os estilos; `frontend/js/mock-data.js` centraliza os dados temporários e `frontend/js/app.js` cuida de renderização, navegação e eventos locais.

## Abrir

Abra `frontend/index.html` diretamente no navegador para uma prévia local. Para servir no Docker:

```bash
docker compose up -d --build
```

Depois, acesse `http://localhost:8080` ou `http://IP_DO_SERVIDOR:8080`.

## Conexão futura com Python

Troque os dados e as funções de carregamento em `frontend/js/app.js` por chamadas como `fetch('/api/dashboard')`, `fetch('/api/transactions')` e `fetch('/api/goals')`. O HTML pode ser servido sem alterações por Flask, FastAPI ou Jinja2.
