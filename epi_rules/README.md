# EPI Vision — Fase 3.3: Rules Engine

Motor de regras de conformidade de EPIs. Recebe o **estado consolidado** de um
funcionário produzido pelo `FusionService` (Fase 3.1) e responde a uma única
pergunta:

> "Dado este funcionário, neste contexto (área/operação/função), com este estado
> consolidado e considerando estas regras de segurança, ele está em conformidade?"

Ele **não** acessa câmera, não roda YOLO, não faz reconhecimento facial, não faz
Re-ID e não duplica a fusão. Trabalha exclusivamente com dados estruturados.

## Cadeia do sistema

```
Módulo 1 (employee_id) → Módulo 2 (PPE) → Fase 3.1 (FusionService → EmployeeSafetyState)
   → Fase 3.3 (Rules Engine → ComplianceEvaluation → Violation)
   → Fase 3.4 futura (Incident Service → Alert → Dashboard)
```

## Instalação e execução

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
# docs interativas: http://localhost:8000/docs
```

## Testes

```bash
pytest -q
```

## Avaliação rápida (debug, sem câmera)

```bash
curl -X POST http://localhost:8000/api/v1/rules/evaluate \
  -H "Content-Type: application/json" -d '{
    "employee_id": "FUNC-000234",
    "area": "PATIO_CARGA",
    "operation": "MOVIMENTACAO_CARGA",
    "role": "OPERADOR",
    "ppe": {
      "helmet": {"status": "DETECTED", "confidence": 0.98},
      "vest":   {"status": "DETECTED", "confidence": 0.97},
      "gloves": {"status": "MISSING",  "confidence": 0.93},
      "boots":  {"status": "DETECTED", "confidence": 0.96}
    }
  }'
```

## Endpoints

| Método | Rota | Descrição |
|-------|------|-----------|
| POST | `/api/v1/rules/evaluate` | Avalia um EmployeeSafetyState (real ou artificial) |
| GET | `/api/v1/rules/evaluations/{id}` | Recupera uma avaliação (auditoria) |
| GET | `/api/v1/rules/employees/{id}/compliance` | Última avaliação do funcionário |
| GET | `/api/v1/rules/violations` | Violações recentes |
| GET/POST | `/api/v1/rules` | Listar / criar regra |
| GET/PUT/DELETE | `/api/v1/rules/{id}` | Obter / nova versão / remover |
| GET | `/api/v1/rules/{id}/versions` | Histórico de versões |
| GET | `/api/v1/rules/metrics/snapshot` | Métricas |

Veja `docs/architecture.md` para as decisões de projeto.
