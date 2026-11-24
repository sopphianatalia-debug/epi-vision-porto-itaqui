#!/usr/bin/env python3
"""
start_demo.py — sobe TODOS os serviços da demonstração com um comando e os
encerra todos com Ctrl+C (sem deixar porta presa).

Portas fixas: vision 8000 · identity 8001 · fusion 8002 · rules 8003 ·
incident 8004 · alerts 8005 · tracker 8010.

Cadastra um funcionário de demonstração no Identity (identidade MOCK — não é
reconhecimento facial real), atribui capacete e colete a ele no tracker e
imprime o comando exato para rodar a câmera.

Uso:
    python scripts/start_demo.py --model /caminho/best.pt        # YOLO real
    python scripts/start_demo.py --mock                          # sem YOLO

Todos os serviços rodam no MESMO ambiente Python (um único venv com as
dependências de todos). Cada serviço é um subprocesso, como na Fase 3.5.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "epi_integration"))

from app.identity_client import IdentityClient
from app.rules_tuning import apply_persistence  # noqa: E402

SERVICES = {  # nome: (pasta, porta)
    "vision": ("epi_ppe", 8000),
    "identity": ("epi_identity", 8001),
    "fusion": ("epi_fusion", 8002),
    "rules": ("epi_rules", 8003),
    "incident": ("epi_incident", 8004),
    "alerts": ("epi_alerts", 8005),
    "tracker": ("epi_tracker", 8010),
}
DEMO_AREA = "PATIO-02"
procs: list[subprocess.Popen] = []


def stop_all(*_args) -> None:
    for p in procs:
        if p.poll() is None:
            p.terminate()
    deadline = time.time() + 5
    for p in procs:
        try:
            p.wait(timeout=max(0.1, deadline - time.time()))
        except subprocess.TimeoutExpired:
            p.kill()
    print("\nServiços encerrados.")


def start(name: str, env: dict, log_dir: Path) -> None:
    folder, port = SERVICES[name]
    log = open(log_dir / f"{name}.log", "w")
    e = os.environ.copy()
    e["PYTHONPATH"] = str(ROOT / folder)
    e.update(env)
    procs.append(subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port),
         "--log-level", "warning", "--loop", "asyncio"],
        cwd=str(ROOT / folder), env=e, stdout=log, stderr=subprocess.STDOUT,
    ))


def wait_healthy(name: str, timeout: float = 90.0) -> None:
    port = SERVICES[name][1]
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.0).status_code == 200:
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)
    raise RuntimeError(f"'{name}' não respondeu em {timeout:.0f}s — veja o log em demo_logs/{name}.log")


# Câmeras da demonstração (cadastro no Tracker; a tela Câmeras lê de lá).
# CAM-ENTRY-02 é a webcam da demo (setor fictício só para a demonstração).
# As CAM-EX-* são EXEMPLOS (example=True): não são câmeras reais; apague-as na tela quando cadastrar as reais.
DEMO_CAMERAS = [
    {"camera_id": "CAM-ENTRY-02", "name": "Entrada — demonstração", "sector": "CARGA_GERAL_CELULOSE", "kind": "ENTRADA", "pos": {"x": 14, "y": 86}},
    {"camera_id": "CAM-EX-GS-ENT", "name": "Entrada Granéis Sólidos", "sector": "GRANEIS_SOLIDOS", "kind": "ENTRADA", "pos": {"x": 14, "y": 86}, "example": True},
    {"camera_id": "CAM-EX-GS-INT1", "name": "Interna Granéis Sólidos 1", "sector": "GRANEIS_SOLIDOS", "kind": "INTERNA", "pos": {"x": 45, "y": 68}, "example": True},
    {"camera_id": "CAM-EX-GS-INT2", "name": "Interna Granéis Sólidos 2", "sector": "GRANEIS_SOLIDOS", "kind": "INTERNA", "pos": {"x": 78, "y": 80}, "example": True},
    {"camera_id": "CAM-EX-PB-ENT", "name": "Entrada Píer e Bordo", "sector": "PIER_BORDO", "kind": "ENTRADA", "pos": {"x": 14, "y": 86}, "example": True},
    {"camera_id": "CAM-EX-PB-INT1", "name": "Interna Píer e Bordo", "sector": "PIER_BORDO", "kind": "INTERNA", "pos": {"x": 60, "y": 70}, "example": True},
]


def seed_cameras(t: httpx.Client) -> None:
    for cam in DEMO_CAMERAS:
        r = t.post("/cameras", json=cam)
        if r.status_code not in (201, 409):   # 409 = já cadastrada: ok
            r.raise_for_status()


def seed_tracker(employee_code: str, seed_demo_cameras: bool = True) -> None:
    t = httpx.Client(base_url="http://127.0.0.1:8010/api/v1", timeout=5)
    if seed_demo_cameras:
        seed_cameras(t)
    t.post("/areas", json={"area_id": DEMO_AREA, "name": "Pátio 02"})
    t.post("/areas", json={"area_id": "ARMAZEM", "name": "Armazém"})
    for i, kind in enumerate(("helmet", "vest"), start=1):
        tid = f"TRACKER-DEMO-{i:02d}"
        t.post("/trackers", json={"technology": "MOCK", "tracker_id": tid})
        ppe_id = t.post("/ppe", json={"ppe_type": kind, "tracker_id": tid}).json()["ppe_id"]
        t.post(f"/ppe/{ppe_id}/assign", json={"employee_id": employee_code})
        t.post("/demo/location", json={"tracker_id": tid, "area_id": DEMO_AREA})
        t.post(f"/trackers/{tid}/poll")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="caminho do best.pt (provider YOLO)")
    ap.add_argument("--mock", action="store_true", help="usa o detector mock (sem YOLO)")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--violation-seconds", type=float, default=3.0,
                    help="segundos CONTÍNUOS sem o EPI até abrir um incidente (padrão 3)")
    ap.add_argument("--recovery-seconds", type=float, default=3.0,
                    help="segundos CONTÍNUOS com o EPI visível até resolver o incidente (padrão 3)")
    ap.add_argument("--person-threshold", type=float, default=0.65,
                    help="confiança mínima para aceitar uma PESSOA (padrão 0.65; "
                         "o do serviço é 0.50 e deixava passar sombras/reflexos)")
    ap.add_argument("--min-confidence", type=float, default=0.60,
                    help="confiança mínima do EPI para valer como conforme (padrão da demo 0.60; "
                         "o das regras é 0.85, alto para um yolov8n e deixava capacete real "
                         "em INDETERMINATE). Abaixo disso o resultado é indeterminado, nunca violação.")
    ap.add_argument("--cameras-file", default="~/.epi_vision/cameras.json",
                    help="onde o cadastro de câmeras é gravado (sobrevive a reiniciar e a trocar de versão). "
                         "Apague o arquivo para voltar às câmeras de exemplo.")
    ap.add_argument("--evidence", action="store_true",
                    help="liga login (epi_auth :8006) e a evidência em imagem no Incident. Exige EPI_JWT_SECRET e "
                         "INC_SERVICE_KEY no ambiente (ex.: set -a; . .local/segredos.env; set +a).")
    args = ap.parse_args()
    if not args.model and not args.mock:
        ap.error("informe --model /caminho/best.pt ou --mock")

    log_dir = Path.cwd() / "demo_logs"
    log_dir.mkdir(exist_ok=True)
    signal.signal(signal.SIGINT, lambda *a: (stop_all(), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda *a: (stop_all(), sys.exit(0)))

    db = tempfile.mkstemp(prefix="epi_identity_demo_", suffix=".db")[1]
    vision_env = {"PPE_ENVIRONMENT": "test"}
    if args.mock:
        vision_env["PPE_DETECTOR_PROVIDER"] = "mock"
    else:
        vision_env["PPE_PERSON_CONFIDENCE_THRESHOLD"] = str(args.person_threshold)
        vision_env.update({"PPE_DETECTOR_PROVIDER": "yolo", "PPE_DETECTOR_MODEL_PATH": str(Path(args.model).resolve()),
                           "PPE_DETECTOR_DEVICE": args.device})

    secret = os.environ.get("EPI_JWT_SECRET") or "integration-tests-shared-secret-please-ignore"
    incident_env: dict = {}
    if args.evidence:
        if not os.environ.get("EPI_JWT_SECRET") or not os.environ.get("INC_SERVICE_KEY"):
            ap.error("--evidence exige EPI_JWT_SECRET e INC_SERVICE_KEY no ambiente (set -a; . .local/segredos.env; set +a)")
        local = ROOT / ".local"
        (local / "evidencias").mkdir(parents=True, exist_ok=True)
        SERVICES["auth"] = ("epi_auth", 8006)
        incident_env = {"INC_AUTH_MODE": "required", "EPI_JWT_SECRET": secret,
                        "INC_SERVICE_KEY": os.environ["INC_SERVICE_KEY"],
                        "INC_EVIDENCE_DIR": str(local / "evidencias"),
                        "INC_IDENTITY_URL": "http://127.0.0.1:8001/api/v1", "INC_DB_PATH": str(local / "incident.db")}

    cameras_path = Path(args.cameras_file).expanduser()
    first_run = not cameras_path.exists()          # só semeia as câmeras de exemplo na primeira vez
    envs = {
        "vision": vision_env,
        "identity": {"EPI_ENVIRONMENT": "test", "EPI_DATABASE_URL": f"sqlite+aiosqlite:///{db}",
                     "EPI_JWT_SECRET": secret},
        "fusion": {"FUS_ENVIRONMENT": "test"},
        "rules": {}, "incident": incident_env,
        "auth": {"AUTH_DB_PATH": str(ROOT / ".local" / "auth.db"), "EPI_JWT_SECRET": secret},
        "tracker": {"EPI_TRACKER_LOCATION_FRESH_SECONDS": "3600", "EPI_TRACKER_LOCATION_TTL_SECONDS": "7200",
                    "EPI_TRACKER_CAMERAS_FILE": str(cameras_path)},
        "alerts": {"EPI_ALERTS_SYNC_MIN_INTERVAL_SECONDS": "2"},
    }
    print("Subindo serviços (o YOLO pode levar alguns segundos para carregar)...")
    for name in SERVICES:
        start(name, envs[name], log_dir)
    try:
        for name in SERVICES:
            wait_healthy(name)
            print(f"  ok  {name:9s} :{SERVICES[name][1]}")

        tuned = apply_persistence("http://127.0.0.1:8003/api/v1", ("RULE-PATIO-GERAL-001", "RULE-PATIO-CARGA-001"),
                                  args.violation_seconds, args.recovery_seconds,
                                  min_confidence=args.min_confidence)
        print(f"  regras com persistência: violação {args.violation_seconds:g}s / recuperação "
              f"{args.recovery_seconds:g}s / confiança mínima {args.min_confidence:g} -> versões {tuned}")
        ident = IdentityClient("http://127.0.0.1:8001/api/v1")
        emp = ident.create_employee(registration="DEMO-0001", name="Funcionário Demonstração")
        ident.enroll(employee_id=emp["id"], seed=emp["employee_code"])
        code = emp["employee_code"]
        seed_tracker(code, seed_demo_cameras=first_run)
        print(f"  câmeras: {'cadastro criado com as de exemplo' if first_run else 'cadastro existente mantido'} em {cameras_path}")
    except Exception as exc:  # noqa: BLE001
        print(f"\nERRO ao preparar a demonstração: {exc}")
        stop_all()
        return 1

    evidence_env = ("EPI_PIPELINE_SEND_EVIDENCE=true EPI_PIPELINE_INCIDENT_SERVICE_KEY=$INC_SERVICE_KEY \\\n  "
                    if args.evidence else "")
    print(f"""
Tudo pronto. Funcionário de demonstração: {code} (identidade MOCK)
Capacete e colete dele estão no tracker em {DEMO_AREA}.

Em OUTRO terminal (mesmo venv), rode a câmera:

  cd {ROOT / 'epi_integration'}
  {evidence_env}EPI_PIPELINE_DEMO_EMPLOYEE_SEED={code} \\
  EPI_PIPELINE_OPERATION=GERAL \\
  EPI_PIPELINE_BLIND_REGIONS=feet,hands \\
  EPI_PIPELINE_TRACKER_URL=http://127.0.0.1:8010/api/v1 \\
  EPI_PIPELINE_TRACKER_AREA_ID={DEMO_AREA} \\
  python scripts/run_camera_demo.py --source 0 --camera-id CAM-ENTRY-02

Interface: cd {ROOT / 'epi_tracker' / 'frontend'} && python3 -m http.server 8020
           abra http://127.0.0.1:8020/index.html

Pressione Ctrl+C aqui para encerrar TODOS os serviços.""")
    while True:
        time.sleep(1)
        dead = [n for n, p in zip(SERVICES, procs) if p.poll() is not None]
        if dead:
            print(f"\nServiço(s) caíram: {dead}. Veja demo_logs/. Encerrando.")
            stop_all()
            return 1


if __name__ == "__main__":
    sys.exit(main())
