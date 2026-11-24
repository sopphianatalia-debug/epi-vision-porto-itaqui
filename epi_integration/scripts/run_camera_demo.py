#!/usr/bin/env python3
"""
run_camera_demo.py — Fase 3.7, a peça que faltava: liga a câmera real ao
pipeline de negócio completo (Vision -> Identity -> Fusion -> Rules ->
Incident), com overlay ao vivo.

IMPORTANTE — por que este script usa cv2.VideoCapture DIRETO, em vez do
CameraService/OpenCVCamera do epi_ppe: este script já importa
`app.camera_pipeline` (epi_integration) — importar TAMBÉM o `app.camera.
service` do epi_ppe no mesmo processo colidiria os dois pacotes chamados
`app` (o mesmo motivo documentado em `app/runner.py` desde a Fase 3.5).
A captura de frame em si é simples o bastante (abrir uma fonte, ler frames,
tratar falha) para não precisar da abstração completa do Módulo 2 aqui —
"o loop da câmera deve permanecer separado da lógica de negócio" (seção 4
do pedido) já é respeitado: este arquivo só captura e desenha; TODA a
decisão (identidade, fusão, regras, incidente) continua em
`app/camera_pipeline.py`, chamada por HTTP nos outros 4 serviços.

NÃO TESTADO NESTE AMBIENTE DE GERAÇÃO DE CÓDIGO — sem webcam nem display
disponíveis aqui. Só a sintaxe foi verificada (`py_compile`). Precisa ser
validado na sua máquina.

Pré-requisitos (ver README_FASE_3_7.md para o passo a passo completo):
  1. epi_identity, epi_fusion, epi_rules, epi_incident rodando (uvicorn,
     como em todas as fases anteriores).
  2. epi_ppe rodando com PPE_DETECTOR_PROVIDER=yolo e um modelo de EPI real
     configurado (PPE_DETECTOR_MODEL_PATH), OU com PPE_DETECTOR_PROVIDER=mock
     se voce so quer testar a integracao sem deteccao real.
  3. pip install opencv-python-headless numpy neste ambiente (epi_integration).

Exemplos:
    python scripts/run_camera_demo.py --source 0 --camera-id CAM-01
    python scripts/run_camera_demo.py --source video.mp4 --headless --save saida.mp4
    EPI_PIPELINE_DEMO_SCENARIO=missing_helmet python scripts/run_camera_demo.py --source 0
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.clients import TrackerClient  # noqa: E402
from app.camera_config import get_camera_pipeline_settings, resolve_camera_visibility, resolve_demo_scenario_override  # noqa: E402
from app.camera_pipeline import PersonPipelineResult, RealCameraPipeline  # noqa: E402
from app.clients import FusionClient, IncidentClient, RulesClient, VisionClient  # noqa: E402
from app.identity_client import IdentityClient  # noqa: E402

STATUS_COLOR = {
    "COMPLIANT": (60, 200, 60),
    "NON_COMPLIANT": (0, 0, 220),
    "INDETERMINATE": (0, 180, 220),
    "PARTIAL": (0, 180, 220),
    None: (150, 150, 150),
}


def _open_cv2():
    try:
        import cv2  # type: ignore
        return cv2
    except ImportError:
        sys.exit("Erro: instale as dependencias de video com `pip install opencv-python-headless numpy`.")


def build_pipeline(settings, demo_employee_seed: Optional[str]) -> RealCameraPipeline:
    vision = VisionClient(settings.vision_url)
    identity = IdentityClient(settings.identity_url)
    fusion = FusionClient(settings.fusion_url)
    rules = RulesClient(settings.rules_url)
    incident = IncidentClient(settings.incident_url, service_key=settings.incident_service_key or None)

    def seed_provider(camera_id: str, track_id: str) -> Optional[str]:
        return demo_employee_seed

    return RealCameraPipeline(
        vision, identity, fusion, rules, incident,
        process_every_n_frames=settings.process_every_n_frames,
        area=settings.area, operation=settings.operation, role=settings.role,
        identity_seed_provider=seed_provider,
        demo_ppe_override=resolve_demo_scenario_override(settings.demo_scenario),
        camera_visibility=resolve_camera_visibility(settings.blind_regions),
        use_real_images=True,
        tracker_client=TrackerClient(settings.tracker_url) if settings.tracker_url else None,
        tracker_area_id=settings.tracker_area_id or None,
        # Com identidade de demonstração, só UMA pessoa por quadro a recebe.
        single_identity_per_frame=bool(demo_employee_seed),
        send_evidence=settings.send_evidence,
    )


def _label_for(person: PersonPipelineResult, is_demo_identity: bool) -> str:
    label = person.display_identity_label
    if label != "unknown" and is_demo_identity:
        return f"{label} (DEMO IDENTITY)"
    return label


def draw_overlay(cv2, frame, results, fps, status_board, is_demo_identity):
    header_lines = [f"FPS: {fps:.1f}   Pessoas: {len(results)}"]
    header_lines.append("  ".join(f"{name.upper()}: {state}" for name, state in status_board.items()))
    y = 20
    for line in header_lines:
        cv2.rectangle(frame, (0, y - 16), (min(960, 10 * len(line)), y + 6), (30, 30, 30), -1)
        cv2.putText(frame, line, (6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (240, 240, 240), 1, cv2.LINE_AA)
        y += 26

    for person in results:
        color = STATUS_COLOR.get(person.overall_status, STATUS_COLOR[None])
        label = _label_for(person, is_demo_identity)
        lines = [f"TRACK: {person.person_track_id}", f"IDENTITY: {label}"]
        for ppe_type, data in person.ppe.items():
            lines.append(f"{ppe_type.upper()}: {data['status']} {data.get('confidence', 0):.2f}")
        lines.append(f"COMPLIANCE: {person.overall_status or '...'}")
        if person.incident_actions:
            actions = ", ".join(f"{a['action']}({a['incident_id']})" for a in person.incident_actions)
            lines.append(f"INCIDENT: {actions}")
        else:
            lines.append("INCIDENT: NONE")

        box_x, box_y = 10, y
        for line in lines:
            cv2.putText(frame, line, (box_x, box_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
            box_y += 20
        y = box_y + 12

    return frame


def open_source(cv2, source: str):
    src = int(source) if source.isdigit() else source
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        sys.exit(f"Nao foi possivel abrir a fonte: {source!r}")

    def gen():
        fails = 0
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                fails += 1
                if fails >= 30:
                    break
                continue
            fails = 0
            yield frame
        cap.release()

    return gen()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fase 3.7 - pipeline de camera real, ponta a ponta")
    parser.add_argument("--source", default="0", help="indice da webcam (0) | caminho de video | url rtsp")
    parser.add_argument("--camera-id", default=None, help="sobrescreve EPI_PIPELINE_CAMERA_ID")
    parser.add_argument("--headless", action="store_true", help="nao abre janela (usa com --save)")
    parser.add_argument("--save", default=None, help="grava um video anotado no caminho dado")
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args()

    cv2 = _open_cv2()
    settings = get_camera_pipeline_settings()
    camera_id = args.camera_id or settings.camera_id
    is_demo_identity = bool(settings.demo_employee_seed)

    pipeline = build_pipeline(settings, settings.demo_employee_seed)

    print(f"Camera: {camera_id}")
    print(f"process_every_n_frames: {settings.process_every_n_frames}")
    print(f"DEMO IDENTITY: {'ativado (' + settings.demo_employee_seed + ')' if is_demo_identity else 'desligado'}")
    print(f"DEMO_SCENARIO: {settings.demo_scenario or '(nenhum - deteccao real)'}")
    print("Pressione 'q' ou ESC na janela para sair (ou Ctrl+C no terminal em modo headless).\n")

    frames = open_source(cv2, args.source)
    writer = None
    last = time.perf_counter()
    fps = 0.0
    count = 0
    shown_results: list = []

    try:
        for raw_frame in frames:
            results = pipeline.process_frame(camera_id, raw_frame)
            # A amostragem (process_every_n_frames) pula frames: nesses, a lista
            # vem vazia sem querer dizer "ninguém na câmera". Mantém na tela o
            # último resultado real até o próximo frame processado.
            if pipeline.last_frame_processed:
                shown_results = results
            results = shown_results

            now = time.perf_counter()
            dt = now - last
            last = now
            fps = 0.9 * fps + 0.1 * (1.0 / dt) if dt > 0 else fps

            annotated = draw_overlay(cv2, raw_frame, results, fps, pipeline.status.snapshot(), is_demo_identity)

            if args.save:
                if writer is None:
                    h, w = annotated.shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    writer = cv2.VideoWriter(args.save, fourcc, 20.0, (w, h))
                writer.write(annotated)

            if not args.headless:
                cv2.imshow("EPI Vision - Fase 3.7", annotated)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break

            count += 1
            if args.max_frames and count >= args.max_frames:
                break
    except KeyboardInterrupt:
        pass
    finally:
        if writer is not None:
            writer.release()
        if not args.headless:
            cv2.destroyAllWindows()

        snap = pipeline.metrics.snapshot()
        print(f"\nEncerrado. Frames capturados: {count}. FPS final ~ {fps:.1f}")
        print(f"Frames processados pela cadeia completa: {snap['frames_processed']}")
        print(f"Pessoas detectadas: {snap['detections_total']}")
        print(f"Identificacoes MATCHED: {snap['identity_matches']}  |  nao identificados: {snap['identity_unmatched']}")
        print(f"Incidentes criados: {snap['incidents_created']}  |  resolvidos: {snap['incidents_resolved']}")
        print(f"Latencia media do pipeline: {snap['pipeline_latency_ms_avg']} ms")
        if snap["errors_by_service"]:
            print(f"Erros por servico: {snap['errors_by_service']}")


if __name__ == "__main__":
    main()
