# EPI Vision — Módulo 3: Verificação de Uso Correto

Transforma **"EPI detectado"** em **"EPI corretamente utilizado"**. Recebe as
pessoas rastreadas e os EPIs associados (saída do Módulo 2) e decide, por EPI e
com confiança, se está `PROPER`, `IMPROPER`, `MISSING`, `NOT_VISIBLE` ou
`UNKNOWN` — usando visibilidade, posicionamento e **análise temporal**.

> Princípios: nunca afirmar ausência quando a região **não está visível**;
> nunca concluir além do que a câmera permite; nunca decidir por um único frame.

## Arquitetura (multimodal + temporal)

```
frame (pessoa rastreada + EPIs + contexto da câmera)
        │
        ▼
1. Pose / Regiões corporais  (app/pose.py, regions.py)
2. Visibilidade              (app/visibility.py)   ── decide o que dá para avaliar
        │
        ▼
3. Avaliadores por EPI       (app/evaluators.py)   ── PROPER / IMPROPER / MISSING / NOT_VISIBLE
        │
        ▼
4. Análise temporal          (app/temporal.py)     ── janela deslizante -> confiança
        │
        ▼
5. Motor de regras           (app/rules.py)        ── veredito geral
        │
        ├─► Evidência         (app/evidence.py)     ── registra não conformidade
        └─► Dashboard         (app/dashboard.py)    ── 🟢🔴⚪🟡 + ⚠️/✅
```

`PPEComplianceService` (app/compliance.py) orquestra tudo e é **stateful por
track** (mantém a janela temporal entre frames do mesmo `person_track_id`).

## Estados

Por EPI: `MISSING`, `PRESENT`, `PROPER`, `IMPROPER`, `NOT_VISIBLE`, `UNKNOWN`.
Geral: `COMPLIANT`, `PARTIAL_NON_COMPLIANCE`, `NON_COMPLIANT`, `UNDETERMINED`.

A distinção **`MISSING` × `NOT_VISIBLE`** é central: só afirmamos ausência quando
a região corporal está comprovadamente no campo de visão.

## Como rodar

```bash
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
# API:       http://localhost:8000/docs
# Dashboard: http://localhost:8000/api/v1/dashboard
```

Sem banco, sem autenticação, síncrono — igual ao Módulo 2.

### Exemplo (um frame)

`POST /api/v1/compliance/evaluate`:

```json
{
  "person_track_id": "TRACK-000123",
  "person_bbox": [300, 100, 500, 900],
  "frame_width": 1000, "frame_height": 1000,
  "employee_id": "FUNC-000002", "camera_id": "CAM-07",
  "ppe": [
    {"ppe_type": "helmet", "bbox": [360, 110, 440, 180], "confidence": 0.95},
    {"ppe_type": "vest",   "bbox": [325, 270, 475, 520], "confidence": 0.93},
    {"ppe_type": "gloves", "bbox": [310, 470, 360, 520], "confidence": 0.90},
    {"ppe_type": "boots",  "bbox": [340, 830, 460, 895], "confidence": 0.90}
  ]
}
```

> Um único frame costuma sair `UNKNOWN` (a análise temporal exige alguns frames
> consistentes). Use `POST /compliance/evaluate-batch` com vários frames, ou
> chame `evaluate` repetidamente para o mesmo track, para ver `PROPER`.

## API

```
GET  /api/v1/health
GET  /api/v1/config
POST /api/v1/compliance/evaluate         # 1 frame (stateful por track)
POST /api/v1/compliance/evaluate-batch   # sequência de frames (demonstra temporal)
GET  /api/v1/compliance/state            # último resultado por pessoa
GET  /api/v1/compliance/evidence         # evidências de não conformidade
GET  /api/v1/dashboard                   # dashboard HTML (🟢🔴⚪🟡)
```

## Análise temporal

Janela deslizante por `(person_track_id, EPI)`. O status final é o dominante,
ponderado por confiança; a confiança cresce com o acordo entre frames. Quando o
status é `PROPER` com alto acordo e janela cheia, marca
`HIGH_CONFIDENCE_PROPER_USE`. Isso reduz falsos positivos de um frame ruim.

## Visibilidade — nunca concluir além da câmera

`app/visibility.py` marca uma região como `NOT_VISIBLE` quando ela cai fora do
frame **ou** quando a pessoa está cortada por aquela borda (ex.: câmera de torso
→ `BOOTS = NOT_VISIBLE`, jamais `MISSING`). Veja `docs/camera_limitations.md`
para o impacto de cada tipo de câmera.

## Evidência (LGPD)

Em não conformidade, registra `event_id`, `camera_id`, `timestamp`,
`frame_reference`, `employee_id`, `ppe_type`, `status`, `confidence`. Por padrão
**não** guarda a imagem (só a referência); retenção configurável.

## Integração

- **Consome** o Módulo 2: `person_track_id`, `person_bbox` e a lista de EPIs
  com bounding boxes (o que o `process-frame` do Módulo 2 já retorna).
- **Consome** o Módulo 1: `employee_id` (identidade), usado no resultado, na
  evidência e no dashboard.

## Pose

`heuristic` (padrão, sem dependências) deriva as regiões da caixa da pessoa.
Para maior precisão (mãos/olhos), troque para `yolo` (`CMP_POSE_PROVIDER=yolo`,
requer `pip install -e ".[pose]"`) — a interface `PoseProvider` isola essa troca.

## Testes

```bash
pytest -q     # 24 testes
```

Cobrem: visibilidade (torso-only → botas não verificáveis), avaliadores
(capacete na cabeça=PROPER, na mão=IMPROPER, ausente=MISSING; luva esq. presente
/ dir. ausente), análise temporal (constrói confiança; baixa confiança→UNKNOWN;
NOT_VISIBLE nunca vira UNKNOWN), regras (o exemplo do spec →
PARTIAL_NON_COMPLIANCE), serviço completo, evidência e API.

## Limitações

- Precisão de mãos/olhos melhora bastante com pose real (YOLO-pose/MediaPipe).
- Sem oclusão 3D: cenas muito aglomeradas podem exigir múltiplas câmeras.
- O veredito é tão bom quanto a detecção que o alimenta (Módulo 2) e o
  enquadramento da câmera.
