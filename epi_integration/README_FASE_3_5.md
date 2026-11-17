# Fase 3.5 — Integração End-to-End do Pipeline de Segurança

## Objetivo

Provar que os módulos já existentes (Fusion, Rules Engine, Incident Service)
funcionam corretamente **juntos**, através de contratos claros, sem
reescrever nenhum deles. Não é uma funcionalidade nova — é uma camada de
integração + testes.

## Escopo desta fase

Fluxo validado:

```
Observation (artificial) -> Fusion -> EmployeeSafetyState -> Rules Engine
    -> ComplianceEvaluation -> Incident Service -> Incident (OPEN/RESOLVED)
```

epi_identity e epi_ppe (câmera real / YOLO / reconhecimento facial) **não**
fazem parte desta fase — conforme pedido, observações são artificiais e já
chegam com `employee_id` resolvido, direto no contrato de entrada do Fusion.

## Arquitetura da integração

```
epi_integration/
├── app/
│   ├── runner.py     # sobe fusion/rules/incident como processos uvicorn isolados
│   ├── clients.py     # clientes HTTP finos (1 por serviço)
│   └── bridge.py      # tradução de contrato entre os 3 serviços (a única lógica nova)
├── tests/
│   ├── conftest.py
│   └── integration/
│       ├── test_scenarios.py          # os 10 cenários end-to-end
│       └── test_events_and_errors.py  # observabilidade + tratamento de erros
└── docs/
    ├── contracts.md          # contratos campo a campo, com os pontos de fricção
    └── payload_examples.md
```

### Por que subprocessos e não import direto

Cada módulo (`epi_fusion`, `epi_rules`, `epi_incident`, ...) define seu
próprio pacote de nível superior chamado `app`. Isso é correto dentro de
cada módulo, mas impede importar dois deles no mesmo processo Python (o
segundo `import app` sobrescreveria o primeiro em `sys.modules`). Em vez de
tocar na estrutura de pacotes de qualquer módulo existente, a integração
sobe cada serviço como um processo `uvicorn` real, isolado, e conversa com
eles por HTTP — os mesmos contratos que qualquer consumidor real usaria em
produção (cada módulo já tem seu próprio `Dockerfile`).

### A única alteração em código existente

Um endpoint novo em `epi_incident`: `POST /incidents/evaluations`. Antes
dele, o Incident Service só expunha via HTTP "abrir 1 violação" e "resolver
por id" — nada cobria o fluxo agregado de uma avaliação inteira (abrir o que
está em violação, resolver o que deixou de estar). Essa lógica agregada **já
existia e já era testada** como `IncidentService.process_evaluation`; o novo
endpoint é um repasse de uma linha para esse método. Nenhuma regra de
negócio foi criada, alterada ou duplicada. Detalhes em `docs/contracts.md`.

## Como rodar

Cada módulo (`epi_fusion`, `epi_rules`, `epi_incident`) precisa de suas
dependências instaladas no ambiente que vai rodar os testes (o runner sobe
`python -m uvicorn app.main:app` dentro do diretório de cada módulo, usando
o Python do ambiente atual — não cria venvs isoladas por módulo):

```bash
# a partir da raiz do projeto (epi_vision_projeto_completo/)
pip install -e epi_fusion -e epi_rules -e epi_incident
pip install -e epi_integration[dev]

# testes unitários de cada módulo (já existiam, devem continuar passando)
pytest epi_fusion/tests epi_rules/tests epi_incident/tests

# testes de integração da Fase 3.5 (novo)
pytest epi_integration/tests/integration -v
```

O `conftest.py` sobe fusion+rules+incident **uma vez por sessão de pytest**
(fixture `scope="session"`) e os encerra ao final. Cada teste usa um
`employee_id` único para não haver interferência de estado entre cenários
(os serviços mantêm estado em memória durante toda a sessão de testes).

## Cenários cobertos (seção 5 a 14 do pedido original)

| # | Cenário | Arquivo |
|---|---|---|
| 1 | Conformidade total, zero incidentes | `test_scenarios.py::test_scenario_1_*` |
| 2 | EPI ausente -> violação -> incidente OPEN | `test_scenario_2_*` |
| 3 | Recuperação -> incidente RESOLVED | `test_scenario_3_*` |
| 4 | NOT_VISIBLE nunca vira MISSING | `test_scenario_4_*` |
| 5 | Multi-câmera -> um único incidente | `test_scenario_5_*` |
| 6 | Idempotência (mesma avaliação 2x) | `test_scenario_6_*` |
| 7 | Conflito entre câmeras -> INDETERMINATE | `test_scenario_7_*` |
| 8 | Baixa confiança -> INDETERMINATE | `test_scenario_8_*` |
| 9 | Funcionário não identificado -> nada é aberto | `test_scenario_9_*` |
| 10 | Nova violação após resolução não reabre a antiga | `test_scenario_10_*` |

Mais: métricas de observabilidade e 7 testes de tratamento de erro
(`test_events_and_errors.py`) — payload inválido, contexto sem regra
aplicável, incidente inexistente, resolução dupla, violação malformada, e a
verificação de que um erro em um módulo não corrompe os outros.

## Critérios de aceitação — status

Todos os itens da seção 23 do pedido original foram endereçados no design e
no código. **Importante:** este ambiente de execução (sandbox usado para
gerar os arquivos) não tem acesso à internet, então não foi possível
instalar `fastapi`/`uvicorn`/`pytest` aqui para efetivamente rodar a suíte —
só a sintaxe de todos os arquivos foi verificada (`py_compile`, sem erros).
Os números reais de "quantos passaram/falharam" (seção 24 do pedido)
precisam vir da sua execução local — ver "Como rodar" acima. Se algo falhar,
me mande a saída do pytest que eu ajusto.

## Métricas de integração (seção 19)

Não foram adicionadas métricas novas (`pipeline_evaluations_total` etc.)
nesta rodada — cada serviço já expõe suas próprias métricas
(`/fusion/metrics`, `/rules/metrics/snapshot`,
`/incidents/metrics/snapshot`), inalteradas, e os testes de observabilidade
verificam esses três endpoints em conjunto. Uma métrica agregada de pipeline
exigiria um componente com estado próprio (quem chamaria os 3 serviços em
produção) — que não existe ainda nesta fase, já que a integração hoje é só
uma biblioteca de teste. Fica como próximo passo explícito abaixo.

## Limitações conhecidas

- `area`/`operation`/`role` são passados explicitamente pelo chamador —
  não há serviço de escala/turno.
- Nenhum serviço expõe histórico bruto de eventos via HTTP; testes de
  "evento" verificam efeito observável (métricas/estado), não o payload
  interno publicado no Event Bus.
- Timestamp não é propagado ponta a ponta (cada serviço usa seu próprio
  `Clock` no momento do processamento).
- A integração hoje é uma **biblioteca de teste**, não um serviço orquestrador
  rodando em produção — não há endpoint único "processar observação de
  câmera e disparar o pipeline inteiro". Isso é intencional nesta fase
  (o pedido pediu para provar que o fluxo funciona, não para criar um novo
  serviço orquestrador).

## Próximos passos (fora do escopo desta fase, por pedido explícito)

1. Camada de ALERTAS E NOTIFICAÇÕES.
2. DASHBOARD OPERACIONAL.
3. Se desejado depois: um serviço orquestrador real (não só testes) que
   consome observações de câmera continuamente e dispara o pipeline
   automaticamente — hoje isso é feito manualmente pelo chamador em cada
   teste, via `app/bridge.py`.
