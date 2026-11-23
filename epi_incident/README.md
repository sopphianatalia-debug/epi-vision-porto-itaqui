# EPI Vision — Fase 3.4: Incident Service

Transforma uma **violação já confirmada** pelo Rules Engine (Fase 3.3) em um
**incidente rastreável** e gerencia seu ciclo de vida. Ele **não** descobre a
violação — recebe a decisão pronta e responde a outra pergunta:

> "Como registrar, acompanhar, deduplicar e encerrar esta ocorrência?"

## O que ele faz / não faz

Faz: cria incidentes, deduplica, mantém estado, atualiza, resolve, registra
timestamps/duração, mantém severidade e vínculos (employee/rule/evaluation),
histórico, consultas, eventos, auditoria e explicabilidade.

Não faz (pertence a fases anteriores): câmera, OpenCV, YOLO, Face ID, Re-ID,
tracking, fusão, cálculo de confidence, decisão de EPI obrigatório, Rules Engine,
debounce/histerese (confia nas transições do Rules Engine), análise de imagem.

## Cadeia

```
FusionService → EmployeeSafetyState → Rules Engine → DECISÃO (ComplianceEvaluation/Violation)
   → Incident Service → GESTÃO DA OCORRÊNCIA → Event Bus / API / Histórico
```

O Rules Engine decide *"existe violação?"*. O Incident Service decide
*"como registrar e encerrar a ocorrência?"*. As responsabilidades não se misturam.

## Modelo Incident

`incident_id, employee_id, evaluation_id, last_evaluation_id, rule_id,
rule_version, violation_type, ppe_type, reason_code, reason, severity, status,
opened_at, updated_at, resolved_at, duration_seconds, occurrence_count, source,
source_cameras, metadata`.

Estados: **OPEN → RESOLVED** (mínimo necessário; sem estados supérfluos).

## Deduplicação

Chave lógica: **`employee_id | rule_id | ppe_type | violation_type`**.

`camera_id` **não** entra na chave: a mesma violação vista por várias câmeras é
UMA ocorrência do funcionário (as câmeras são guardadas em `source_cameras` para
auditoria). EPIs diferentes geram incidentes separados. Enquanto houver incidente
**aberto** para a mesma chave, novas confirmações **não** criam outro — apenas
incrementam `occurrence_count`.

## Idempotência

Cada incidente aberto guarda os `evaluation_id` já aplicados. Se o mesmo
`VIOLATION_DETECTED` (mesmo `evaluation_id`) chegar duas vezes, a segunda é
**NOOP**: não incrementa `occurrence_count` nem emite evento. `occurrence_count`
sobe uma vez por `evaluation_id` distinto que confirmar a violação.

## Resolução e reabertura

Quando o Rules Engine indica recuperação (`VIOLATION_RESOLVED`, ou uma avaliação
`COMPLIANT`/`NON_COMPLIANT` onde o EPI deixou de estar violado), o incidente vai
**OPEN → RESOLVED** com `resolved_at`, `updated_at` e `duration_seconds`
(via clock injetável). Um incidente resolvido **não** é reaberto: uma nova
violação da mesma condição cria um **novo** incidente, preservando o histórico.

`duration_seconds`: aberto → `now - opened_at`; resolvido → `resolved_at - opened_at`.

## API

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/incidents` | Registra violação. 201 se cria; 200 se deduplica/atualiza |
| GET | `/api/v1/incidents` | Lista com filtros `employee_id`, `status`, `severity`, `ppe_type` |
| GET | `/api/v1/incidents/{id}` | Consulta um incidente (404 se inexistente) |
| POST | `/api/v1/incidents/{id}/resolve` | Resolve (404 inexistente, 409 já resolvido) |
| GET | `/api/v1/incidents/metrics/snapshot` | Métricas |

### Exemplo — POST /incidents

```json
{
  "employee_id": "FUNC-000234",
  "evaluation_id": "EVAL-000001",
  "rule_id": "RULE-PATIO-CARGA-001",
  "rule_version": 3,
  "ppe_type": "helmet",
  "violation_type": "PPE_VIOLATION",
  "reason_code": "PPE_MISSING",
  "reason": "helmet obrigatório e ausente",
  "severity": "HIGH"
}
```

## Eventos (Event Bus)

`INCIDENT_CREATED` (uma vez, na criação), `INCIDENT_UPDATED` (nova confirmação
de incidente aberto), `INCIDENT_RESOLVED` (uma vez, na resolução). Payload só com
dados estruturados — **nunca** imagem/frame/embedding/template/biometria.

## Integração com o Rules Engine

`IncidentService.process_evaluation(EvaluationInput.from_rules_dict(...))` consome
diretamente o `ComplianceEvaluation.to_dict()` do Rules Engine: abre para cada
violação confirmada e resolve o que deixou de estar em violação.
`INDETERMINATE`, `PARTIAL`, `NOT_EVALUATED` (e `employee_id` ausente) **não**
abrem nem encerram incidentes — o contrato do Rules Engine é respeitado.

O Rules Engine expõe `observed_status` na violação (não `reason_code`); o adapter
deriva o `reason_code` de forma explícita (`MISSING → PPE_MISSING`,
`IMPROPER → PPE_IMPROPER`, senão `PPE_VIOLATION`).

## Severidade e auditoria

A severidade **vem do Rules Engine** e não é recalculada. Cada incidente preserva
`evaluation_id`, `rule_id`, `rule_version`, `reason_code`, `reason`, `severity` e
timestamps — uma mudança futura de regra não altera incidentes históricos.
Não há DELETE: o sistema é orientado a auditoria.

## Privacidade

Armazena apenas dados estruturados (`employee_id`, `camera_id`, `ppe_type`,
`status`, `rule_id`, `evaluation_id`, `reason_code`, `severity`, timestamps).
Nunca imagens, vídeos, frames, embeddings, templates ou vetores biométricos.

## Rodar / testar

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload   # http://localhost:8000/docs
pytest -q                        # 45 testes (unit + cenários + API)
```

## Revisão humana e persistência (Fase 1 do Mapa Operacional)
- `POST /api/v1/incidents/{id}/review` com `{"decision": "CONFIRMED|DISMISSED|INSUFFICIENT_EVIDENCE", "note": "...", "reviewer": "..."}`. Justificativa e revisor obrigatórios (422 sem eles). A revisão **não** altera `OPEN/RESOLVED` nem a conformidade (decidida pelo Rules Engine). Cada parecer entra em `review_history` (trilha de auditoria, só cresce). Evento `INCIDENT_REVIEWED`.
- `INC_DB_PATH=/caminho/incidentes.db` liga a persistência em SQLite: incidentes, revisões e idempotência sobrevivem a reinício. Sem a variável, continua em memória (como antes). O arquivo `.db` não vai para o Git.
- O `reviewer` ainda é texto informado; vira usuário autenticado quando houver login.

## WebSocket de eventos
`ws://localhost:8004/api/v1/ws/incidents`: ao conectar envia `{"type":"SNAPSHOT","incidents":[...abertos]}`; depois cada evento (`INCIDENT_CREATED`, `INCIDENT_UPDATED`, `INCIDENT_RESOLVED`, `INCIDENT_REVIEWED`) como `{"type": "...", ...}`. Só difusão (não decide nada). Cliente lento perde os eventos mais antigos; mantenha uma consulta REST de reserva. Requer o pacote `websockets` (já em `pyproject.toml`).
