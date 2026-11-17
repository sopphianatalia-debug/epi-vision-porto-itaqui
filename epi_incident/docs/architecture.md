# Arquitetura — Fase 3.4 Incident Service

## Posição na cadeia

```
Câmeras → Visão/Detecção → Identificação → FusionService → EmployeeSafetyState
   → Rules Engine (DECISÃO de conformidade)
   → Incident Service (GESTÃO da ocorrência)
   → Event Bus / API / Histórico
```

Regra de ouro: o Incident Service **não** é um segundo Rules Engine. Ele nunca
redecide conformidade nem reaplica debounce/histerese — confia nas transições já
confirmadas pelo Rules Engine.

## Entrada

Dois caminhos, ambos com dados estruturados:

1. `record_violation(ViolationInput)` — uma violação confirmada
   (`VIOLATION_DETECTED` / `POST /incidents`).
2. `process_evaluation(EvaluationInput)` — uma `ComplianceEvaluation` inteira do
   Rules Engine; abre para cada violação e resolve o que saiu de violação.

`EvaluationInput.from_rules_dict()` e `ViolationInput.from_rules_violation()`
adaptam a saída real do Rules Engine sem acoplar os pacotes.

## Ciclo de vida

```
NON_COMPLIANT confirmado ──▶ existe incidente OPEN para a chave?
                              ├─ não  ▶ cria incidente (INC-seq), occurrence=1, INCIDENT_CREATED
                              └─ sim  ▶ evaluation_id já visto?
                                        ├─ sim ▶ NOOP (idempotência)
                                        └─ não ▶ occurrence++, INCIDENT_UPDATED
recuperação (COMPLIANT / EPI fora das violações) ──▶ OPEN → RESOLVED, INCIDENT_RESOLVED
nova violação após RESOLVED ──▶ novo incidente (não reabre o histórico)
```

## Decisões

- **Chave de deduplicação:** `employee_id | rule_id | ppe_type | violation_type`.
  Sem `camera_id` — multi-câmera é uma ocorrência só (câmeras vão para
  `source_cameras`). Um incidente por violação/EPI.
- **Idempotência:** conjunto de `evaluation_id` processados por incidente aberto.
  Reentrega do mesmo evento é NOOP.
- **`occurrence_count`:** distingue "um incidente persistente" de "N incidentes".
- **Estados inconclusivos** (`INDETERMINATE`, `PARTIAL`, `UNKNOWN`,
  `CONFLICTING`, `NOT_EVALUATED`) e `employee_id` ausente: não abrem nem encerram.
- **Severidade:** herdada do Rules Engine, nunca recalculada.
- **Clock injetável:** toda marcação temporal e duração usam o `Clock`
  (testes com `FakeClock`), nunca `datetime.now()` direto.
- **Auditoria:** incidentes resolvidos permanecem (sem DELETE); cada um preserva
  `evaluation_id/rule_id/rule_version/reason_code/reason/severity/timestamps`.
- **Privacidade:** apenas dados estruturados; nenhum dado biométrico em modelos,
  eventos ou logs.

## Estrutura

```
app/
├── domain/          # enums + models (ViolationInput, EvaluationInput, Incident)
├── infrastructure/  # clock, event_bus, repository (memória, IDs sequenciais, índice de abertos)
├── observability/   # metrics + logs estruturados (sem biometria)
├── service.py       # IncidentService (ciclo de vida)
└── api/             # schemas, deps, routes
```
