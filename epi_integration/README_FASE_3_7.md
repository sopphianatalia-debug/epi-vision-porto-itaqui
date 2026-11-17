# Fase 3.7 — Real Camera End-to-End Pipeline

## Objetivo

Conectar a câmera/vídeo real do Módulo 2 (`epi_ppe`) ao pipeline já
construído nas Fases 3.5/3.6, provando que uma observação produzida pelo
YOLO (ou pelo provider mock, para testes) pode percorrer o sistema inteiro:

```
Câmera -> OpenCV -> YOLO -> Identity -> Fusion -> Rules -> Incident
```

## O que já existia e foi reaproveitado (não recriado)

O Módulo 2 já tinha praticamente toda a infraestrutura que esta fase
precisava:

- `app/camera/service.py` — `CameraService` abstrato com `TestCamera`
  (testes, sem hardware), `OpenCVCamera` (webcam/vídeo/RTSP real).
- `app/pipeline/pipeline.py` — `PPEPipeline` (detecção + tracking +
  associação pessoa↔EPI), já com `PersonTracker` (IoU) e
  `PersonPPEAssociator` (contenção + região corporal esperada).
- `app/detection/factory.py` — providers plugáveis (`mock`, `demo`,
  `yolo`), trocáveis por configuração (`PPE_DETECTOR_PROVIDER`).
- `app/viewer/renderer.py` + `scripts/live_view.py` — visualização com
  bounding boxes, FPS, track_id, já com suporte a modo headless e
  gravação em arquivo.
- `POST /pipeline/process-frame` — endpoint HTTP que já expõe o pipeline
  inteiro do Módulo 2.

Nada disso foi alterado nesta fase.

## O que foi construído (a camada de integração)

Tudo em `epi_integration/app/`:

| Arquivo | O que faz |
|---|---|
| `observation_builder.py` | Traduz a saída do Módulo 2 (`PersonResultOut`) para o `ppe` que o Fusion espera. Contém a Fricção 4 (ver `docs/contracts.md`, seção 10.2). |
| `identity_cache.py` | Cache TTL por `(camera_id, track_id)` — evita chamar `/recognition/match` em todo frame. |
| `camera_config.py` | Configurações centralizadas da camada de pipeline (`EPI_PIPELINE_*`). |
| `camera_pipeline.py` | `RealCameraPipeline` — o orquestrador: amostragem de frames, métricas, status por serviço, resiliência a erro por etapa, logs estruturados. |
| `bridge.py` (estendido) | Nova função `identify_ingest_and_evaluate`, composição das funções já existentes das Fases 3.5/3.6. |
| `clients.py` (estendido) | Novo `VisionClient` — o Módulo 2 tratado como 5º serviço HTTP. |
| `runner.py` (estendido) | Sobe também o `epi_ppe` (`Pipeline(include_vision=True)`). |

## Arquitetura de integração — por que HTTP, de novo

Igual às Fases 3.5/3.6: o Módulo 2 não é importado em processo (o pacote
`app` colidiria com o `app` do `epi_integration` e dos outros módulos — ver
o cabeçalho de `app/runner.py`). Ele é tratado como mais um serviço
`uvicorn` subido via subprocesso, falado por HTTP. Isso é, inclusive, o que
a própria Fase 3.7 pedia na seção 33: *"Se os módulos forem serviços
FastAPI independentes, não copiar o código de um módulo para outro."*

```
Observation (câmera real ou cena de teste)
    │
    ▼
POST /pipeline/process-frame  (epi_ppe — Módulo 2, HTTP)
    │  PersonResultOut: track_id, person_bbox, detections[]
    ▼
observation_builder.build_fusion_ppe()   <- Fricção 4 aplicada aqui
    │  ppe: {helmet: {status, confidence}, ...}
    ▼
IdentityCache.get(camera_id, track_id) — hit? usa; miss? chama Identity
    │
    ▼
POST /recognition/match  (epi_identity)
    │  identity_result_to_fusion_identity()  <- Fricção 3 (Fase 3.6)
    ▼
POST /fusion/observations  (epi_fusion)
    │
    ▼
GET /fusion/employees/{id}  (só se MATCHED)
    │  build_rules_evaluate_payload() + enrich_violations_with_cameras()
    ▼
POST /rules/evaluate  (epi_rules)
    │
    ▼
POST /incidents/evaluations  (epi_incident)
```

Cada seta é uma chamada HTTP real, cada uma no seu próprio `try/except` —
ver `docs/contracts.md`, seção 10.6, para o porquê de não usar a função
"tudo-ou-nada" `identify_ingest_and_evaluate` aqui.

## Como rodar os testes (sem hardware, sem YOLO)

```bash
# a partir da raiz do projeto
pip install -e epi_fusion -e epi_rules -e epi_incident -e epi_identity -e epi_ppe
pip install -e "epi_integration[dev]"
pip install greenlet aiosqlite pytest-asyncio

# testes unitários de cada módulo (nenhum foi alterado, devem continuar passando)
pytest epi_fusion/tests epi_rules/tests epi_incident/tests epi_identity/tests epi_ppe/tests

# testes de integração — Fases 3.5 + 3.6 + 3.7
pytest epi_integration/tests/integration -v
```

Os testes da Fase 3.7 sobem `epi_ppe` com `PPE_DETECTOR_PROVIDER=mock` —
nenhum peso de YOLO é baixado, nenhuma câmera é aberta. As "cenas" são
dicts Python determinísticos (ver `tests/integration/test_camera_pipeline.py`,
`make_scene()`), no mesmo formato que o provider mock do Módulo 2 já
documentava desde antes desta fase.

## Cenários cobertos

| # | Cenário | Teste |
|---|---|---|
| A | Conformidade total via câmera | `test_scenario_a_full_compliance_no_incident` |
| B | EPI ausente detectado pela câmera -> incidente | `test_scenario_b_missing_helmet_creates_incident` |
| C | Pessoa não identificada -> nenhum incidente individual | `test_scenario_c_unmatched_identity_no_individual_incident` |
| D | Câmera não enxerga os pés -> NOT_VISIBLE, sem incidente | `test_scenario_d_camera_cannot_see_feet_is_not_visible` |
| — | LOW_CONFIDENCE nunca aparece como identidade confirmada | `test_low_confidence_identity_never_shown_as_confirmed` |
| — | Amostragem (`process_every_n_frames`) | `test_process_every_n_frames_skips_frames` |
| — | Cache de identidade evita chamadas repetidas | `test_identity_cache_avoids_repeated_match_calls` |
| — | Frames repetidos não duplicam incidente | `test_repeated_frames_do_not_duplicate_incident` |
| — | Múltiplas pessoas no mesmo frame, tratadas à parte | `test_multiple_people_same_frame_independent` |
| — | Fusion indisponível não derruba o pipeline | `test_fusion_unavailable_does_not_crash_pipeline` |
| — | Métricas da camada de pipeline | `test_pipeline_metrics_snapshot_fields` |
| — | `track_id` e `employee_id` continuam distintos | `test_track_id_and_employee_id_stay_distinct` |
| — | Observation Builder (8 testes unitários, sem servidor) | `test_observation_builder.py` |

`test_observation_builder.py` foi validado manualmente durante o
desenvolvimento (rodado com um script Python direto, sem pytest, já que
este ambiente de geração de código não tem acesso à internet para instalar
dependências) — os 5 casos centrais passaram. Os testes de integração
completos (que sobem os 5 serviços) **precisam ser rodados na sua máquina**,
como em todas as fases anteriores.

## Status de execução

Este ambiente de geração de código não tem acesso à internet nem a
hardware de câmera — não foi possível instalar as dependências completas
nem rodar a suíte de integração de ponta a ponta aqui. O que FOI validado
nesta máquina:

- Sintaxe de todos os arquivos novos/alterados (`py_compile`, sem erros).
- A lógica do `observation_builder.py`, rodada diretamente (sem pytest) —
  os 5 casos centrais da Fricção 4 confirmados.
- A geometria dos cenários de teste (associação pessoa↔EPI e continuidade
  do tracker), validada chamando o código real do Módulo 2
  (`PersonPPEAssociator`, `PersonTracker`) diretamente.

O que precisa da sua máquina: a suíte completa de integração (`pytest
epi_integration/tests/integration -v`), que sobe os 5 serviços de verdade.

## Modo demonstração (webcam real) — implementado nesta rodada

`scripts/run_camera_demo.py` liga a câmera real ao pipeline de negócio
completo. Diferente da versão anterior desta fase (que só tinha a peça de
orquestração pronta, sem o loop de captura), agora existe:

1. **Suporte a imagem real no `epi_ppe`** — `POST /pipeline/process-frame`
   passou a aceitar `frame_b64` (imagem JPEG/PNG em base64), além do `frame`
   (dict, mock/demo) que já existia. Só um script novo, `_decode_frame`,
   decide qual dos dois usar — nada no resto do módulo mudou.
2. **Mapa de classes configurável** — `PPE_DETECTOR_NAME_MAP_JSON` permite
   usar um modelo YOLO de EPI pré-treinado por terceiros sem editar código,
   mesmo que os nomes de classe não batam com o vocabulário do projeto
   (ex.: `"hard-hat"` do modelo -> `"HELMET"` do sistema).
3. **`RealCameraPipeline` aceita imagem real** — novo parâmetro
   `use_real_images=True` (e o `VisionClient.process_frame_image`
   correspondente) fazem o roteamento; o comportamento com cena mock (usado
   em todos os 58 testes anteriores) continua idêntico por padrão.
4. **`DEMO_SCENARIO`** — força um EPI ausente de forma controlada e
   claramente identificada como demonstração, sem tocar no Rules Engine
   nem inventar isso dentro do YOLO (aplicado depois da detecção real,
   nunca no lugar dela).
5. **`scripts/run_camera_demo.py`** — o loop de captura em si (webcam,
   arquivo de vídeo ou RTSP), com overlay mostrando track_id, identidade
   (rotulada como `DEMO IDENTITY` quando aplicável — nunca apresentada como
   reconhecimento facial real), EPIs, conformidade e incidentes.

### Por que a câmera é capturada com `cv2.VideoCapture` direto, não com o `CameraService` do epi_ppe

O script já importa `app.camera_pipeline` (`epi_integration`) — importar
também `app.camera.service` (`epi_ppe`) no mesmo processo colidiria os dois
pacotes `app`, o mesmo problema resolvido desde a Fase 3.5 subindo os
módulos como processos separados. A captura de frame em si (abrir fonte,
ler, tratar falha) é simples o bastante para não precisar da abstração
completa do Módulo 2 aqui — e a separação que a seção 4 do pedido exige
("o loop da câmera deve permanecer separado da lógica de negócio") continua
verdadeira: este script só captura e desenha; toda decisão continua em
`app/camera_pipeline.py`, falado por HTTP com os outros 4 serviços.

### Como rodar a demonstração completa

```bash
# 1) Suba os 4 serviços de sempre (cada um em um terminal, ou em background)
cd epi_identity && EPI_ENVIRONMENT=production EPI_DATABASE_URL=... EPI_JWT_SECRET=... \
  python3 -m uvicorn app.main:app --port 8001
cd epi_fusion   && python3 -m uvicorn app.main:app --port 8002
cd epi_rules    && python3 -m uvicorn app.main:app --port 8003
cd epi_incident && python3 -m uvicorn app.main:app --port 8004

# 2) Suba o epi_ppe com um modelo de EPI real (baixe um modelo pré-treinado
#    de EPI publicado por terceiros — ex. Roboflow Universe/Kaggle — ou use
#    PPE_DETECTOR_PROVIDER=mock para testar sem detecção real)
cd epi_ppe
pip install ultralytics opencv-python-headless
PPE_DETECTOR_PROVIDER=yolo \
PPE_DETECTOR_MODEL_PATH=/caminho/para/seu/modelo_epi.pt \
PPE_DETECTOR_NAME_MAP_JSON='{"hard-hat": "HELMET", "safety-vest": "SAFETY_VEST"}' \
  python3 -m uvicorn app.main:app --port 8000

# 3) Cadastre um "funcionário de demonstração" no epi_identity (mesmo
#    processo das Fases 3.6/3.7 — ver test_identity_scenarios.py,
#    enroll_employee) e anote o employee_code gerado, ex. FUNC-000001

# 4) Rode a demonstração
cd epi_integration
pip install opencv-python-headless numpy
EPI_PIPELINE_DEMO_EMPLOYEE_SEED=FUNC-000001 \
  python3 scripts/run_camera_demo.py --source 0 --camera-id CAM-01
```

Pra demonstrar `NON_COMPLIANT` sem precisar tirar o capacete de verdade:

```bash
EPI_PIPELINE_DEMO_EMPLOYEE_SEED=FUNC-000001 \
EPI_PIPELINE_DEMO_SCENARIO=missing_helmet \
  python3 scripts/run_camera_demo.py --source 0
```

### O que ainda não pôde ser testado remotamente

Este ambiente de geração de código não tem webcam, display, nem acesso à
internet para baixar um modelo YOLO de EPI real ou o `ultralytics`. O que
FOI validado aqui, com o código real (não simulado):

- A decodificação base64 -> imagem (`_decode_frame`), incluindo uma
  imagem sintética codificada em JPEG de verdade e decodificada de volta.
- O merge do mapa de classes configurável (`PPE_DETECTOR_NAME_MAP_JSON`),
  com o `DEFAULT_NAME_MAP` real do projeto.
- O roteamento `use_real_images` (`process_frame` vs `process_frame_image`)
  dentro do `RealCameraPipeline`.
- O `demo_ppe_override` sobrescrevendo corretamente uma detecção real.

O que precisa da sua máquina (com webcam, internet para baixar um modelo, e
`pip install ultralytics opencv-python-headless`): a demonstração ao vivo em
si, ponta a ponta.

## Limitações

Ver `docs/contracts.md`, seção 10.7 — resumo:

- Identificação continua no provider mock (nenhum reconhecimento facial
  real, banco biométrico ou embeddings).
- Demonstração ao vivo com `MATCHED` real exige funcionário pré-cadastrado
  com seed fixa — o mock não reconhece rostos de verdade.
- Sem Re-ID nem calibração espacial entre câmeras.
- Loop de captura ao vivo com webcam real não pôde ser testado neste
  ambiente.

## Próximos passos

1. Validar a demonstração ao vivo na sua máquina (webcam real + modelo de
   EPI real) — o `scripts/run_camera_demo.py` está pronto, mas não pôde ser
   testado remotamente (sem webcam/display/internet neste ambiente).
2. Se a qualidade do modelo pré-treinado de terceiros não for suficiente,
   avaliar treinar um modelo próprio (já documentado em `epi_ppe/docs/dataset.md`).
3. Alertas/Notificações.
4. Dashboard Operacional.
