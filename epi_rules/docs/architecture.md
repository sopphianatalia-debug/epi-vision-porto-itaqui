# Arquitetura — Fase 3.3 Rules Engine

## Princípio: Observação → Regra → Decisão

Três responsabilidades separadas:

- **Observação** (Módulos 1–2): "capacete detectado com confiança 0.97".
- **Consolidação** (Fase 3.1 / FusionService): "FUNC-000234 possui capacete DETECTED".
- **Decisão** (esta fase): "para esta atividade, capacete é obrigatório → requisito atendido".

O detector nunca decide se algo é obrigatório; isso é exclusivo do Rules Engine.

## Entrada e saída

- **Entrada:** `EmployeeSafetyStateInput` = `EvaluationContext` (employee_id, área,
  operação, função, identity_status, timestamp) + `ppe: {tipo → (status, confidence)}`.
- **Saída:** `ComplianceEvaluation` (auditável) com `rule_results`, `overall_status`,
  `violations` e `explanation`.

## Fluxo de avaliação

1. **Idempotência** — se `evaluation_id` já foi processado, devolve o resultado
   anterior sem reprocessar nem re-emitir eventos.
2. **Identidade** — sem `employee_id` (ou `NOT_IDENTIFIED`) e `evaluate_anonymous=false`
   → `NOT_EVALUATED` (não inventa identidade).
3. **Seleção de regras** — filtra regras ativas, vigentes e compatíveis com o
   contexto; resolve a **regra efetiva** por `(especificidade, prioridade, versão)`.
   Regra específica sobrescreve genérica de forma explícita.
4. **Avaliação por requisito** — para cada EPI da regra, mapeia
   `(status observado + confiança + políticas)` em um resultado explicável.
5. **Debounce/histerese** — estabiliza a decisão ao longo do tempo (abaixo).
6. **Agregação** — combina os requisitos no status da regra e no `overall_status`.
7. **Eventos + persistência + métricas** — publica eventos, grava a avaliação
   imutável e as violações, atualiza métricas.

## Estados e políticas (o ponto crítico)

Cada status inconclusivo tem uma **política configurável** por requisito. Nada é
convertido silenciosamente:

| Status observado | Tratamento padrão | Configurável via |
|------------------|-------------------|------------------|
| DETECTED/PROPER/PRESENT + conf ok | COMPLIANT | `allowed_statuses`, `minimum_confidence` |
| DETECTED + conf < threshold | **LOW_CONFIDENCE → INDETERMINATE** | `low_confidence_policy` |
| MISSING | NON_COMPLIANT | — (evidência de ausência) |
| IMPROPER | NON_COMPLIANT | `allowed_statuses` |
| **NOT_VISIBLE** | **INDETERMINATE (nunca MISSING)** | `not_visible_policy` |
| NOT_OBSERVED | INDETERMINATE | `not_observed_policy` |
| UNKNOWN | INDETERMINATE | `unknown_policy` |
| CONFLICTING | INDETERMINATE | `conflicting_policy` |

> **Regra crítica:** `NOT_VISIBLE` nunca vira `MISSING` automaticamente. Se a
> câmera não vê as botas, o resultado é indeterminado — não uma violação.

## Agregação → `overall_status`

Considerando apenas requisitos que "contam" (exclui `NOT_APPLICABLE` de opcionais):

- qualquer `NON_COMPLIANT` → **NON_COMPLIANT**;
- todos `COMPLIANT` → **COMPLIANT**;
- mistura de `COMPLIANT` + `INDETERMINATE` → **INDETERMINATE** (padrão) ou
  **PARTIAL** (se `indeterminate_rollup=PARTIAL` na regra);
- só `INDETERMINATE` → **INDETERMINATE**.

Decisão documentada: o padrão é **INDETERMINATE** (conservador — não é possível
_confirmar_ conformidade total), atendendo aos cenários de aceitação 3–5. `PARTIAL`
fica disponível por configuração para quem quiser distinguir "parcialmente confirmado".

## Debounce temporal e histerese

Estado por `(employee_id, rule_id, ppe_type)` com relógio injetável:

- Uma condição `NON_COMPLIANT` só vira **violação confirmada** após
  `min_violation_seconds` contínuos (evita violação por 1 frame / 300 ms).
- Uma recuperação só encerra a violação após `min_recovery_seconds` contínuos de
  conformidade (**histerese** — evita abrir/fechar ocorrência a cada frame).
- Oscilação rápida (MISSING/DETECTED/MISSING) não gera ocorrência.

O `overall_status` reflete o estado **instantâneo** (a conformidade "agora");
debounce/histerese governam a **confirmação da violação** e os eventos de
`VIOLATION_DETECTED` / `VIOLATION_RESOLVED` — que são o que o Incident Service usa
para abrir/encerrar ocorrências.

## Versionamento e auditoria

- `RuleRepository` guarda **todas as versões**; `PUT` cria uma nova versão e mantém
  as anteriores. A avaliação registra `rule_id` + `rule_version` usados.
- `ComplianceEvaluation` é imutável e recuperável por `evaluation_id`. Mudar uma
  regra depois **não** altera avaliações históricas.

## Explainability

Cada requisito carrega `reason_code` + texto (ex.: "gloves obrigatório e ausente
(MISSING)"; "helmet confiança 0.55 < 0.85, política LOW_CONFIDENCE=INDETERMINATE").
A avaliação tem uma `explanation` consolidada.

## Eventos (para o Incident Service)

`RULE_EVALUATION_STARTED`, `RULE_EVALUATED`, `PPE_REQUIREMENT_FAILED`,
`VIOLATION_DETECTED`, `VIOLATION_RESOLVED`, `COMPLIANCE_STATUS_CHANGED`,
`EVALUATION_INDETERMINATE`, `LOW_CONFIDENCE_DETECTED`, `RULE_NOT_FOUND`.

O Incident Service (Fase 3.4) assina o event bus: em `VIOLATION_DETECTED` abre
ocorrência; em `VIOLATION_RESOLVED` encerra; em `COMPLIANCE_STATUS_CHANGED`
atualiza. Nenhuma lógica de incidente é implementada aqui.

## Preparação para a Fase 3.2

O Rules Engine recebe `employee_id` + `EmployeeSafetyState` independentemente de
_como_ a identidade foi resolvida. Calibração espacial e Re-ID (Fase 3.2) mudam a
fusão, não este motor.

## Estrutura

```
app/
├── domain/         # enums + entidades (SafetyRule, PPERequirement, ComplianceEvaluation, Violation)
├── rules/          # seleção (aplicabilidade + resolução) + regras seed
├── evaluation/     # requirement_evaluator, debounce, engine (orquestrador)
├── infrastructure/ # clock, event_bus, repositories (regras versionadas, avaliações, violações)
├── observability/  # métricas + logs estruturados (sem biometria)
└── api/            # schemas, deps, routes
```
