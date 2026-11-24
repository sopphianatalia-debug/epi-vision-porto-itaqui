#!/usr/bin/env bash
# Roda a câmera da demonstração (com evidência) em UM comando. Use depois de subir o start_demo.py --evidence.
# Uso:  ./scripts/camera_local.sh [fonte]      fonte: 0 (webcam, padrão) | video.mp4 | rtsp://...
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$ROOT/.local/segredos.env" ] || { echo "Falta .local/segredos.env (rode antes o ./scripts/subir_local.sh start uma vez)."; exit 1; }
set -a; . "$ROOT/.local/segredos.env"; set +a
export EPI_PIPELINE_SEND_EVIDENCE=true
export EPI_PIPELINE_INCIDENT_SERVICE_KEY="$INC_SERVICE_KEY"
export EPI_PIPELINE_DEMO_EMPLOYEE_SEED="${EPI_PIPELINE_DEMO_EMPLOYEE_SEED:-FUNC-000001}"
export EPI_PIPELINE_OPERATION=GERAL
export EPI_PIPELINE_BLIND_REGIONS=feet,hands
export EPI_PIPELINE_TRACKER_URL=http://127.0.0.1:8010/api/v1
export EPI_PIPELINE_TRACKER_AREA_ID=PATIO-02
cd "$ROOT/epi_integration"
exec python scripts/run_camera_demo.py --source "${1:-0}" --camera-id CAM-ENTRY-02
