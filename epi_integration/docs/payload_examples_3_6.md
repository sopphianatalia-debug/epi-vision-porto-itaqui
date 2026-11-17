# Exemplos de payload — Fase 3.6 (Identity-to-Fusion)

## 1) Cadastro do funcionário (pré-requisito para MATCHED)

`POST /employees` (epi_identity, header `Authorization: Bearer <token>`)

```json
{"registration": "SEED-0001", "name": "João Silva", "sector": "PATIO_CARGA", "role_title": "OPERADOR"}
```

Resposta: `employee_code` gerado automaticamente (ex.: `FUNC-000042`) — nunca
o nome. É esse `employee_code` que vira a "seed" usada no cadastro
biométrico e no reconhecimento mock.

`POST /employees/{id}/biometric-enrollment`

```json
{
  "frame": {"faces": [{"bbox": [0,0,100,100], "seed": "FUNC-000042", "quality": 0.95,
                        "single_face": true, "face_visible": true}]},
  "consent": true
}
```

## 2) Reconhecimento — MATCHED

`POST /recognition/match`

```json
{
  "camera_id": "CAM-01",
  "person_track_id": "TRACK-000001",
  "frame": {"faces": [{"bbox": [0,0,100,100], "seed": "FUNC-000042", "quality": 0.95,
                        "single_face": true, "face_visible": true}]}
}
```

```json
{
  "event_id": "EVT-...",
  "camera_id": "CAM-01",
  "person_track_id": "TRACK-000001",
  "employee_id": "FUNC-000042",
  "status": "MATCHED",
  "similarity_score": 1.0,
  "confidence": 0.97,
  "quality_score": 0.95,
  "requires_review": false,
  "model_version": "mock-v1"
}
```

## 3) Adaptado pela ponte para o Fusion

`app/bridge.py::identity_result_to_fusion_identity` produz:

```json
{"employee_id": "FUNC-000042", "identity_status": "MATCHED", "identity_confidence": 0.97}
```

Que alimenta `POST /fusion/observations`:

```json
{
  "camera_id": "CAM-01",
  "person_track_id": "TRACK-000001",
  "employee_id": "FUNC-000042",
  "identity_status": "MATCHED",
  "identity_confidence": 0.97,
  "ppe": {"helmet": {"status": "MISSING", "confidence": 0.94}}
}
```

## 4) Reconhecimento — UNKNOWN (não identificado)

```json
{"camera_id": "CAM-01", "frame": {"faces": [{"bbox":[0,0,100,100],"seed":"NUNCA-CADASTRADO","quality":0.9,"single_face":true,"face_visible":true}]}}
```

```json
{"status": "UNKNOWN", "employee_id": null, "confidence": null, "requires_review": false}
```

Adaptado: `{"employee_id": null, "identity_status": "UNKNOWN", "identity_confidence": 0.0}`
— o Fusion recebe a observação como **anônima**.

## 5) Reconhecimento — AMBIGUOUS (colisão de seed nos testes)

```json
{"status": "AMBIGUOUS", "employee_id": null, "confidence": 0.55, "requires_review": true}
```

## 6) Reconhecimento — UNAVAILABLE (qualidade insuficiente)

```json
{"camera_id": "CAM-01", "frame": {"faces": [{"bbox":[0,0,100,100],"seed":"x","quality":0.1,"single_face":true,"face_visible":true}]}}
```

```json
{"status": "UNAVAILABLE", "employee_id": null, "confidence": null}
```

Adaptado pela ponte (ponto de fricção 3): `{"identity_status": "NOT_IDENTIFIED", ...}`.
