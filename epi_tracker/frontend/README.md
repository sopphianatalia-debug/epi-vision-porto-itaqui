# Frontend — EPI Safety Tracker Service (Fase 3.8B)

## O que é

Interface React (sem build tool pesada — `esbuild` puro) para o
`epi_tracker`: Dashboard, Mapa Operacional, Funcionários, EPIs,
Rastreadores, Áreas, Checkpoints, Inconsistências, Histórico e Simulação.

## Validado neste ambiente (sem internet, sem `npm install`)

Este ambiente de geração de código não tem acesso ao registro do npm
(mesma limitação já documentada em fases anteriores para `pip`). Para
ainda assim provar que o frontend funciona de verdade, usei o que já
estava disponível globalmente (`react`, `react-dom`, `esbuild` via `tsx`,
e `playwright` com Chromium já baixado em `/opt/pw-browsers`):

1. **Empacotei o bundle de verdade** com `esbuild`, embutindo React
   (sem depender de CDN) — `dist/bundle.js`, ~1.1MB.
2. **Renderizei num Chromium real** (headless, via Playwright) sem
   backend — confirmei que a interface mostra corretamente "API
   INDISPONÍVEL" em vez de quebrar, com **zero erros de JavaScript**.
3. **Construí um servidor mock mínimo** (`/tmp/mock_backend.py` — só
   biblioteca padrão do Python, sem FastAPI) implementando o mesmo
   contrato HTTP da API real, e testei o **fluxo central da seção 53**
   de ponta a ponta num navegador real:
   - Abrir a página de Funcionários -> ver FUNC-000234 em PÁTIO-02
   - Ir em Simulação -> mover TRACKER-001 para MANUTENÇÃO
   - Voltar em Funcionários -> área atualizada para MANUTENÇÃO
   - Ir no Mapa Operacional -> ver a contagem de funcionários mudar de
     área visualmente

   Todos os 7 checks desse fluxo passaram, com capturas de tela reais
   confirmando visualmente (sem CSS quebrado, sem elemento fora do
   lugar). **Isso NÃO usa o backend real** (que não pôde ser instalado
   aqui) — é a prova de que o frontend fala corretamente com qualquer
   servidor que implemente o mesmo contrato, incluindo o real.

**O que isso NÃO prova:** que o backend real (FastAPI) se comporta
exatamente como o mock em todos os detalhes. Isso precisa ser confirmado
na sua máquina, rodando os dois de verdade juntos.

## Como rodar de verdade (na sua máquina, com internet)

```bash
# 1) Backend
cd epi_tracker
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --port 8010

# 2) Frontend — instalar dependências de verdade
cd frontend
npm install react react-dom esbuild --save

# 3) Empacotar
npx esbuild src/main.jsx --bundle --outfile=dist/bundle.js \
  --loader:.jsx=jsx --jsx-factory=React.createElement --jsx-fragment=React.Fragment \
  --format=iife --platform=browser

# 4) Servir (qualquer servidor estático)
python3 -m http.server 8020
# abra http://127.0.0.1:8020/index.html
```

Se preferir Vite (recomendado para desenvolvimento contínuo, com hot
reload) — basta `npm create vite@latest` num projeto novo e mover os
arquivos de `src/` para lá; o código não usa nenhuma API específica do
esbuild, só JSX + fetch puro.

## Configuração da URL da API

`index.html` define `window.__EPI_TRACKER_API__` — mude isso (ou passe a
URL certa) se o backend não estiver em `http://127.0.0.1:8010`.

## Decisões de escopo (dado o tamanho da fase)

- **Sem React Router** — navegação por hash simples (`window.location.hash`),
  já que não há acesso para instalar `react-router-dom`. Funciona
  perfeitamente para este caso de uso (SPA de página única por vez).
- **Detalhe de EPI/Funcionário/Tracker** em modal, não em rota própria —
  mais simples de implementar sem router, e a experiência é equivalente.
- **CORS liberado amplamente** no backend (`allow_origins=["*"]"`) — este
  serviço não expõe biometria nem PII sensível além de `employee_id` (já
  em texto claro em todo o sistema).
- **Sem testes automatizados de frontend** (Vitest/Testing Library) — não
  há acesso para instalar essas dependências aqui. A validação foi feita
  via Playwright de ponta a ponta (mais forte que testes unitários de
  componente, mas não substitui uma suíte formal). Recomendo adicionar
  `@testing-library/react` + `vitest` quando estiver na sua máquina.
