# epi_alerts — Alertas internos

Dá visibilidade ao que OUTROS módulos já decidiram. Não decide conformidade,
não cria incidente e não acusa ninguém.

## Origens
| Origem | Alerta | Gravidade |
|---|---|---|
| Tracker | Rastreador offline / bateria baixa | Atenção |
| Tracker | Localização expirada | Informativo |
| Fusion | Possível inconsistência câmera × rastreador | Atenção (nunca violação) |
| Incident | Incidente aberto | Crítico (CRITICAL/HIGH), Atenção (MEDIUM), Informativo (LOW/INFO) |

## Ciclo
Novo → Visto → Resolvido. O mesmo problema gera UM alerta (não repete a cada
leitura). Quando o problema some, o alerta se resolve sozinho. Se uma origem
estiver fora do ar, nada é resolvido e a tela avisa.

## Executar
```
cd epi_alerts
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --port 8005
```
Variáveis (prefixo `EPI_ALERTS_`): `TRACKER_URL` (8010), `FUSION_URL` (8002),
`INCIDENT_URL` (8004), `SYNC_MIN_INTERVAL_SECONDS` (3).

## API
`GET /api/v1/alerts` · `GET /api/v1/alerts/summary` · `POST /api/v1/alerts/sync`
· `POST /api/v1/alerts/{id}/ack`

Fora do escopo: WhatsApp, e-mail, SMS (próxima etapa, depois de escolher o canal).
