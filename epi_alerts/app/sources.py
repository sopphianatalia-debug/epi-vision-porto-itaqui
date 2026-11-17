"""Fontes de condições. Só LEEM serviços já existentes e traduzem o que eles
já decidiram — nenhuma regra de conformidade vive aqui."""
from __future__ import annotations

from typing import Any, Protocol

import httpx

from app.domain import AlertType, Condition, Severity


class JsonGetter(Protocol):
    def get(self, url: str) -> Any: ...


class HttpJson:
    def __init__(self, timeout: float = 2.0) -> None:
        self._client = httpx.Client(timeout=timeout)

    def get(self, url: str) -> Any:
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp.json()


_INCIDENT_SEVERITY = {
    "CRITICAL": Severity.CRITICAL, "HIGH": Severity.CRITICAL,
    "MEDIUM": Severity.WARNING, "LOW": Severity.INFO, "INFO": Severity.INFO,
}
_PPE_PT = {"helmet": "capacete", "vest": "colete", "gloves": "luvas", "boots": "botas",
           "glasses": "óculos", "goggles": "óculos"}


def _ppe(name: str | None) -> str:
    return _PPE_PT.get((name or "").lower(), name or "EPI")


class TrackerSource:
    name = "tracker"

    def __init__(self, http: JsonGetter, base_url: str) -> None:
        self._http, self._base = http, base_url.rstrip("/")

    def collect(self) -> list[Condition]:
        out: list[Condition] = []
        for t in self._http.get(f"{self._base}/trackers"):
            tid, status = t["tracker_id"], t.get("status")
            ent = {"tracker_id": tid, "area_id": t.get("last_area_id")}
            if status == "OFFLINE":
                out.append(Condition(f"tracker_offline:{tid}", self.name, AlertType.TRACKER_OFFLINE,
                                     Severity.WARNING, "Rastreador offline",
                                     f"O rastreador {tid} está offline.", ent))
            elif status == "LOW_BATTERY":
                out.append(Condition(f"tracker_low_battery:{tid}", self.name, AlertType.TRACKER_LOW_BATTERY,
                                     Severity.WARNING, "Bateria baixa",
                                     f"O rastreador {tid} está com bateria baixa.", ent))
            elif status == "ACTIVE":
                loc = self._http.get(f"{self._base}/trackers/{tid}/location")
                if loc.get("state") == "EXPIRED":
                    out.append(Condition(f"tracker_location_expired:{tid}", self.name,
                                         AlertType.TRACKER_LOCATION_EXPIRED, Severity.INFO,
                                         "Localização expirada",
                                         f"O rastreador {tid} não informa localização recente; "
                                         "a posição anterior não deve ser considerada atual.", ent))
        return out


class FusionSource:
    name = "fusion"

    def __init__(self, http: JsonGetter, base_url: str) -> None:
        self._http, self._base = http, base_url.rstrip("/")

    def collect(self) -> list[Condition]:
        out = []
        for i in self._http.get(f"{self._base}/fusion/ppe-inconsistencies"):
            key = f"ppe_inconsistency:{i['employee_id']}:{i.get('ppe_id')}:{i.get('camera_id')}"
            out.append(Condition(
                key, self.name, AlertType.PPE_LOCATION_INCONSISTENCY, Severity.WARNING,
                "Possível inconsistência de localização do EPI",
                f"A câmera viu o {_ppe(i.get('ppe_type'))} em {i.get('camera_area_id')}, mas o rastreador "
                f"informa {i.get('tracker_area_id')}. Isso não indica, por si só, violação.",
                {"employee_id": i["employee_id"], "ppe_id": i.get("ppe_id"),
                 "tracker_id": i.get("tracker_id"), "camera_id": i.get("camera_id")},
            ))
        return out


class IncidentSource:
    name = "incident"

    def __init__(self, http: JsonGetter, base_url: str) -> None:
        self._http, self._base = http, base_url.rstrip("/")

    def collect(self) -> list[Condition]:
        out = []
        for inc in self._http.get(f"{self._base}/incidents?status=OPEN"):
            out.append(Condition(
                f"incident:{inc['incident_id']}", self.name, AlertType.INCIDENT_OPEN,
                _INCIDENT_SEVERITY.get(str(inc.get("severity", "")).upper(), Severity.WARNING),
                "Incidente aberto",
                f"{inc.get('employee_id')}: {inc.get('reason') or _ppe(inc.get('ppe_type'))}",
                {"employee_id": inc.get("employee_id"), "incident_id": inc["incident_id"],
                 "ppe_type": inc.get("ppe_type"), "cameras": inc.get("source_cameras", [])},
            ))
        return out
