"""Cadastro de câmeras (HTTP). Câmera é dado administrativo: não decide conformidade."""
from __future__ import annotations

import re
from pathlib import Path

PREFIX = "/api/v1"
BODY = {"camera_id": "CAM-GS-ENT", "name": "Entrada Granéis Sólidos", "sector": "GRANEIS_SOLIDOS",
        "kind": "ENTRADA", "pos": {"x": 14, "y": 86}}


def test_create_list_get_camera(client):
    r = client.post(f"{PREFIX}/cameras", json=BODY)
    assert r.status_code == 201
    assert r.json() == {"camera_id": "CAM-GS-ENT", "name": "Entrada Granéis Sólidos", "sector": "GRANEIS_SOLIDOS",
                        "kind": "ENTRADA", "pos": {"x": 14.0, "y": 86.0}, "active": True, "example": False}
    assert [c["camera_id"] for c in client.get(f"{PREFIX}/cameras").json()] == ["CAM-GS-ENT"]
    assert client.get(f"{PREFIX}/cameras/CAM-GS-ENT").json()["kind"] == "ENTRADA"


def test_duplicate_is_409_and_unknown_is_404(client):
    client.post(f"{PREFIX}/cameras", json=BODY)
    assert client.post(f"{PREFIX}/cameras", json=BODY).status_code == 409
    assert client.get(f"{PREFIX}/cameras/NAO-EXISTE").status_code == 404
    assert client.put(f"{PREFIX}/cameras/NAO-EXISTE", json=BODY).status_code == 404
    assert client.delete(f"{PREFIX}/cameras/NAO-EXISTE").status_code == 404


def test_sector_is_normalized_and_unknown_sector_rejected(client):
    ok = client.post(f"{PREFIX}/cameras", json={**BODY, "camera_id": "C1", "sector": " pier_bordo "})
    assert ok.status_code == 201 and ok.json()["sector"] == "PIER_BORDO"
    bad = client.post(f"{PREFIX}/cameras", json={**BODY, "camera_id": "C2", "sector": "SETOR_X"})
    assert bad.status_code == 422                      # nunca adivinhamos o setor
    none = client.post(f"{PREFIX}/cameras", json={**BODY, "camera_id": "C3", "sector": None})
    assert none.status_code == 201 and none.json()["sector"] is None   # sem setor é permitido


def test_kind_and_position_are_validated(client):
    assert client.post(f"{PREFIX}/cameras", json={**BODY, "camera_id": "C4", "kind": "TETO"}).status_code == 422
    assert client.post(f"{PREFIX}/cameras", json={**BODY, "camera_id": "C5", "pos": {"x": 120, "y": 5}}).status_code == 422
    assert client.post(f"{PREFIX}/cameras", json={**BODY, "camera_id": "C6", "pos": {"x": 5}}).status_code == 422
    assert client.post(f"{PREFIX}/cameras", json={**BODY, "camera_id": "C7", "name": "  "}).status_code == 422
    assert client.post(f"{PREFIX}/cameras", json={k: v for k, v in BODY.items() if k != "camera_id"}).status_code == 422


def test_update_changes_sector_without_code(client):
    client.post(f"{PREFIX}/cameras", json=BODY)
    r = client.put(f"{PREFIX}/cameras/CAM-GS-ENT", json={**BODY, "sector": "PIER_BORDO", "name": "Entrada Píer"})
    assert r.status_code == 200
    got = client.get(f"{PREFIX}/cameras/CAM-GS-ENT").json()
    assert got["sector"] == "PIER_BORDO" and got["name"] == "Entrada Píer"


def test_delete_camera(client):
    client.post(f"{PREFIX}/cameras", json=BODY)
    assert client.delete(f"{PREFIX}/cameras/CAM-GS-ENT").status_code == 204
    assert client.get(f"{PREFIX}/cameras").json() == []


def test_sector_codes_match_frontend_and_integration():
    from app.domain.sectors import SECTOR_CODES
    root = Path(__file__).resolve().parents[2]
    js = (root / "epi_tracker/frontend/src/config/itaqui.js").read_text()
    block = js[js.index("export const SECTORS"):]
    assert set(re.findall(r'code:\s*"([A-Z_]+)"', block)) == set(SECTOR_CODES)
    py = (root / "epi_integration/app/sectors.py").read_text()
    assert set(re.findall(r'"([A-Z_]+)",', py)) >= set(SECTOR_CODES)


# ---------------------------------------------------------------- persistência em arquivo
def _service(path):
    from app.infrastructure.clock import FakeClock
    from app.infrastructure.event_bus import InMemoryEventBus
    from app.observability.metrics import TrackerMetrics
    from app.providers.mock_provider import MockTrackerProvider
    from app.service import TrackerService
    from datetime import datetime, timezone
    return TrackerService(clock=FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc)), event_bus=InMemoryEventBus(), metrics=TrackerMetrics(),
                          location_provider=MockTrackerProvider(), cameras_file=str(path))


def test_cameras_survive_restart(tmp_path):
    f = tmp_path / "sub" / "cameras.json"
    a = _service(f)
    a.register_camera("C-1", "Entrada", "PIER_BORDO", "ENTRADA", 10, 20, example=True)
    a.register_camera("C-2", "Interna", None, "INTERNA")
    a.update_camera("C-2", "Interna 2", "GUARDA_PORTUARIA", "INTERNA", 30, 40, active=False)
    a.delete_camera("C-1")
    b = _service(f)                                   # "reiniciou"
    assert b.cameras_loaded_from_file
    cams = {c.camera_id: c.to_dict() for c in b.list_cameras()}
    assert list(cams) == ["C-2"]
    assert cams["C-2"]["name"] == "Interna 2" and cams["C-2"]["sector"] == "GUARDA_PORTUARIA"
    assert cams["C-2"]["pos"] == {"x": 30.0, "y": 40.0} and cams["C-2"]["active"] is False


def test_corrupt_file_does_not_break_service(tmp_path):
    f = tmp_path / "cameras.json"
    f.write_text("{isso não é json")
    s = _service(f)                                   # não levanta
    assert s.list_cameras() == []
    assert (tmp_path / "cameras.json.corrupt").exists()   # cópia guardada para análise
    s.register_camera("C-9", "Nova")                  # e volta a gravar normalmente
    assert [c.camera_id for c in _service(f).list_cameras()] == ["C-9"]


def test_no_file_configured_keeps_memory_only(tmp_path):
    s = _service("")                                  # vazio = só memória
    s.register_camera("C-1", "X")
    assert [c.camera_id for c in s.list_cameras()] == ["C-1"]
