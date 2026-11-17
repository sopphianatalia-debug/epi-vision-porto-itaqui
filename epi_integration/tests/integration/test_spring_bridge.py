"""Ponte Spring Boot (cadastro) -> Identity, e adaptador de detecções.

O Spring é simulado por um servidor HTTP mínimo (o contrato é o do branch
feature/fastapi-vision: GET /api/trabalhadores). O Identity é o REAL, subido
pela fixture `pipeline`.
"""
from __future__ import annotations

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.spring_client import SpringClient
from app.vision_adapter import group_to_ours, ours_to_group
from app.worker_sync import sync_workers


class FakeSpring:
    def __init__(self):
        self.workers: list[dict] = []
        self.status = 200
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                if self.path != "/api/trabalhadores":
                    self.send_response(404); self.end_headers(); return
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(outer.workers).encode())

            def log_message(self, *a):  # silencioso
                pass

        self.server = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def add(self, nome, matricula, ativo=True, empresa="Porto SA", **extra):
        w = {"id": str(uuid.uuid4()), "nome": nome,
             "matricula": matricula, "empresa": empresa, "ativo": ativo}
        w.update(extra)  # setor / cargo (opcionais)
        self.workers.append(w)
        return w

    def close(self):
        self.server.shutdown()


@pytest.fixture()
def spring():
    fake = FakeSpring()
    yield fake
    fake.close()


@pytest.fixture()
def spring_client(spring):
    c = SpringClient(spring.url)
    yield c
    c.close()


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _by_reg(identity, reg):
    return next((e for e in identity.list_employees() if e["registration"] == reg), None)


def test_creates_new_workers_in_identity(spring, spring_client, identity):
    m1, m2 = _uniq("SP"), _uniq("SP")
    spring.add("Ana Souza", m1)
    spring.add("Bruno Lima", m2)
    rep = sync_workers(spring_client, identity)
    assert {m1, m2} <= set(rep.created)
    e = _by_reg(identity, m1)
    assert e["name"] == "Ana Souza" and e["status"] == "ACTIVE"
    assert e["biometric_status"] == "NOT_ENROLLED"  # sync nunca cadastra rosto


def test_sync_is_idempotent(spring, spring_client, identity):
    m = _uniq("SP")
    spring.add("Carla Dias", m)
    sync_workers(spring_client, identity)
    count = len(identity.list_employees())
    rep = sync_workers(spring_client, identity)
    assert m in rep.unchanged and not rep.created and not rep.errors
    assert len(identity.list_employees()) == count


def test_name_change_and_deactivation_propagate(spring, spring_client, identity):
    m = _uniq("SP")
    spring.add("Davi Nunes", m)
    sync_workers(spring_client, identity)
    spring.workers[-1]["nome"] = "Davi N. Nunes"
    spring.workers[-1]["ativo"] = False
    rep = sync_workers(spring_client, identity)
    assert m in rep.updated
    e = _by_reg(identity, m)
    assert e["name"] == "Davi N. Nunes" and e["status"] == "INACTIVE"


def test_inactive_worker_is_created_inactive(spring, spring_client, identity):
    m = _uniq("SP")
    spring.add("Elisa Prado", m, ativo=False)
    sync_workers(spring_client, identity)
    assert _by_reg(identity, m)["status"] == "INACTIVE"


def test_worker_missing_in_spring_is_reported_not_deleted(spring, spring_client, identity):
    m = _uniq("SP")
    spring.add("Fabio Reis", m)
    sync_workers(spring_client, identity)
    spring.workers.clear()
    rep = sync_workers(spring_client, identity)
    assert m in rep.missing_in_spring
    assert _by_reg(identity, m) is not None  # nunca apaga


def test_does_not_touch_enrolled_biometrics(spring, spring_client, identity):
    m = _uniq("SP")
    spring.add("Gil Matos", m)
    sync_workers(spring_client, identity)
    e = _by_reg(identity, m)
    identity.enroll(e["id"], seed=e["employee_code"])
    spring.workers[-1]["nome"] = "Gil M. Matos"
    sync_workers(spring_client, identity)
    e2 = _by_reg(identity, m)
    assert e2["biometric_status"] == "ENROLLED" and e2["name"] == "Gil M. Matos"


def test_spring_down_changes_nothing(spring, spring_client, identity):
    spring.add("Hugo Alves", _uniq("SP"))
    before = len(identity.list_employees())
    spring.status = 500
    rep = sync_workers(spring_client, identity)
    assert rep.spring_reachable is False and rep.errors
    assert len(identity.list_employees()) == before


def test_spring_unreachable_port():
    c = SpringClient("http://127.0.0.1:9", timeout=0.5)
    rep = sync_workers(c, identity=None)  # identity nem chega a ser usado
    assert rep.spring_reachable is False


def test_duplicate_registration_in_spring_is_reported(spring, spring_client, identity):
    m = _uniq("SP")
    spring.add("Iara Costa", m)
    spring.add("Iara Costa (dup)", m)
    rep = sync_workers(spring_client, identity)
    assert any(m in e for e in rep.errors)
    assert _by_reg(identity, m)["name"] == "Iara Costa"


def test_adapter_group_to_ours_and_back():
    g = [{"class_id": 0, "class_name": "person", "confidence": 0.9,
          "bbox": {"x1": 1.0, "y1": 2.0, "x2": 30.0, "y2": 40.0}}]
    ours = group_to_ours(g)
    assert ours == [{"type": "person", "confidence": 0.9, "bbox": [1.0, 2.0, 30.0, 40.0]}]
    back = ours_to_group(ours)[0]
    assert back["class_name"] == "person" and back["bbox"]["x2"] == 30.0


def test_adapter_drops_unknown_class_and_bad_bbox():
    g = [{"class_name": "dog", "confidence": 0.9, "bbox": {"x1": 0, "y1": 0, "x2": 1, "y2": 1}},
         {"class_name": "person", "confidence": 0.9, "bbox": {"x1": 0}},
         {"class_name": "Safety Vest", "confidence": 0.8,
          "bbox": {"x1": 0, "y1": 0, "x2": 5, "y2": 5}}]
    out = group_to_ours(g)
    assert [d["type"] for d in out] == ["vest"]


# ---------------------------------------------------------------- setor / cargo
def test_sector_and_role_from_spring_are_used_on_create(spring, spring_client, identity):
    m = _uniq("SP")
    spring.add("Carla Dias", m, setor="GRANEIS_SOLIDOS", cargo="Operadora de correia")
    rep = sync_workers(spring_client, identity)
    assert m in rep.created and rep.unknown_sector == []
    e = _by_reg(identity, m)
    assert e["sector"] == "GRANEIS_SOLIDOS" and e["role_title"] == "Operadora de correia"


def test_sector_is_normalized_case_and_spaces(spring, spring_client, identity):
    m = _uniq("SP")
    spring.add("Davi Rocha", m, setor="  pier_bordo ")
    sync_workers(spring_client, identity)
    assert _by_reg(identity, m)["sector"] == "PIER_BORDO"


def test_missing_sector_uses_default_on_create(spring, spring_client, identity):
    m = _uniq("SP")
    spring.add("Eva Lima", m)
    sync_workers(spring_client, identity, default_sector="PATIO_CARGA", default_role="OPERADOR")
    e = _by_reg(identity, m)
    assert e["sector"] == "PATIO_CARGA" and e["role_title"] == "OPERADOR"


def test_unknown_sector_is_reported_and_never_guessed(spring, spring_client, identity):
    m = _uniq("SP")
    spring.add("Fábio Reis", m, setor="SETOR_INEXISTENTE")
    rep = sync_workers(spring_client, identity)
    assert m in rep.created
    assert rep.unknown_sector == [f"{m}: SETOR_INEXISTENTE"]
    assert rep.summary()["unknown_sector"] == 1
    assert _by_reg(identity, m)["sector"] == "PATIO_CARGA"      # padrão, não o código inválido


def test_sector_change_in_spring_updates_identity(spring, spring_client, identity):
    m = _uniq("SP")
    w = spring.add("Gil Matos", m, setor="GRANEIS_SOLIDOS")
    sync_workers(spring_client, identity)
    w["setor"] = "MANUTENCAO_ENGENHARIA"
    rep = sync_workers(spring_client, identity)
    assert m in rep.updated
    assert _by_reg(identity, m)["sector"] == "MANUTENCAO_ENGENHARIA"


def test_absent_or_unknown_sector_does_not_overwrite_existing(spring, spring_client, identity):
    m = _uniq("SP")
    w = spring.add("Hana Cruz", m, setor="GUARDA_PORTUARIA")
    sync_workers(spring_client, identity)
    w.pop("setor")                                  # Spring deixou de informar
    rep = sync_workers(spring_client, identity)
    assert m in rep.unchanged
    assert _by_reg(identity, m)["sector"] == "GUARDA_PORTUARIA"
    w["setor"] = "XYZ"                              # código inválido também não sobrescreve
    sync_workers(spring_client, identity)
    assert _by_reg(identity, m)["sector"] == "GUARDA_PORTUARIA"


def test_sector_codes_match_frontend_config():
    """Os 6 códigos do Python e do itaqui.js não podem divergir."""
    import re
    from pathlib import Path
    from app.sectors import SECTOR_CODES
    js = (Path(__file__).resolve().parents[3] / "epi_tracker/frontend/src/config/itaqui.js").read_text()
    block = js[js.index("export const SECTORS"):js.index("export function sectorByCode")]
    assert set(re.findall(r'code:\s*"([A-Z_]+)"', block)) == set(SECTOR_CODES)
