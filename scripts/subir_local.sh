#!/usr/bin/env bash
# Sobe os serviços do EPI Vision no seu computador (macOS/Linux) para testar com webcam ou vídeo.
# Uso:   ./scripts/subir_local.sh start | stop | status
# Logs:  .local/logs/<servico>.log     Dados locais (fora do Git): .local/
# Antes: ver docs/TESTE_LOCAL.md (venv com as dependências e, para YOLO, o arquivo .pt).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL="$ROOT/.local"; LOGS="$LOCAL/logs"; PIDS="$LOCAL/pids"
mkdir -p "$LOGS" "$PIDS" "$LOCAL/evidencias"
PY="${PYTHON:-python}"

# Segredos: gerados uma vez e guardados só aqui (.local/ está no .gitignore).
[ -f "$LOCAL/segredos.env" ] || {
  umask 077
  printf 'EPI_JWT_SECRET=%s\nINC_SERVICE_KEY=%s\n' "$($PY -c 'import secrets;print(secrets.token_urlsafe(32))')" "$($PY -c 'import secrets;print(secrets.token_urlsafe(24))')" > "$LOCAL/segredos.env"
}
# Chave que protege os modelos faciais no Identity. Sem ela fixa, o serviço cria uma nova a cada início e
# não consegue mais abrir o que gravou antes (erro InvalidToken). Gerada uma vez e guardada só aqui.
grep -q '^EPI_BIOMETRIC_ENCRYPTION_KEY=' "$LOCAL/segredos.env" || {
  umask 077
  printf 'EPI_BIOMETRIC_ENCRYPTION_KEY=%s\n' "$($PY -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')" >> "$LOCAL/segredos.env"
}
set -a; . "$LOCAL/segredos.env"; set +a

# nome:pasta:porta
SERVICES="epi_ppe:epi_ppe:8000 identity:epi_identity:8001 fusion:epi_fusion:8002 rules:epi_rules:8003 incident:epi_incident:8004 auth:epi_auth:8006"

launch() { # nome pasta porta  (variáveis de ambiente já exportadas no subshell)
  local name=$1 dir=$2 port=$3
  ( cd "$ROOT/$dir"
    case "$name" in
      epi_ppe)  # Com câmera real o detector TEM que ser o YOLO. Se existir um best.pt do treino, usa ele sozinho.
                if [ -z "${PPE_DETECTOR_PROVIDER:-}" ] && [ -f "$ROOT/runs/detect/train/weights/best.pt" ]; then
                  export PPE_DETECTOR_PROVIDER=yolo PPE_DETECTOR_MODEL_PATH="$ROOT/runs/detect/train/weights/best.pt"
                fi
                export PPE_DETECTOR_PROVIDER="${PPE_DETECTOR_PROVIDER:-mock}"; export PPE_DETECTOR_MODEL_PATH="${PPE_DETECTOR_MODEL_PATH:-yolov8n.pt}"
                echo "  epi_ppe: detector=$PPE_DETECTOR_PROVIDER modelo=$PPE_DETECTOR_MODEL_PATH";;
      identity) export EPI_ENVIRONMENT=test EPI_DATABASE_URL="sqlite+aiosqlite:///$LOCAL/identity.db";;
      incident) export INC_AUTH_MODE=required INC_DB_PATH="$LOCAL/incident.db" INC_EVIDENCE_DIR="$LOCAL/evidencias" INC_IDENTITY_URL="http://127.0.0.1:8001/api/v1";;
      auth)     export AUTH_DB_PATH="$LOCAL/auth.db";;
    esac
    PYTHONPATH="$ROOT/$dir" nohup "$PY" -m uvicorn app.main:app --port "$port" >"$LOGS/$name.log" 2>&1 &
    echo $! > "$PIDS/$name.pid" )
}

case "${1:-}" in
  start)
    for s in $SERVICES; do IFS=: read -r n d p <<<"$s"
      if [ -f "$PIDS/$n.pid" ] && kill -0 "$(cat "$PIDS/$n.pid")" 2>/dev/null; then echo "$n já está rodando"; continue; fi
      launch "$n" "$d" "$p"; done
    echo "Aguardando os serviços..."
    for s in $SERVICES; do IFS=: read -r n d p <<<"$s"
      ok=0; for _ in $(seq 1 40); do curl -fs "http://127.0.0.1:$p/health" >/dev/null 2>&1 && { ok=1; break; }; sleep 0.5; done
      [ $ok = 1 ] && echo "  OK   $n (porta $p)" || echo "  FALHOU $n — veja $LOGS/$n.log"
    done
    echo; echo "Usuário (uma vez):  cd epi_auth && AUTH_DB_PATH=../.local/auth.db python -m app.cli create-user --username ana --name \"Ana\" --role SUPERVISOR"
    echo; echo "Câmera:  EPI_PIPELINE_SEND_EVIDENCE=true EPI_PIPELINE_INCIDENT_SERVICE_KEY=\$INC_SERVICE_KEY python epi_integration/scripts/run_camera_demo.py --source 0"
    ;;
  stop)
    for s in $SERVICES; do IFS=: read -r n d p <<<"$s"
      [ -f "$PIDS/$n.pid" ] && { kill "$(cat "$PIDS/$n.pid")" 2>/dev/null || true; rm -f "$PIDS/$n.pid"; echo "parou $n"; }
    done;;
  status)
    for s in $SERVICES; do IFS=: read -r n d p <<<"$s"
      curl -fs "http://127.0.0.1:$p/health" >/dev/null 2>&1 && echo "OK     $n ($p)" || echo "PARADO $n ($p)"
    done;;
  *) echo "uso: $0 start|stop|status"; exit 1;;
esac
