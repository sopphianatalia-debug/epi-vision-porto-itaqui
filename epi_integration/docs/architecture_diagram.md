# Diagrama — Fase 3.5

```
                    ┌───────────────┐
                    │    Camera     │   (fora do escopo desta fase —
                    │  (YOLO real)  │    observações artificiais no lugar)
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │  Observation  │  {camera_id, person_track_id,
                    │  (artificial) │   employee_id, ppe: {status, confidence}}
                    └───────┬───────┘
                            │  POST /fusion/observations
                            ▼
                 ┌─────────────────────┐
                 │   epi_fusion         │  consolida N câmeras por employee_id
                 │   FusionService       │  NOT_VISIBLE nunca -> MISSING
                 └──────────┬───────────┘
                            │  GET /fusion/employees/{id}
                            ▼
              ┌───────────────────────────┐
              │  EmployeeSafetyState       │  {ppe: {tipo: {status,
              │  (evidência consolidada)   │   confidence, cameras[]}}}
              └──────────────┬─────────────┘
                              │
                    ╔═════════▼═════════╗
                    ║   epi_integration   ║   <-- camada desta fase
                    ║   app/bridge.py     ║       (só tradução de contrato,
                    ║                     ║        nenhuma regra nova)
                    ║  - UNKNOWN+conflict ║
                    ║    -> CONFLICTING   ║
                    ╚═════════┬═════════╝
                              │  POST /rules/evaluate
                              ▼
                 ┌─────────────────────┐
                 │   epi_rules           │  regra efetiva por área/operação/
                 │   RulesEngine          │  função, debounce/histerese,
                 └──────────┬───────────┘  explicabilidade
                            │
                            ▼
              ┌───────────────────────────┐
              │  ComplianceEvaluation      │  {overall_status, violations[],
              │  (COMPLIANT/NON_COMPLIANT/ │   effective_rule_id, evaluation_id}
              │   PARTIAL/INDETERMINATE/   │
              │   NOT_EVALUATED)           │
              └──────────────┬─────────────┘
                              │
                    ╔═════════▼═════════╗
                    ║   epi_integration   ║
                    ║   app/bridge.py     ║
                    ║                     ║
                    ║  + source_cameras   ║  (Rules não conhece câmera;
                    ║    anexado por      ║   integração busca no estado
                    ║    ppe_type          ║   do Fusion e anexa)
                    ╚═════════┬═════════╝
                              │  POST /incidents/evaluations  (endpoint novo
                              │                                 desta fase)
                              ▼
                 ┌─────────────────────┐
                 │   epi_incident        │  dedup por (employee, rule, ppe,
                 │   IncidentService      │  tipo_violação) — NÃO por câmera;
                 └──────────┬───────────┘  idempotência por evaluation_id
                            │
                            ▼
                    ┌───────────────┐
                    │   Incident     │  status: OPEN | RESOLVED
                    │  {incident_id, │
                    │   source_cameras,
                    │   occurrence_count,
                    │   duration_seconds}
                    └───────────────┘
```

## Módulos fora do fluxo desta fase

```
epi_ppe        -> detecção real (YOLO) por câmera — ainda simulado
epi_compliance -> (módulo paralelo, não conectado nesta integração)
```

Nesta fase, `employee_id` chega pronto na `Observation` artificial — o papel
de `epi_identity` e `epi_ppe` é simulado pelos dados de teste, conforme
pedido explícito de não conectar câmera real/YOLO nesta etapa.

---

# Fase 3.6 — Identity-to-Fusion Integration

```
                    ┌───────────────┐
                    │    Camera     │   (fora do escopo — YOLO real ainda
                    │  (YOLO real)  │    não conectado)
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │  Observation  │  ppe artificial, SEM employee_id
                    │  (artificial) │  confiável ainda
                    └───────┬───────┘
                            │  POST /recognition/match  {camera_id,
                            │   person_track_id, frame: {faces:[{seed,...}]}}
                            ▼
                 ┌─────────────────────┐
                 │   epi_identity        │  provider MOCK (determinístico)
                 │   FaceRecognitionSvc   │  MATCHED | LOW_CONFIDENCE |
                 └──────────┬───────────┘  AMBIGUOUS | UNKNOWN | UNAVAILABLE
                            │
                            ▼
              ┌───────────────────────────┐
              │  IdentityResult             │  {status, employee_id?,
              │  (MatchResponse)            │   confidence, requires_review}
              └──────────────┬─────────────┘
                              │
                    ╔═════════▼═════════╗
                    ║   epi_integration   ║   <-- adaptador desta fase
                    ║   app/bridge.py     ║       (identity_result_to_
                    ║                     ║        fusion_identity)
                    ║  RecognitionStatus  ║
                    ║    -> IdentityStatus ║
                    ║  UNAVAILABLE ->     ║
                    ║    NOT_IDENTIFIED   ║
                    ╚═════════┬═════════╝
                              │  POST /fusion/observations
                              │  {employee_id (só se MATCHED),
                              │   identity_status, identity_confidence, ppe}
                              ▼
                 ┌─────────────────────┐
                 │   epi_fusion           │  (inalterado desde a Fase 3.1)
                 │   FusionService         │  JOINABLE_IDENTITY = {MATCHED}
                 └──────────┬───────────┘
                            │
                            ▼
                 ... segue exatamente o fluxo da Fase 3.5
                 (EmployeeSafetyState -> Rules -> Incident) ...
```

## Responsabilidades (seção 27 do pedido) — inalteradas

```
Identity:  "Quem provavelmente é?"           -> IdentityResult
Fusion:    "Qual é o estado consolidado?"     -> EmployeeSafetyState
Rules:     "Está em conformidade?"            -> ComplianceEvaluation
Incident:  "Como gerenciar a ocorrência?"     -> Incident
```

Nenhuma dessas fronteiras foi cruzada pelo adaptador — ele só traduz
vocabulário (enum) entre Identity e Fusion, nunca decide nada.

