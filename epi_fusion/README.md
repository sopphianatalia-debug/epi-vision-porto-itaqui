# EPI Vision — Fase 3.1: Fusion Service (multi-câmera por employee_id)

Consolida observações de **várias câmeras** em um único estado por funcionário,
usando `employee_id` como chave de junção. Resolve o problema de "capacete numa
câmera + botas em outra = a mesma pessoa" **sem** exigir que todas as câmeras
vejam o rosto ao mesmo tempo.

> Escopo: **apenas** junção por `employee_id`. Re-ID, calibração espacial e
> matching visual são a **Fase 3.2** (não implementados aqui, mas o código está
> preparado para recebê-los via `IdentityResolver`).

## Regras de segurança (inegociáveis)

- Só identidade `MATCHED`, com confiança suficiente e funcionário válido/ativo,
  vira chave. Todo o resto → **observação anônima**, nunca atribuída.
- Prefere "NÃO IDENTIFICADO" a "IDENTIFICADO ERRADO". Nunca associa por
  proximidade ou por "só existe um funcionário no local".
- `person_track_id` (por câmera) é sempre separado de `employee_id`.
- `NOT_VISIBLE` ≠ `MISSING` ≠ `NOT_OBSERVED` — silêncio de câmera que não
  enxerga a região **nunca** vira "ausente".
- Consolida **evidência** ("DETECTADO"), **não** conformidade final.

## Como rodar

```bash
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
# Docs: http://localhost:8000/docs
```

Sem banco, sem async — igual aos módulos 2 e 3.

## Fluxo multi-câmera (exemplo do spec)

Envie três observações do mesmo funcionário, uma por câmera:

```
POST /api/v1/fusion/observations
  CAM-01 / TRACK-001 / FUNC-000234  helmet=DETECTED, vest=DETECTED
  CAM-03 / TRACK-017 / FUNC-000234  gloves=DETECTED
  CAM-07 / TRACK-083 / FUNC-000234  boots=DETECTED
```

`GET /api/v1/fusion/employees/FUNC-000234` →

```json
{
  "employee_id": "FUNC-000234",
  "observations": {
    "CAM-01": {"track_id": "TRACK-001", "visible": ["helmet","vest"]},
    "CAM-03": {"track_id": "TRACK-017", "visible": ["gloves"]},
    "CAM-07": {"track_id": "TRACK-083", "visible": ["boots"]}
  },
  "ppe": {
    "helmet": {"status": "DETECTED", "confidence": 0.95},
    "vest":   {"status": "DETECTED", "confidence": 0.96},
    "gloves": {"status": "DETECTED", "confidence": 0.91},
    "boots":  {"status": "DETECTED", "confidence": 0.93}
  },
  "overall_status": "COMPLETE"
}
```

E a câmera sem rosto:

```
POST  CAM-07 / TRACK-089 / employee_id=null  boots=DETECTED
→ { "employee_id": null, "identity_status": "NOT_IDENTIFIED", "kind": "anonymous" }
```

Fica em `GET /api/v1/fusion/anonymous` — **nunca** atribuída a FUNC-000234.

## API

```
POST /api/v1/fusion/observations
GET  /api/v1/fusion/employees/{id}
GET  /api/v1/fusion/employees/{id}/observations
GET  /api/v1/fusion/cameras/{id}/observations
GET  /api/v1/fusion/anonymous
GET  /api/v1/fusion/conflicts
GET  /api/v1/fusion/state
POST /api/v1/fusion/cameras/{id}/visibility
GET  /api/v1/fusion/cameras/{id}/visibility
GET  /api/v1/fusion/metrics
GET  /api/v1/fusion/cameras/health
```

## Perfil de visibilidade por câmera

Diz o que cada câmera consegue ver, evitando falsos `MISSING`:

```
POST /api/v1/fusion/cameras/CAM-07/visibility
{ "visibility": {"face": false, "head": false, "torso": false, "hands": false, "feet": true} }
```

Agora, se a CAM-07 não reporta capacete, o resultado é `NOT_VISIBLE`, não `MISSING`.

## Consolidação e conflitos

Confiança combinada por *noisy-OR* (câmeras concordantes elevam a confiança —
não é média). Conflitos (`PROPER`×`IMPROPER`, presença×`MISSING`) são resolvidos
por visibilidade → confiança → recência; se a diferença for menor que
`FUS_CONFLICT_CONFIDENCE_MARGIN`, vira `UNKNOWN` e é registrado em
`GET /fusion/conflicts`.

## Tempo

- **Janela de fusão** (`FUS_FUSION_WINDOW_SECONDS`): observações antigas não
  influenciam o estado atual.
- **Last known state** (`FUS_IDENTITY_TTL_SECONDS`): se o rosto some, mantém a
  identidade por um TTL enquanto o mesmo track continua; depois → `NOT_IDENTIFIED`.
- **Expiração** (`FUS_STATE_TTL_SECONDS`): estados sem novas observações expiram
  (`expire_stale_state()`).

## Extensão para a Fase 3.2

`IdentityResolver` é a costura: hoje `EmployeeIdIdentityResolver`. A 3.2 fornece
`SpatialIdentityResolver` / `ReIdentificationResolver` que devolvem um
`IdentityResolution` — o FusionService consome sem reescrita. As observações
anônimas já ficam separadas, prontas para a 3.2 tentar resolver.

## Testes

```bash
pytest -q     # 48 testes (unit + integração), inclui saúde por câmera
```

Cobrem os 20 cenários unitários + integração multi-câmera + segurança:
1 câmera/1 func., 2 e 3 câmeras/mesmo func., tracks diferentes agrupados por
employee_id, sem employee_id, baixa confiança, ambíguo, câmera sem rosto,
NOT_VISIBLE vs MISSING, conflito entre câmeras, janela temporal, last-known,
expiração, estado consolidado, anônimos, e o fluxo do spec fim-a-fim.

## Observabilidade

`GET /fusion/metrics` (métricas globais — **inalterado**): observations_total,
observations_per_second, fusion_latency_ms, active_employee_states,
anonymous_observations, fusion_conflicts, expired_states, identity_match_rate,
observations_by_camera, observations_by_employee. Logs estruturados por evento
(`OBSERVATION_RECEIVED`, `IDENTITY_MATCHED`, `FUSION_CONFLICT`, ...),
**sem dados biométricos**.

Essas métricas respondem 7 das 8 perguntas de monitoramento. A 8ª — *"qual
câmera está com mais problemas?"* — é respondida por:

### `GET /fusion/cameras/health` — saúde operacional por câmera

Agrega, por `camera_id`, sinais que o FusionService já processa (nenhum dado
biométrico). Retorna a lista **ordenada da pior para a melhor** (`health_score`
crescente; câmeras sem dados vão para o fim):

| Campo | Significado |
|-------|-------------|
| `observations` | total de observações da câmera (cumulativo, consistente com `observations_total`) |
| `identity_matches` | observações que resultaram em identificação válida (MATCHED) |
| `identity_match_rate` | `identity_matches / observations` (null se `observations = 0`) |
| `anonymous` | observações que permaneceram sem `employee_id` |
| `conflicts` | **participações** em conflitos (cada câmera cuja evidência contribuiu para o conflito recebe +1) |
| `avg_confidence` | média das confidences informativas (presença/MISSING) das observações; null se não houver nenhuma |
| `not_visible` | observações em que a câmera reportou `NOT_VISIBLE` para ao menos um EPI |
| `not_visible_rate` | `not_visible / observations` (null se `observations = 0`) |
| `health_score` | indicador 0–100 (maior = melhor); null se não calculável |

**Fórmula do health_score** (determinística, explicável, fácil de ajustar):

```
identity_component   = identity_match_rate * 100
confidence_component = avg_confidence * 100
not_visible_component= (1 - not_visible_rate) * 100
conflict_rate        = min(conflicts / observations, 1.0)   # limitado a [0,1]
conflict_component   = (1 - conflict_rate) * 100

health_score = ( identity_component   * 0.35
               + confidence_component * 0.25
               + not_visible_component* 0.20
               + conflict_component   * 0.20 )
```

Pesos: identidade **0.35**, confiança **0.25**, visibilidade **0.20**, conflito
**0.20** (a identificação é o sinal mais informativo de utilidade operacional).
O volume de observações **não** entra no score — volume não é saúde.

**Valores ausentes / divisão por zero:**
- `observations = 0` → todas as taxas e o `health_score` são `null` (não se
  inventa 0%).
- se `avg_confidence` for `null` (a câmera nunca teve confidence informativa), o
  peso da confiança é **redistribuído proporcionalmente** entre os demais
  componentes — a câmera não é penalizada por um dado que não pode fornecer.
- `conflict_rate` é limitado a 1.0 (uma observação participa de vários EPIs, então
  `conflicts` pode exceder `observations`).

**Consistência com `/fusion/metrics`** (mesma janela cumulativa): a soma de
`observations` por câmera = `observations_total`; a soma de `anonymous` por câmera
= `anonymous_observations`; a soma de `identity_matches` por câmera = total de
matches. Já a soma de `conflicts` por câmera **pode ser maior** que
`fusion_conflicts`, porque o global conta *eventos* de conflito e o por-câmera
conta *participações* (um conflito envolve várias câmeras) — comportamento
documentado e intencional.

**Limitação (importante):** `health_score` é um indicador de **saúde operacional
observada**, não um diagnóstico de defeito físico. Uma identificação baixa pode
vir de ângulo, iluminação, obstrução ou simplesmente de uma área sem pessoas —
não necessariamente de uma câmera com defeito.

## Arquivos

Ver `docs/architecture.md` para as decisões e o mapeamento de entidades para
banco. Nenhum módulo existente (1, 2, 3) foi modificado — a fusão é aditiva e se
integra pelas observações que os módulos já produzem.

## Estado de sinal das câmeras (REST + WebSocket)
- `GET /api/v1/fusion/cameras/status`: `ONLINE` se a câmera enviou observação nos últimos `FUS_CAMERA_STALE_SECONDS` (padrão 30 s), senão `OFFLINE` (sem sinal). Só lista câmeras que já enviaram algo; "cadastrada e nunca vista" é deduzida pela tela cruzando com o cadastro do Tracker.
- `ws://localhost:8002/api/v1/fusion/ws/cameras`: ao conectar manda `SNAPSHOT`; depois só `CAMERA_STATUS_CHANGED` (`camera_id`, `status`, `previous_status`, `last_observation_at`) quando o estado muda (reavaliado a cada `FUS_WS_POLL_SECONDS`, padrão 1 s).
- Descreve só se a câmera está enviando dados. **Não decide conformidade nem abre incidente**; silêncio de câmera nunca é violação.
