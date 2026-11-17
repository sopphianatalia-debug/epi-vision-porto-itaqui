"""A interface web (outra porta) precisa conseguir LER as câmeras do Fusion."""
from fastapi.testclient import TestClient

from app.main import app


def test_cors_permite_leitura_da_interface():
    c = TestClient(app)
    r = c.get("/api/v1/fusion/cameras/health", headers={"Origin": "http://127.0.0.1:8020"})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") in ("*", "http://127.0.0.1:8020")


def test_cors_preflight():
    c = TestClient(app)
    r = c.options("/api/v1/fusion/state", headers={
        "Origin": "http://127.0.0.1:8020", "Access-Control-Request-Method": "GET"})
    assert r.status_code == 200
