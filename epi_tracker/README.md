# Fase 3.8 — Tracker Service (rastreamento de EPIs)

## O conceito

> "Sistema inteligente de monitoramento de segurança ocupacional baseado em
> visão computacional e rastreamento de EPIs, capaz de verificar a
> conformidade dos funcionários na entrada de diferentes áreas e utilizar
> informações de localização para ampliar a cobertura do monitoramento."

## O problema

A pergunta certa não é "o funcionário está usando EPI?" — é **"o
funcionário está numa área que exige certos EPIs, e ele está com eles?"**.
Os requisitos mudam por área/operação/função (isso já era responsabilidade
do Rules Engine, desde a Fase 3.1, e continua sendo).

A visão computacional tem um limite físico real: linha de visão, câmeras
cegas, obstáculos, baixa luz. O Tracker Service resolve exatamente esse
ponto cego — mas **sem fingir que resolve mais do que resolve**.

## A distinção mais importante desta fase

**O tracker fica no EPI, não na pessoa.**

```
TRACKER-001 está em PÁTIO-02
```

significa **"o capacete-001 está fisicamente nesta área"** — não
**"o funcionário X está usando o capacete"**. Essa diferença é preservada
em todo o código: `PPEAsset.employee_id` significa **ASSIGNED**
(atribuição administrativa), nunca **WORN** (uso comprovado). A prova de
uso continua sendo a câmera, em outro módulo.

## Câmera x Tracker — fontes complementares, não concorrentes

| | Câmera | Tracker |
|---|---|---|
| Responde | "Estou vendo o funcionário usar o EPI?" | "Onde esse EPI está fisicamente?" |
| Funciona sem linha de visão? | Não | Sim |
| Prova uso? | Sim (evidência direta) | Não (só localização) |

## O que foi construído

Um módulo novo e **independente**, `epi_tracker/`, seguindo o mesmo padrão
arquitetural dos módulos anteriores (estado em memória atrás de
interfaces, Clock/EventBus/Provider injetáveis, FastAPI síncrono). Não
toca em nenhum módulo existente — Identity, Fusion, Rules, Incident e
epi_ppe continuam exatamente como estavam.

| Camada | Arquivo | O que faz |
|---|---|---|
| Domínio | `app/domain/enums.py`, `models.py` | Tracker, PPEAsset, Area, LocationReader, SafetyCheckpoint, TrackerObservation, SafetyCheck, LocationInconsistency |
| Infraestrutura | `app/infrastructure/` | Clock/FakeClock, EventBus, repositórios em memória |
| Provider | `app/providers/mock_provider.py` | Simula movimentação, bateria baixa, offline, tracker desconhecido |
| Serviço | `app/service.py` | Toda a lógica de negócio — nunca decide conformidade |
| API | `app/api/` | Endpoints REST |

## Por que este módulo nunca decide conformidade

O `TrackerService` não tem, em lugar nenhum do código, uma função que
retorne `COMPLIANT`/`NON_COMPLIANT`. O `SafetyCheck` **representa** um
resultado que foi decidido em outro lugar (Rules Engine, numa integração
futura) — ele só guarda o contexto (funcionário, área, checkpoint,
EPIs detectados/ausentes). Isso é verificado em
`test_safety_check_represents_result_does_not_decide` (`tests/test_service.py`).

## O TTL — nunca afirma presença eterna

Uma leitura de localização vale por um tempo limitado:

```
CURRENT (leitura recente) -> LAST_KNOWN (mais antiga, mas ainda dentro do TTL) -> EXPIRED
```

Depois de `EPI_TRACKER_LOCATION_TTL_SECONDS` (padrão 30s), o sistema
**para de informar uma área** para aquele tracker — `area_id` vira `None`
na resposta. Isso evita a pior classe de erro deste tipo de sistema:
assumir que um EPI "ainda está lá" porque a última leitura, há muito
tempo, dizia isso.

## Inconsistência — evidência preservada, nunca uma violação sozinha

Se a câmera confirma o funcionário numa área, mas o tracker do EPI
atribuído a ele está em outra, o sistema registra um
`POSSIBLE_INCONSISTENCY` — nunca cria um incidente por conta própria (essa
decisão continua sendo do Rules/Incident Service, fora deste módulo).

```python
# câmera confirmou FUNC-000234 em PATIO-02
# tracker do capacete dele está no ARMAZÉM
svc.check_location_inconsistency("FUNC-000234", "PATIO-02", helmet.ppe_id)
# -> LocationInconsistency(type=POSSIBLE_INCONSISTENCY, ppe_area_id="ARMAZEM", ...)
```

## Contrato compatível com o Fusion (preparado, não integrado ainda)

`GET /trackers/{id}/fusion-observation` monta o payload no formato que uma
integração futura enviaria ao Fusion como evidência de localização — mas
**esta fase não chama o Fusion de verdade**. Isso é deliberado (seções 22 e
41 do pedido original): primeiro provar que o contrato é sólido e
testável sozinho, depois integrar.

```json
{
  "source": "tracker",
  "tracker_id": "TRACKER-001",
  "ppe_id": "PPE-000001",
  "ppe_type": "helmet",
  "employee_id_assigned": "FUNC-000234",
  "area_id": "PATIO-02",
  "location_state": "CURRENT",
  "confidence": 1.0,
  "timestamp": "2026-01-01T12:00:00+00:00"
}
```

Repare no nome do campo: `employee_id_assigned`, nunca `employee_id_wearing`
ou parecido — o nome do campo já deixa a distinção impossível de ignorar
por quem for consumir esse contrato depois.

## Como rodar

```bash
cd epi_tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests -v
```

Nenhuma dependência de outro módulo — este é o único módulo do projeto que
roda 100% isolado, sem precisar de nenhum outro serviço no ar.

## Bugs encontrados e corrigidos durante o desenvolvimento

Dois erros reais apareceram ao **executar** o código (não apareceriam só
com `py_compile`):

1. **Import cruzado errado** — `AreaNotFoundError`, `PPEAssetNotFoundError`
   etc. são definidas em `app/service.py`, mas `routes.py` e os testes
   tentavam importá-las de `app/domain/models.py`. Corrigido.
2. **Métricas vazando entre execuções** — o objeto de métricas era um
   singleton de módulo (`metrics = TrackerMetrics()`), não limpo entre
   chamadas de `get_service()`. Corrigido com injeção de dependência de
   verdade (`get_metrics()`, também via `lru_cache`, limpo nos testes do
   mesmo jeito que `get_service`/`get_provider` já eram).

Ambos foram encontrados executando a suíte de testes de verdade (com um
substituto mínimo de `pytest.raises`, já que este ambiente de geração de
código não tem acesso à internet para instalar `pytest`/`fastapi`) — não
por inspeção manual do código.

## Status de execução

- **`tests/test_service.py`**: 36/36 testes executados de verdade e
  passando (os 24 cenários da seção 36 do pedido).
- **`tests/test_end_to_end.py`**: cenário completo da seção 37 (duas
  áreas, regras diferentes, inconsistência tracker×câmera) executado de
  verdade e passando.
- **`tests/test_api.py`**: escrito com o mesmo rigor, com verificação de
  que `routes.py`/`deps.py`/`schemas.py`/`main.py` importam corretamente
  (usando módulos `fastapi`/`pydantic` simulados, já que as bibliotecas
  reais não estão disponíveis neste ambiente) — mas **não executado de
  ponta a ponta com um servidor real**. Precisa ser confirmado na sua
  máquina com `pytest tests/test_api.py -v`.

## O que NÃO foi implementado nesta fase (por pedido explícito)

Hardware físico (BLE/RFID/UWB reais), GPS, reconhecimento facial real,
biometria, Re-ID, matching espacial probabilístico, dashboard,
notificações externas. Também não foi feita a integração real com Fusion —
só o contrato compatível.

## Próximos passos

1. Confirmar `pytest tests -v` completo na sua máquina.
2. Integração real com o Fusion (consumir `/fusion-observation` de
   verdade, do lado do Fusion).
3. Alertas/Notificações.
4. Dashboard Operacional.

## Fase 3.8B — Interface web

Um frontend React completo foi construído em `frontend/` — Dashboard,
Mapa Operacional, Funcionários, EPIs, Rastreadores, Áreas, Checkpoints,
Inconsistências, Histórico e Simulação. Ver `frontend/README.md` para
detalhes completos, incluindo como validei o fluxo central (mover um
tracker de área e ver o mapa/funcionário atualizarem) de ponta a ponta
num navegador real, mesmo sem conseguir instalar o backend real neste
ambiente — usando um servidor mock mínimo (só biblioteca padrão do
Python) que implementa o mesmo contrato HTTP.

Três pequenas extensões foram feitas no backend para viabilizar a
interface (nenhuma mexe em lógica de negócio existente):
- `GET /employees` e `GET /employees/{id}/summary` — agregação de dados
  que já existiam (EPIs atribuídos + histórico de Safety Checks).
- `GET /inconsistencies` — passou a persistir as inconsistências
  detectadas (antes só existiam como retorno pontual de
  `POST /inconsistency-check`, sem histórico consultável).
- `GET /events` — expõe o histórico do EventBus (já existia em memória,
  faltava só o endpoint).
- CORS liberado no backend (`app/main.py`) — necessário para o frontend
  (outra origem/porta) conseguir chamar a API.

## Latitude e longitude da câmera
`latitude` e `longitude` (graus decimais, opcionais) no cadastro de câmeras (`/api/v1/cameras`). Devem vir **juntas** (ou nenhuma) e dentro de -90..90 / -180..180 (422 caso contrário). Câmeras antigas, sem coordenadas, continuam carregando (valem `null`). Servem ao mapa geográfico e não decidem conformidade. A tela *Gerenciar câmeras* tem os dois campos.
