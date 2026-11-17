"""Clientes HTTP finos para os três serviços envolvidos na Fase 3.5.

Nenhum destes clientes contém lógica de negócio — apenas serializa/chama os
endpoints REST já existentes (mais o único endpoint novo desta fase,
POST /incidents/evaluations). Toda decisão de conformidade continua nos
serviços originais.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import httpx


class ServiceClient:
    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def close(self) -> None:
        self._client.close()


class FusionClient(ServiceClient):
    def ingest(
        self,
        camera_id: str,
        person_track_id: str,
        ppe: dict[str, dict],
        employee_id: Optional[str] = None,
        identity_status: str = "MATCHED",
        identity_confidence: float = 0.95,
        timestamp: Optional[datetime] = None,
        observation_id: Optional[str] = None,
    ) -> dict:
        body = {
            "camera_id": camera_id,
            "person_track_id": person_track_id,
            "identity_status": identity_status,
            "identity_confidence": identity_confidence,
            "employee_id": employee_id,
            "ppe": ppe,
        }
        if timestamp is not None:
            body["timestamp"] = timestamp.isoformat()
        if observation_id is not None:
            body["observation_id"] = observation_id
        resp = self._client.post("/fusion/observations", json=body)
        resp.raise_for_status()
        return resp.json()

    def get_employee_state(self, employee_id: str) -> Optional[dict]:
        resp = self._client.get(f"/fusion/employees/{employee_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def set_visibility_profile(self, camera_id: str, visibility: dict[str, bool]) -> dict:
        resp = self._client.post(f"/fusion/cameras/{camera_id}/visibility", json={"visibility": visibility})
        resp.raise_for_status()
        return resp.json()

    def get_conflicts(self, limit: int = 50) -> list[dict]:
        resp = self._client.get("/fusion/conflicts", params={"limit": limit})
        resp.raise_for_status()
        return resp.json()

    def metrics(self) -> dict:
        resp = self._client.get("/fusion/metrics")
        resp.raise_for_status()
        return resp.json()

    def send_ppe_location(self, observation: dict) -> dict:
        """Envia ao Fusion a evidência de LOCALIZAÇÃO de um EPI (formato
        gerado por GET /trackers/{id}/fusion-observation do epi_tracker)."""
        resp = self._client.post("/fusion/ppe-locations", json=observation)
        resp.raise_for_status()
        return resp.json()

    def set_camera_area(self, camera_id: str, area_id: str) -> dict:
        resp = self._client.post(f"/fusion/cameras/{camera_id}/area", json={"area_id": area_id})
        resp.raise_for_status()
        return resp.json()

    def get_ppe_inconsistencies(self) -> list[dict]:
        resp = self._client.get("/fusion/ppe-inconsistencies")
        resp.raise_for_status()
        return resp.json()


class TrackerClient(ServiceClient):
    """Cliente fino do epi_tracker. Só LÊ evidência de localização — o
    tracker nunca decide conformidade."""

    def get_employee_summary(self, employee_id: str) -> dict:
        resp = self._client.get(f"/employees/{employee_id}/summary")
        resp.raise_for_status()
        return resp.json()

    def get_fusion_observation(self, tracker_id: str) -> dict:
        resp = self._client.get(f"/trackers/{tracker_id}/fusion-observation")
        resp.raise_for_status()
        return resp.json()


class RulesClient(ServiceClient):
    def evaluate(
        self,
        employee_id: Optional[str],
        ppe: dict[str, dict],
        area: Optional[str] = "PATIO_CARGA",
        operation: Optional[str] = "MOVIMENTACAO_CARGA",
        role: Optional[str] = "OPERADOR",
        identity_status: str = "MATCHED",
        evaluation_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> dict:
        body = {
            "employee_id": employee_id,
            "area": area,
            "operation": operation,
            "role": role,
            "identity_status": identity_status,
            "ppe": ppe,
        }
        if evaluation_id is not None:
            body["evaluation_id"] = evaluation_id
        if timestamp is not None:
            body["timestamp"] = timestamp.isoformat()
        resp = self._client.post("/rules/evaluate", json=body)
        resp.raise_for_status()
        return resp.json()

    def metrics(self) -> dict:
        resp = self._client.get("/rules/metrics/snapshot")
        resp.raise_for_status()
        return resp.json()


class VisionClient(ServiceClient):
    """Cliente HTTP do epi_ppe (Módulo 2 — detecção/tracking/associação de
    EPIs). Introduzido na Fase 3.7: o pipeline de câmera real trata a visão
    computacional como mais um serviço HTTP, no mesmo padrão dos outros
    quatro — nunca importa o código do módulo em processo."""

    def process_frame(self, camera_id: str, frame: dict) -> dict:
        """`frame` é o dict de cena aceito pelo provider mock/demo — ver
        epi_ppe/app/detection/providers/mock_provider.py para o formato
        exato ({"detections": [{"cls": "PERSON", "confidence": ..., "bbox":
        [...]}, ...]}). Para imagem real (provider yolo), use
        `process_frame_image`."""
        resp = self._client.post("/pipeline/process-frame", json={"camera_id": camera_id, "frame": frame})
        resp.raise_for_status()
        return resp.json()

    def process_frame_image(self, camera_id: str, image_bgr: Any, jpeg_quality: int = 85) -> dict:
        """Envia uma imagem REAL (array BGR do OpenCV) para o provider
        `yolo` — Fase 3.7. Codifica em JPEG + base64 antes de mandar, porque
        JSON não carrega bytes binários diretamente. Requer que o servidor
        do epi_ppe esteja configurado com PPE_DETECTOR_PROVIDER=yolo — mandar
        isso para um servidor mock não faz sentido (o MockDetector espera um
        dict, não uma imagem) e vai falhar do lado do servidor."""
        import base64

        import cv2  # type: ignore

        ok, buf = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
        if not ok:
            raise ValueError("Falha ao codificar o frame em JPEG.")
        frame_b64 = base64.b64encode(buf.tobytes()).decode("ascii")
        resp = self._client.post("/pipeline/process-frame", json={"camera_id": camera_id, "frame_b64": frame_b64})
        resp.raise_for_status()
        return resp.json()

    def metrics(self) -> dict:
        resp = self._client.get("/metrics")
        resp.raise_for_status()
        return resp.json()


class IncidentClient(ServiceClient):
    def process_evaluation(self, evaluation: dict) -> list[dict]:
        resp = self._client.post("/incidents/evaluations", json=evaluation)
        resp.raise_for_status()
        return resp.json()

    def get(self, incident_id: str) -> Optional[dict]:
        resp = self._client.get(f"/incidents/{incident_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def list(self, **filters) -> list[dict]:
        resp = self._client.get("/incidents", params={k: v for k, v in filters.items() if v is not None})
        resp.raise_for_status()
        return resp.json()

    def metrics(self) -> dict:
        resp = self._client.get("/incidents/metrics/snapshot")
        resp.raise_for_status()
        return resp.json()
