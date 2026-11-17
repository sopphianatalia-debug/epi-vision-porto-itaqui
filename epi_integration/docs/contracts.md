# Contratos entre módulos — Fase 3.5

Este documento descreve, campo a campo, o que cada serviço **realmente**
recebe e entrega (verificado no código-fonte de cada módulo, não inferido),
e onde a camada de integração (`app/bridge.py`) precisou preencher lacunas.

## 1. Câmera/Detecção -> Fusion (`POST /fusion/observations`)

Entrada (`ObservationIn`):

| campo | tipo | obrigatório | observação |
|---|---|---|---|
| `camera_id` | string | sim | |
| `person_track_id` | string | sim | id de tracking POR câmera — nunca confundir com `employee_id` |
| `employee_id` | string ou null | não | ausente/null => observação **anônima** (nunca é atribuída por proximidade) |
| `identity_status` | enum (`MATCHED`, `LOW_CONFIDENCE`, `AMBIGUOUS`, `NOT_IDENTIFIED`, `UNKNOWN`) | não (default `MATCHED`) | só `MATCHED` é usado como chave de junção |
| `ppe` | dict[ppe_type -> {status, confidence}] | não | chaves ausentes = silêncio da câmera sobre aquele EPI |
| `timestamp`, `observation_id` | opcionais | não | gerados automaticamente se ausentes |

Saída (`IngestOut`): `{employee_id, identity_status, kind: "employee_state"|"anonymous", reason}`.

## 2. Fusion -> Rules Engine (`POST /rules/evaluate`)

O Fusion **não empurra** para o Rules Engine — expõe `GET
/fusion/employees/{employee_id}` e quem consulta (a camada de integração)
decide quando avaliar.

`EmployeeSafetyState.to_dict()` relevante:

```json
{
  "employee_id": "FUNC-000234",
  "identity_status": "MATCHED",
  "ppe": {
    "helmet": {"status": "MISSING", "confidence": 0.94, "cameras": ["CAM-01"], "conflict": false}
  },
  "overall_status": "PARTIAL"
}
```

O Rules Engine espera (`EvaluateRequest`): `employee_id`, `area`,
`operation`, `role`, `identity_status`, `evaluation_id`, `ppe: dict[ppe_type
-> {status, confidence}]`.

**Ponto de fricção 1 — CONFLICTING:** o `PPEStatus` do Fusion não tem um
valor `CONFLICTING`; um conflito não resolvido vira `status: "UNKNOWN"` +
`conflict: true`. O `ObservedStatus` do Rules Engine, por outro lado, tem
`CONFLICTING` com política própria (`conflicting_policy`). A ponte
(`bridge.fusion_ppe_to_rules_ppe`) traduz `UNKNOWN + conflict=true` para
`"CONFLICTING"` antes de enviar. Sem essa tradução, todo conflito de câmeras
cairia na política de `UNKNOWN` em vez da política de `CONFLICTING`
configurada na regra.

`area`/`operation`/`role` **não existem no Fusion** (ele não sabe onde o
funcionário está trabalhando) — são metadados de contexto que, num sistema
real, viriam de escala/turno ou de outro serviço. Nesta fase eles são
parâmetros explícitos do chamador (default: pátio de carga / movimentação de
carga / operador, que casam com a regra seed `RULE-PATIO-CARGA-001`).

## 3. Rules Engine -> Incident Service (`POST /incidents/evaluations`)

`ComplianceEvaluation.to_dict()` relevante:

```json
{
  "evaluation_id": "EVAL-...",
  "employee_id": "FUNC-000234",
  "effective_rule_id": "RULE-PATIO-CARGA-001",
  "overall_status": "NON_COMPLIANT",
  "violations": [
    {
      "violation_id": "VIOL-...",
      "rule_id": "RULE-PATIO-CARGA-001",
      "rule_version": 1,
      "employee_id": "FUNC-000234",
      "ppe_type": "helmet",
      "observed_status": "MISSING",
      "severity": "CRITICAL",
      "confidence": 0.94,
      "reason": "helmet obrigatório e ausente (MISSING)"
    }
  ]
}
```

**Ponto de fricção 2 — source_cameras e reason_code:**

- `Violation.to_dict()` **não tem** `source_cameras` (o Rules Engine nunca
  viu câmeras, só o estado já consolidado). O `IncidentService` guarda
  `source_cameras` por incidente e o exige para a fusão de multi-câmera
  (seção 9 do pedido). A ponte (`bridge.enrich_violations_with_cameras`)
  busca, para cada `ppe_type` em violação, as câmeras contribuintes no
  `EmployeeSafetyState` do Fusion (`ppe[ppe_type]["cameras"]`) e as anexa
  antes de enviar ao Incident Service.
- `Violation.to_dict()` **não tem** `reason_code` (só `reason`, texto livre).
  Isso já era esperado pelo próprio `epi_incident`:
  `ViolationInput.from_rules_violation` deriva `reason_code` a partir de
  `observed_status` (`MISSING` -> `PPE_MISSING`, `IMPROPER` ->
  `PPE_IMPROPER`, senão `PPE_VIOLATION`). A camada de integração não precisou
  mexer nisso — já é tratado dentro do próprio Incident Service.

**Único endpoint novo desta fase:** `POST /incidents/evaluations`. Antes da
Fase 3.5 o Incident Service só expunha `POST /incidents` (abre/deduplica
UMA violação) e `POST /incidents/{id}/resolve` (resolve por id). Nenhum dos
dois cobre o fluxo agregado "abrir o que está em violação e resolver o que
deixou de estar" — isso já existia como método Python
(`IncidentService.process_evaluation`, usado e testado desde a Fase 3.4), só
não estava acessível via HTTP. O novo endpoint é um *pass-through* de uma
linha para esse método; nenhuma regra de negócio foi criada ou alterada
(ver `epi_incident/app/api/routes.py` e `epi_incident/app/api/schemas.py`).

Saída: lista de `{action: "CREATED"|"UPDATED"|"NOOP"|"RESOLVED", incident:
{...}}`.

## 4. Campos obrigatórios vs. opcionais (resumo)

| Contrato | Obrigatórios | Podem ser nulos |
|---|---|---|
| Observation -> Fusion | `camera_id`, `person_track_id` | `employee_id`, `ppe` (vazio = silêncio total) |
| Fusion -> Rules | `ppe` (pode ser `{}`) | `employee_id` (funcionário não identificado) |
| Rules -> Incident | `overall_status`; por violação: `rule_id`, `ppe_type`, `severity` | `employee_id` (bloqueia abertura — ver `InvalidViolation`), `source_cameras` (default `[]`) |

## 5. Timestamps

Cada serviço tem seu próprio `Clock` injetável (`Clock`/`FakeClock`).
`timestamp` é opcional em todos os contratos de entrada; quando omitido, cada
serviço usa seu próprio relógio no momento do processamento — **não há
propagação obrigatória de um único timestamp através do pipeline** nesta
fase. Isso é aceitável porque o pipeline é síncrono e a janela entre
serviços é da ordem de milissegundos; passou a ser uma limitação conhecida
(ver `README_FASE_3_5.md`, seção Limitações) caso no futuro seja necessário
timestamp de captura da câmera propagado ponta a ponta.

## 6. evaluation_id

Gerado pelo Rules Engine se o chamador não fornecer (`EVAL-{uuid12}`).
Propagado para o Incident Service dentro de cada violação
(`ViolationInput.evaluation_id`) e usado por ele para idempotência
(`Incident._processed_eval_ids`). A camada de integração sempre fornece um
`evaluation_id` explícito ao Rules Engine nos testes para poder reenviar a
mesma avaliação de propósito (cenário de idempotência).

## 7. Tratamento de erros entre módulos

Cada serviço valida sua própria entrada de forma independente (Pydantic +
exceções de domínio convertidas em HTTP 4xx pela própria API) — a falha de
um módulo não corrompe o estado dos outros porque não há transação
distribuída nem estado compartilhado: cada serviço só é afetado por chamadas
dirigidas a ele. Ver `tests/integration/test_events_and_errors.py`.

## 9. Fase 3.6 — Identity-to-Fusion Integration

A Fase 3.5 assumia `employee_id` artificial já resolvido na Observation. A
Fase 3.6 substitui isso por uma chamada real a `POST /recognition/match` do
`epi_identity` (provider mock, sem biometria real).

### 9.1 Contrato real do epi_identity (verificado no código, não no pedido)

`epi_identity` já tinha um enum `RecognitionStatus` praticamente idêntico ao
pedido pela Fase 3.6 — não foi criado nada nesse módulo:

```
UNKNOWN | LOW_CONFIDENCE | MATCHED | AMBIGUOUS | UNAVAILABLE
```

(`UNKNOWN` é o "UNMATCHED" do pedido; `UNAVAILABLE` é um quinto estado que o
pedido não previu — ver 9.2.)

`POST /recognition/match` (autenticado, `RECOGNITION_RUN`):

```json
// entrada
{"camera_id": "CAM-01", "person_track_id": "TRACK-01", "frame": {"faces": [...]}}
// saída
{"event_id": "...", "employee_id": "FUNC-000234", "status": "MATCHED",
 "confidence": 0.97, "similarity_score": 0.99, "requires_review": false, ...}
```

### 9.2 Ponto de fricção 3 — RecognitionStatus (Identity) x IdentityStatus (Fusion)

| Identity (`RecognitionStatus`) | Fusion (`IdentityStatus`) | Motivo |
|---|---|---|
| `MATCHED` | `MATCHED` | direto |
| `LOW_CONFIDENCE` | `LOW_CONFIDENCE` | direto |
| `AMBIGUOUS` | `AMBIGUOUS` | direto |
| `UNKNOWN` | `UNKNOWN` | direto |
| `UNAVAILABLE` | `NOT_IDENTIFIED` | **sem correspondência direta** — traduzido pela ponte |

`UNAVAILABLE` (rosto não detectado ou qualidade insuficiente) não existe no
vocabulário do Fusion — para ele, simplesmente não houve tentativa de
identificação, que é exatamente o que `NOT_IDENTIFIED` significa no
contrato dele. Implementado em
`app/bridge.py::identity_result_to_fusion_identity`. Em qualquer status que
não seja `MATCHED`, o Fusion já trata a observação como anônima por conta
própria (`JOINABLE_IDENTITY = {MATCHED}`) — a tradução só evita mandar um
valor de enum que o Fusion não reconheceria.

### 9.3 Como os estados LOW_CONFIDENCE/AMBIGUOUS são reproduzidos nos testes

O provider mock gera embeddings **determinísticos por seed de texto**: a
mesma seed sempre produz o mesmo vetor; seeds diferentes produzem vetores
praticamente ortogonais entre si (~0 de similaridade). Isso dá controle
direto sobre dois casos (`MATCHED` com a mesma seed do cadastro; `UNKNOWN`
com uma seed nunca cadastrada), mas **não** dá controle direto sobre uma
similaridade intermediária — não existe como pedir ao provider mock "gere um
rosto 70% parecido".

- **AMBIGUOUS**: contornado cadastrando **dois funcionários com a mesma
  seed** (colisão determinística) — 1º e 2º colocados ficam empatados em
  similaridade, o que é justamente a definição de ambiguidade no
  `MatchingEngine`. Funciona com os thresholds padrão, nenhuma configuração
  especial.
- **LOW_CONFIDENCE**: contornado com uma **segunda instância** do
  `epi_identity` (`identity_permissive`, fixture em `conftest.py`) subida
  com `EPI_SIMILARITY_THRESHOLD=-1.0`. Isso não quebra o `MATCHED` (que
  continua funcionando normalmente, autossimilaridade = 1.0 sempre vence),
  mas faz qualquer candidato "fracamente parecido" (~0 de similaridade)
  ainda ser considerado um candidato válido — só que com confiança baixa
  (fórmula de `_confidence` em `matching.py`), o que produz `LOW_CONFIDENCE`
  de forma determinística em vez de cair em `UNKNOWN`.

Essa é uma decisão da camada de **teste**, não do sistema: em produção, com
um provider real (InsightFace), rostos parcialmente parecidos produzem
similaridades intermediárias naturalmente — o truque das duas instâncias só
existe porque o provider mock não tem "meio-termo" configurável via seed.

### 9.4 Autenticação na integração

`epi_identity` é o único dos quatro serviços que exige JWT + RBAC. O
`runner.py` sobe cada instância de identity com um `EPI_JWT_SECRET` fixo e
conhecido (só para os testes); `app/identity_client.py::mint_token` gera um
token compatível com esse mesmo segredo, com papel `SECURITY_MANAGER`
(mesmo padrão que os testes originais do `epi_identity` já usavam —
`tests/conftest.py::auth_header`). Nenhuma credencial real, nenhuma alteração
no mecanismo de auth existente.

### 9.5 Segurança arquitetural (seção 27 do pedido)

O Identity Service, nesta integração, só é chamado para produzir um
`IdentityResult` — nunca decide conformidade, nunca cria incidente, nunca
altera `EmployeeSafetyState`. Isso é garantido pela própria separação de
processos (cada serviço só expõe os endpoints que sempre teve); não foi
necessário nenhum controle adicional na camada de integração.

## 10. Fase 3.7 — Real Camera End-to-End Pipeline

Conecta o Módulo 2 (`epi_ppe` — detecção/tracking/associação, YOLO ou mock)
na frente do pipeline: `Observation (câmera) -> epi_ppe -> Identity -> Fusion
-> Rules -> Incident`. Assim como nas fases anteriores, nada foi
reimplementado — o Módulo 2 já tinha praticamente tudo que a fase pedia
(`CameraService`/`TestCamera`/`OpenCVCamera`, `PPEPipeline`,
`scripts/live_view.py` com overlay via OpenCV). O trabalho desta fase foi a
ponte entre ele e o restante do sistema.

### 10.1 epi_ppe também é um serviço HTTP na integração

Diferente do que se poderia imaginar (importar `PPEPipeline` em processo),
o Módulo 2 já expõe `POST /pipeline/process-frame` — então a integração o
trata como um **quinto serviço**, no mesmo padrão dos outros quatro
(subprocesso `uvicorn`, HTTP, nunca importado em processo). Isso evita de
novo o problema de colisão do pacote `app` (seção "Por que subprocessos"
no topo de `app/runner.py`) e mantém a integração honesta: ela testa
exatamente o contrato REST que qualquer outro consumidor real usaria.

`app/clients.py::VisionClient` chama esse endpoint; a resposta
(`ProcessFrameResponse`) já vem com os EPIs associados a cada pessoa
rastreada (schema `PersonResultOut`: `person_track_id`, `employee_id`
sempre `None` neste ponto, `person_confidence`, `person_bbox`,
`detections: [{type, confidence, bbox}]`).

### 10.2 Ponto de fricção 4 — silêncio do detector não é silêncio de câmera

Este é o ponto mais sutil desta fase, documentado em detalhe no docstring
de `app/observation_builder.py` (vale a leitura completa lá). Resumo:

O Fusion, desde a Fase 3.1, já tinha uma regra para quando uma câmera
"fica em silêncio" sobre um EPI: se o perfil de visibilidade diz que ela
não enxerga aquela região, o silêncio vira `NOT_VISIBLE`; se a câmera
enxerga e ainda assim fica em silêncio, vira `NOT_OBSERVED` — e os dois
casos são tratados como `INDETERMINATE` pelo Rules Engine (nunca abrem
incidente).

Isso fazia sentido quando "silêncio" só podia significar "essa câmera
nunca me disse nada sobre esse funcionário". Mas o Módulo 2 roda a
detecção em TODO frame — se ele não encontrou um capacete numa pessoa que
está enquadrada, isso é uma ausência real e observada, não silêncio. Se o
`observation_builder` simplesmente omitisse a chave `helmet` nesse caso, o
sistema cairia sempre em `NOT_OBSERVED`/`INDETERMINATE` e **nunca abriria
um incidente por EPI ausente** — o que anularia a funcionalidade inteira
do pipeline de câmera.

A regra implementada em `build_fusion_ppe`:

| Situação | O que o builder envia |
|---|---|
| Módulo 2 detectou o EPI | `{"status": "DETECTED", "confidence": <real>}` |
| Módulo 2 rodou a detecção e não achou, câmera enxerga a região | `{"status": "MISSING", ...}` (ausência real e observada) |
| Câmera não enxerga a região (perfil de visibilidade) | chave omitida — Fusion decide `NOT_VISIBLE` sozinho, como sempre fez |

O perfil de visibilidade (`POST /fusion/cameras/{id}/visibility`, já
existente desde a Fase 3.1) continua sendo a única fonte de verdade sobre
"o que a câmera consegue fisicamente enxergar" — este ponto de fricção só
decide, a cada frame, se o que FOI enxergado tinha o EPI ou não.

### 10.3 Tradução de nomes de classe

O Módulo 2 usa nomes de `DetectionClass` (`HELMET`, `SAFETY_VEST`,
`GLOVES`, `SAFETY_BOOTS`, `SAFETY_GLASSES`, `EAR_PROTECTION`); o Fusion usa
slugs curtos (`helmet`, `vest`, `gloves`, `boots`, `glasses`,
`ear_protection`). Não é um `.lower()` — `SAFETY_VEST` não vira
`safety_vest`. `DETECTION_CLASS_TO_PPE_TYPE` em `observation_builder.py`
faz essa tradução explicitamente, célula por célula.

### 10.4 Cache de identidade — por que TTL, não por employee_id

`IdentityCache` é indexado por `(camera_id, person_track_id)`, nunca por
`employee_id` — porque antes da identificação responder não sabemos quem é
a pessoa. O TTL padrão é curto (2s) porque uma pessoa pode sair do
enquadramento e outra ocupar o mesmo track_id depois que o track anterior
expira no tracker do Módulo 2; um cache de identidade "eterno" arriscaria
atribuir a identidade errada a uma pessoa diferente que reaproveitasse
por coincidência um track_id antigo.

### 10.5 Amostragem cobre a cadeia inteira, não só o negócio

Como o Módulo 2 passou a ser um serviço remoto nesta fase (10.1), a
amostragem por `process_every_n_frames` acontece **antes** de qualquer
chamada de rede — inclusive a de detecção — e não só antes de
Identity/Fusion/Rules/Incident como se poderia supor. Rodar detecção a 30
FPS via HTTP para todo frame seria uma carga desnecessária mesmo que as
etapas seguintes fossem puladas; a seção 37 do pedido já era explícita
sobre isso ("vídeo a 30 FPS, análise a 2-10/s").

### 10.6 Resiliência a erro é por etapa, não tudo-ou-nada

`bridge.py` já tinha `identify_ingest_and_evaluate` (introduzida nesta
mesma fase, compondo `identify_and_ingest` + `evaluate_and_process`), mas
o `RealCameraPipeline` **não** a usa — ele chama Vision/Identity/Fusion/
Rules/Incident cada um no seu próprio `try/except`. A diferença importa:
num teste, "tudo ou nada" é aceitável (se uma etapa falha, o teste falha).
Numa câmera rodando ao vivo, uma falha temporária no Rules Engine não pode
impedir que o Fusion continue recebendo observações da câmera, nem travar
o loop de captura. Cada etapa reaproveita as mesmas funções de tradução de
contrato do `bridge.py` — só a orquestração do tratamento de erro é
diferente.

### 10.7 Limitações conhecidas desta fase

- O provider de identificação continua sendo o mock (Fase 3.6) — nenhuma
  mudança em reconhecimento facial real, banco biométrico ou embeddings.
- Em modo demonstração com webcam real, o provider mock não deriva
  identidade do conteúdo da imagem — ele só reconhece quem foi cadastrado
  com uma "seed" de texto específica. Isso significa que uma demonstração
  ao vivo com `MATCHED` de verdade exige um funcionário pré-cadastrado com
  uma seed fixa (`EPI_PIPELINE_DEMO_EMPLOYEE_SEED`), não reconhecimento
  automático de quem aparece na câmera — documentado explicitamente para
  não ser confundido com reconhecimento facial real.
- Não há Re-ID nem calibração espacial entre câmeras — cada câmera
  identifica pessoas de forma independente (mesma limitação já assumida na
  Fase 3.6).
- O script de demonstração com webcam/YOLO real (`scripts/run_camera_demo.py`)
  não pôde ser executado neste ambiente de geração de código (sem acesso a
  hardware de câmera nem a pesos de modelo YOLO) — só os testes
  automatizados com o provider mock foram validados de fato.

