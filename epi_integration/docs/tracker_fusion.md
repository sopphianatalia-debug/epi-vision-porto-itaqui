# Tracker -> Fusion (evidência de localização de EPI)

O tracker informa ONDE o EPI está. Não prova uso (ASSIGNED != WORN), não decide
conformidade e uma divergência com a câmera é `POSSIBLE_INCONSISTENCY`, nunca
violação. O Rules Engine continua sendo o único decisor.

## Fluxo
1. Pipeline reconhece o funcionário (MATCHED) na câmera.
2. Lê no tracker `GET /employees/{id}/summary` e, para cada EPI atribuído,
   `GET /trackers/{tracker_id}/fusion-observation`.
3. Envia ao Fusion `POST /fusion/ppe-locations` (fonte separada; não entra na
   consolidação por câmera).
4. Fusion compara a área da câmera (`POST /fusion/cameras/{id}/area`) com a do
   tracker quando a câmera viu o EPI. Consulta: `GET /fusion/ppe-inconsistencies`
   e `GET /fusion/employees/{id}/ppe-locations`.

Localização `EXPIRED` ou evidência mais antiga que `FUS_STATE_TTL_SECONDS` não
afirma nada. Falha do tracker nunca interrompe o frame.

## Variáveis (epi_integration)
- `EPI_PIPELINE_TRACKER_URL` — ex. `http://127.0.0.1:8010/api/v1` (vazio = desligado)
- `EPI_PIPELINE_TRACKER_AREA_ID` — área desta câmera no vocabulário do tracker, ex. `PATIO-02`
- `EPI_PIPELINE_BLIND_REGIONS` — regiões que o modelo não avalia, ex. `feet,hands`
