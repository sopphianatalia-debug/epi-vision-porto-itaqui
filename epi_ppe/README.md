# EPI Vision — Módulo 2: Detecção de Pessoas e EPIs

Detecção de **pessoas** e **EPIs** (capacete, colete, luvas, botas, óculos,
protetor auricular) em vídeos de câmeras de segurança, com tracking, associação
pessoa↔EPI e avaliação do modelo. Prepara os dados para o **Módulo 3** (uso
correto), que **não** está implementado aqui.

> Este módulo detecta e associa. Ele **não decide** se o EPI está sendo usado
> corretamente — essa decisão pertence ao Módulo 3.

## Arquitetura

Pipeline síncrono, sem banco de dados, com modelo de detecção **plugável**:

```
app/
├── config.py            # Settings: thresholds por classe, modelo, tracking (via env)
├── enums.py             # DetectionClass (configurável) + PPE_CLASSES derivado
├── types.py             # BoundingBox, Detection, PersonResult
├── geometry.py          # IoU, contenção
├── detection/
│   ├── base.py          # ObjectDetectionProvider (ABC): load_model / detect
│   ├── service.py       # ObjectDetectionService (thresholds+NMS), Person/PPE services
│   ├── factory.py
│   └── providers/       # mock (dev/testes) | yolo (produção, import protegido)
├── association/
│   └── associator.py    # pessoa↔EPI: contenção + região corporal + score
├── tracking/
│   └── tracker.py       # PersonTracker → person_track_id (TRACK-000123)
├── camera/
│   └── service.py       # CameraService: RTSP/arquivo/webcam/teste + resiliência
├── pipeline/
│   └── pipeline.py      # PPEPipeline (orquestra tudo) + DetectionEventService
├── evaluation/
│   └── metrics.py       # Precision/Recall/F1/AP por classe + mAP
├── observability/
│   └── metrics.py       # FPS, latência, tempo de inferência
└── api/                 # rotas REST síncronas
```

Fluxo: `frame → detecção → separa pessoas/EPIs → tracking → associação → resultado`.

## Como rodar

```bash
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
# Docs: http://localhost:8000/docs
```

Sem autenticação e sem banco — mais simples de testar que o Módulo 1. O provider
padrão é o `mock`, que aceita cenas descritas em JSON (ótimo para testar toda a
lógica sem GPU nem vídeo real).

### Exemplo (processar um frame)

`POST /api/v1/pipeline/process-frame`:

```json
{
  "camera_id": "CAM-07",
  "frame": {"detections": [
    {"cls": "PERSON",      "confidence": 0.95, "bbox": [100, 100, 300, 500]},
    {"cls": "HELMET",      "confidence": 0.96, "bbox": [150, 110, 230, 160]},
    {"cls": "SAFETY_VEST", "confidence": 0.94, "bbox": [130, 230, 270, 380]}
  ]}
}
```

Resposta: uma pessoa `TRACK-000001` com capacete e colete associados.

## API

```
GET  /api/v1/health
GET  /api/v1/classes                 # classes + thresholds ativos
POST /api/v1/detect                  # detecções cruas (pessoa + EPIs)
POST /api/v1/pipeline/process-frame  # pipeline completo (tracking + associação)
GET  /api/v1/events                  # eventos recentes (para Módulo 3 / interface)
GET  /api/v1/metrics                 # FPS, latência, tempo de inferência
POST /api/v1/evaluate                # Precision/Recall/F1/AP por classe + mAP
```

## Estratégia de modelo

Detecção de objetos em tempo real via **YOLO (Ultralytics)** como referência de
produção — rápido, maduro, treinável no dataset próprio. A abstração
`ObjectDetectionProvider` permite trocar por RT-DETR ou outro sem tocar no
pipeline. Para dev/testes há o `MockDetector`, determinístico e sem dependências
de CV. Selecione via `PPE_DETECTOR_PROVIDER`.

```bash
pip install -e ".[detection]"     # ultralytics + opencv
export PPE_DETECTOR_PROVIDER=yolo
export PPE_DETECTOR_MODEL_PATH=/caminho/seu_modelo.pt
```

## Associação pessoa↔EPI

Para cada EPI, calcula-se a **fração contida** na caixa da pessoa e o
**encaixe na região corporal esperada** (capacete no topo, botas embaixo, colete
no torso). O EPI é atribuído à pessoa de maior score acima do limiar — assim um
capacete distante não é associado a quem está do outro lado da cena. Tudo
configurável (`PPE_ASSOCIATION_*`). Ver `docs/classes.md`.

## Tracking

`PersonTracker` por IoU gera `person_track_id` (`TRACK-000123`) e mantém a mesma
identidade da pessoa entre frames, reduzindo duplicações. Trocável por
ByteTrack/DeepSORT mantendo a interface.

## Câmeras e resiliência

`CameraService` abstrai **RTSP, arquivo de vídeo, webcam e stream de teste**.
O gerador `frames()` tolera frames inválidos (pula), quedas de conexão e fim de
stream sem derrubar o pipeline. Backends reais (OpenCV) têm import protegido.

## Avaliação

`POST /evaluate` (ou `app/evaluation`) recebe predições e ground-truth e devolve
**Precision, Recall, F1 e AP por classe** e o **mAP**, casando caixas por IoU.
Base para medir o modelo no conjunto de teste do dataset (ver `docs/dataset.md`).

## Integração

- **Consome** o Módulo 1: o `person_track_id` pode ser enriquecido com
  `employee_id` (campo já presente em `PersonResult`).
- **Alimenta** o Módulo 3: `PersonResult.to_module3_contract()` reporta
  presença/ausência de cada EPI, sem julgar uso correto.

## Visualizador ao vivo (OpenCV)

Interface de teste visual (seção 15): abre webcam / vídeo / RTSP, desenha as
caixas com classe, confiança, `track_id` e FPS.

```bash
# 1) Ver funcionando já, sem YOLO nem câmera (cena sintética em movimento):
pip install -e ".[viewer]"
python scripts/live_view.py --source demo --provider demo

# 2) Webcam com modelo YOLO treinado:
pip install -e ".[detection,viewer]"
python scripts/live_view.py --source 0 --provider yolo --model seu_modelo.pt

# 3) Arquivo de vídeo:
python scripts/live_view.py --source /caminho/video.mp4 --provider yolo --model seu_modelo.pt

# 4) RTSP:
python scripts/live_view.py --source "rtsp://user:pass@ip:554/stream" --provider yolo --model seu_modelo.pt

# 5) Servidor sem tela: grava um vídeo anotado
python scripts/live_view.py --source video.mp4 --provider yolo --model m.pt --headless --save saida.mp4
```

Na janela: `q` ou `ESC` para sair. Cores por classe e "Pessoa #N" com o track ID.

> Use `opencv-python` (extra `viewer`) para abrir janela; `opencv-python-headless`
> (extra `detection`/`dev`) é para servidor/CI, sem GUI.

## Testes

```bash
pytest -q     # 32 testes
```

Cobrem: thresholds e NMS, associação (incluindo o exemplo do spec e o caso
"capacete distante não associa"), tracking (ID estável, expiração), avaliação
(precision/recall/F1/AP/mAP), pipeline completo, câmera de teste com frames
inválidos, e todos os endpoints da API.

## Limitações

- Um `PersonTracker` por instância de pipeline: para várias câmeras simultâneas,
  instancie um pipeline por câmera (o estado de tracking não deve se misturar).
- A associação é geométrica (2D); cenas muito aglomeradas podem exigir sinais
  adicionais (pose, profundidade).
- O `MockDetector` é para desenvolvimento; a acurácia real depende do modelo
  YOLO treinado no dataset do porto.
