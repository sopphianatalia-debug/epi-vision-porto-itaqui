#!/usr/bin/env python3
"""
Visualizador ao vivo do Módulo 2 (OpenCV).

Abre uma fonte de vídeo, roda a detecção + tracking + associação e mostra as
caixas com classe, confiança, track ID e FPS.

Exemplos:
    # Demo sem câmera nem YOLO (cena sintética em movimento):
    python scripts/live_view.py --source demo --provider demo

    # Webcam com modelo YOLO treinado:
    python scripts/live_view.py --source 0 --provider yolo --model seu_modelo.pt

    # Arquivo de vídeo:
    python scripts/live_view.py --source /caminho/video.mp4 --provider yolo --model seu_modelo.pt

    # Câmera RTSP:
    python scripts/live_view.py --source "rtsp://user:pass@ip:554/stream" --provider yolo --model seu_modelo.pt

    # Sem janela (servidor) — grava um vídeo anotado:
    python scripts/live_view.py --source video.mp4 --provider yolo --model m.pt --headless --save saida.mp4

Teclas na janela: 'q' ou ESC para sair.
"""
from __future__ import annotations

import argparse
import sys
import time

import numpy as np

from app.config import Settings
from app.pipeline import build_pipeline
from app.viewer import draw_results


def _open_cv2():
    try:
        import cv2  # type: ignore
        return cv2
    except ImportError:
        sys.exit("Erro: instale as dependências de vídeo com `pip install opencv-python-headless`.")


def demo_frames(cv2, width=960, height=600):
    """Gera frames em branco (fundo escuro) para o modo --source demo."""
    while True:
        canvas = np.full((height, width, 3), 32, dtype=np.uint8)
        yield canvas


def open_source(cv2, source: str):
    """Retorna um iterável de frames a partir de webcam(int)/arquivo/RTSP."""
    src = int(source) if source.isdigit() else source
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        sys.exit(f"Não foi possível abrir a fonte: {source!r}")

    def gen():
        fails = 0
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                fails += 1
                if fails >= 30:  # resiliência: encerra após muitas falhas
                    break
                continue
            fails = 0
            yield frame
        cap.release()

    return gen()


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualizador ao vivo — detecção de EPIs")
    parser.add_argument("--source", default="demo",
                        help="'demo' | índice da webcam (0) | caminho de vídeo | url rtsp")
    parser.add_argument("--provider", default="demo", choices=["demo", "yolo", "mock"])
    parser.add_argument("--model", default="yolov8n.pt", help="pesos do YOLO (se --provider yolo)")
    parser.add_argument("--camera-id", default="CAM-VIEW")
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--headless", action="store_true", help="não abre janela (usa com --save)")
    parser.add_argument("--save", default=None, help="grava um vídeo anotado no caminho dado")
    args = parser.parse_args()

    cv2 = _open_cv2()

    settings = Settings(detector_provider=args.provider, detector_model_path=args.model)
    pipeline = build_pipeline(settings)

    frames = demo_frames(cv2) if args.source == "demo" else open_source(cv2, args.source)

    writer = None
    last = time.perf_counter()
    fps = 0.0
    count = 0

    for frame in frames:
        results = pipeline.process_frame(args.camera_id, frame)

        now = time.perf_counter()
        dt = now - last
        last = now
        fps = 0.9 * fps + 0.1 * (1.0 / dt) if dt > 0 else fps

        annotated = draw_results(frame, results, fps=fps)

        if args.save:
            if writer is None:
                h, w = annotated.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(args.save, fourcc, 20.0, (w, h))
            writer.write(annotated)

        if not args.headless:
            cv2.imshow("EPI Vision - Modulo 2", annotated)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):  # q ou ESC
                break

        count += 1
        if args.max_frames and count >= args.max_frames:
            break

    if writer is not None:
        writer.release()
    if not args.headless:
        cv2.destroyAllWindows()
    print(f"Encerrado. Frames processados: {count}. FPS final ~ {fps:.1f}")


if __name__ == "__main__":
    main()
