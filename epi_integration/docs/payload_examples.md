# Exemplos de payload — Fase 3.5

## 1) Observação de câmera -> Fusion

`POST /fusion/observations` (em cada instância `epi_fusion`)

```json
{
  "camera_id": "CAM-01",
  "person_track_id": "TRACK-000001",
  "employee_id": "FUNC-000234",
  "identity_status": "MATCHED",
  "identity_confidence": 0.95,
  "ppe": {
    "helmet": {"status": "MISSING", "confidence": 0.94},
    "vest": {"status": "DETECTED", "confidence": 0.93},
    "gloves": {"status": "DETECTED", "confidence": 0.90},
    "boots": {"status": "DETECTED", "confidence": 0.91}
  }
}
```

## 2) Estado consolidado do Fusion (lido, não enviado)

`GET /fusion/employees/FUNC-000234`

```json
{
  "employee_id": "FUNC-000234",
  "identity_status": "MATCHED",
  "ppe": {
    "helmet": {"status": "MISSING", "confidence": 0.94, "cameras": ["CAM-01"]},
    "vest": {"status": "DETECTED", "confidence": 0.93, "cameras": ["CAM-01"]},
    "gloves": {"status": "DETECTED", "confidence": 0.90, "cameras": ["CAM-01"]},
    "boots": {"status": "DETECTED", "confidence": 0.91, "cameras": ["CAM-01"]}
  },
  "overall_status": "PARTIAL",
  "confidence": 0.72
}
```

## 3) Fusion -> Rules Engine

`POST /rules/evaluate` (montado por `bridge.build_rules_evaluate_payload`)

```json
{
  "employee_id": "FUNC-000234",
  "identity_status": "MATCHED",
  "area": "PATIO_CARGA",
  "operation": "MOVIMENTACAO_CARGA",
  "role": "OPERADOR",
  "evaluation_id": "EVAL-FUNC-000234-001",
  "ppe": {
    "helmet": {"status": "MISSING", "confidence": 0.94},
    "vest": {"status": "DETECTED", "confidence": 0.93},
    "gloves": {"status": "DETECTED", "confidence": 0.90},
    "boots": {"status": "DETECTED", "confidence": 0.91}
  }
}
```

## 4) Rules Engine -> Incident Service

`POST /incidents/evaluations` (a resposta do passo 3, enriquecida com
`source_cameras` por `bridge.enrich_violations_with_cameras`)

```json
{
  "evaluation_id": "EVAL-FUNC-000234-001",
  "employee_id": "FUNC-000234",
  "overall_status": "NON_COMPLIANT",
  "effective_rule_id": "RULE-PATIO-CARGA-001",
  "violations": [
    {
      "employee_id": "FUNC-000234",
      "rule_id": "RULE-PATIO-CARGA-001",
      "rule_version": 1,
      "ppe_type": "helmet",
      "observed_status": "MISSING",
      "severity": "CRITICAL",
      "reason": "helmet obrigatório e ausente (MISSING)",
      "source_cameras": ["CAM-01"]
    }
  ]
}
```

Resposta:

```json
[
  {
    "action": "CREATED",
    "incident": {
      "incident_id": "INC-000001",
      "employee_id": "FUNC-000234",
      "rule_id": "RULE-PATIO-CARGA-001",
      "rule_version": 1,
      "ppe_type": "helmet",
      "reason_code": "PPE_MISSING",
      "severity": "CRITICAL",
      "status": "OPEN",
      "source_cameras": ["CAM-01"],
      "occurrence_count": 1
    }
  }
]
```

## 5) Conflito entre câmeras (Cenário 7)

Estado consolidado com conflito não resolvido:

```json
{
  "ppe": {
    "helmet": {"status": "UNKNOWN", "confidence": 0.5, "cameras": ["CAM-01", "CAM-02"], "conflict": true}
  }
}
```

Convertido pela ponte antes do `POST /rules/evaluate`:

```json
{ "ppe": { "helmet": {"status": "CONFLICTING", "confidence": 0.5} } }
```
