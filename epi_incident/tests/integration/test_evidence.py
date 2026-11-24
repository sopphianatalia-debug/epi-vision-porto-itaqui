"""Evidência em imagem: só recorte, só com login, prazos 30/7 dias, acesso por perfil e trilha de acesso."""
import base64
import struct
import zlib
from datetime import timedelta

import pytest

from app.api.deps import get_evidence, get_service
from app.config import get_settings
from app.evidence import EvidenceService, EvidenceStore
from app.main import app
from tests.conftest import PREFIX
from tests.integration.test_api import _body
from tests.integration.test_auth_mode import SECRET, tok


def png(w=40, h=60):
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\x80" * (w * 3) for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def b64(b):
    return base64.b64encode(b).decode()


DET = [{"label": "helmet", "status": "MISSING", "bbox": [0.2, 0.0, 0.3, 0.2], "confidence": 0.9}]


@pytest.fixture
def ev(client, monkeypatch, tmp_path):
    s = get_settings()
    monkeypatch.setattr(s, "auth_mode", "required")
    monkeypatch.setattr(s, "jwt_secret", SECRET)
    monkeypatch.setattr(s, "evidence_dir", str(tmp_path / "ev"))
    svc = EvidenceService(s, EvidenceStore(s.evidence_dir, ":memory:"))
    app.dependency_overrides[get_evidence] = lambda: svc
    yield client, svc
    app.dependency_overrides.pop(get_evidence, None)


def _inc(client, emp="FUNC-001"):
    return client.post(f"{PREFIX}/incidents", json=_body(employee_id=emp, evaluation_id="E-" + emp)).json()["incident_id"]


def _up(client, iid, data=None, det=DET):
    return client.post(f"{PREFIX}/incidents/{iid}/evidence", json={"image_base64": b64(data or png()), "detections": det})


def test_disabled_without_login_or_dir(client):
    iid = _inc(client)
    assert _up(client, iid).status_code == 503


def test_upload_then_operator_views_pending_and_log_records_it(ev):
    client, _ = ev
    iid = _inc(client)
    r = _up(client, iid)
    assert r.status_code == 201, r.text
    eid = r.json()["evidence_id"]
    assert r.json()["width"] == 40 and "filename" not in r.json()
    lst = client.get(f"{PREFIX}/incidents/{iid}/evidence", headers=tok("op", "OPERADOR")).json()
    assert lst[0]["detections"][0]["label"] == "helmet"
    img = client.get(f"{PREFIX}/incidents/{iid}/evidence/{eid}/image", headers=tok("op", "OPERADOR"))
    assert img.status_code == 200 and img.headers["cache-control"] == "private, no-store"
    assert img.content == png()
    log = client.get(f"{PREFIX}/incidents/{iid}/evidence-access-log", headers=tok("sup", "SUPERVISOR")).json()
    assert [(e["action"], e["username"]) for e in log] == [("UPLOAD", "service"), ("VIEW", "op")]


def test_image_requires_login(ev):
    client, _ = ev
    iid = _inc(client)
    eid = _up(client, iid).json()["evidence_id"]
    assert client.get(f"{PREFIX}/incidents/{iid}/evidence/{eid}/image").status_code == 401


def test_rejects_non_images_oversize_and_bad_boxes(ev):
    client, _ = ev
    iid = _inc(client)
    assert _up(client, iid, b"GIF89a-not-allowed" * 3).status_code == 422
    assert _up(client, iid, png(2000, 10)).status_code == 422
    assert _up(client, iid, det=[{"label": "x", "bbox": [0.9, 0, 0.5, 0.5]}]).status_code == 422
    r = client.post(f"{PREFIX}/incidents/{iid}/evidence", json={"image_base64": "@@@@@@@@@"})
    assert r.status_code == 422


def test_limit_per_incident(ev):
    client, _ = ev
    iid = _inc(client)
    for _i in range(3):
        assert _up(client, iid).status_code == 201
    assert _up(client, iid).status_code == 422


def test_operator_blocked_after_other_reviews_supervisor_always_sees(ev):
    client, _ = ev
    iid = _inc(client)
    eid = _up(client, iid).json()["evidence_id"]
    client.post(f"{PREFIX}/incidents/{iid}/review", json={"decision": "CONFIRMED", "note": "ok ok ok"}, headers=tok("sup", "SUPERVISOR"))
    assert client.get(f"{PREFIX}/incidents/{iid}/evidence", headers=tok("op", "OPERADOR")).status_code == 403
    assert client.get(f"{PREFIX}/incidents/{iid}/evidence/{eid}/image", headers=tok("sup", "SUPERVISOR")).status_code == 200


def test_retention_30_days_and_7_when_dismissed(ev):
    client, svc = ev
    a, b, c = _inc(client, "FUNC-A"), _inc(client, "FUNC-B"), _inc(client, "FUNC-C")
    ids = {k: _up(client, k).json()["evidence_id"] for k in (a, b, c)}
    sup = tok("sup", "SUPERVISOR")
    client.post(f"{PREFIX}/incidents/{b}/review", json={"decision": "DISMISSED", "note": "falso alarme"}, headers=sup)
    client.post(f"{PREFIX}/incidents/{c}/review", json={"decision": "CONFIRMED", "note": "confirmado ok"}, headers=sup)
    isvc = get_service()
    now = isvc.now()
    assert svc.purge_expired(isvc.get, now + timedelta(days=6)) == 0
    assert svc.purge_expired(isvc.get, now + timedelta(days=8)) == 1      # só a descartada
    assert client.get(f"{PREFIX}/incidents/{b}/evidence/{ids[b]}/image", headers=sup).status_code == 410
    assert client.get(f"{PREFIX}/incidents/{c}/evidence/{ids[c]}/image", headers=sup).status_code == 200
    assert svc.purge_expired(isvc.get, now + timedelta(days=31)) == 2     # confirmada + sem revisão
    log = client.get(f"{PREFIX}/incidents/{b}/evidence-access-log", headers=sup).json()
    assert log[-1]["action"] == "PURGE"


def test_supervisor_delete_and_operator_cannot(ev):
    client, _ = ev
    iid = _inc(client)
    eid = _up(client, iid).json()["evidence_id"]
    url = f"{PREFIX}/incidents/{iid}/evidence/{eid}"
    assert client.delete(url, headers=tok("op", "OPERADOR")).status_code == 403
    assert client.delete(url, headers=tok("sup", "SUPERVISOR")).status_code == 204
    assert client.get(url + "/image", headers=tok("sup", "SUPERVISOR")).status_code == 410
    assert client.get(f"{PREFIX}/incidents/{iid}/evidence-access-log", headers=tok("op", "OPERADOR")).status_code == 403
    assert client.post(f"{PREFIX}/evidence/purge", headers=tok("op", "OPERADOR")).status_code == 403
