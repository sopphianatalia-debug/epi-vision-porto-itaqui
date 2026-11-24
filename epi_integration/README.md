
## Evidência em imagem

Com `EPI_PIPELINE_SEND_EVIDENCE=true`, ao abrir um incidente o pipeline recorta **só a pessoa** (com margem, corpo inteiro, ≤ 1280 px) e envia ao Incident Service com as caixas de detecção relativas ao recorte. O quadro inteiro nunca sai da câmera. Se o Incident exigir `INC_SERVICE_KEY`, defina `EPI_PIPELINE_INCIDENT_SERVICE_KEY` no seu `.env` local (nunca no Git). Falha no envio só deixa de haver imagem: nunca derruba o pipeline nem altera conformidade.
