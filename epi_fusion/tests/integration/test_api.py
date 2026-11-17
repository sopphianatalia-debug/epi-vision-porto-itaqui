from tests.conftest import PREFIX


def _obs(camera, track, employee=None, ppe=None, identity="MATCHED", conf=0.97):
    return {
        "camera_id": camera, "person_track_id": track,
        "identity_status": identity, "identity_confidence": conf,
        "employee_id": employee, "ppe": ppe or {},
    }


def test_api_ingest_and_state(client):
    client.post(f"{PREFIX}/fusion/observations",
                json=_obs("CAM-01", "TRACK-001", "FUNC-000234",
                          {"helmet": {"status": "DETECTED", "confidence": 0.95}}))
    client.post(f"{PREFIX}/fusion/observations",
                json=_obs("CAM-07", "TRACK-083", "FUNC-000234",
                          {"boots": {"status": "DETECTED", "confidence": 0.93}}))
    r = client.get(f"{PREFIX}/fusion/employees/FUNC-000234")
    assert r.status_code == 200
    body = r.json()
    assert body["ppe"]["helmet"]["status"] == "DETECTED"
    assert body["ppe"]["boots"]["status"] == "DETECTED"


def test_api_anonymous_when_no_employee(client):
    r = client.post(f"{PREFIX}/fusion/observations",
                    json=_obs("CAM-07", "TRACK-900", employee=None,
                              ppe={"boots": {"status": "DETECTED", "confidence": 0.94}}))
    assert r.status_code == 200
    assert r.json()["employee_id"] is None
    assert client.get(f"{PREFIX}/fusion/anonymous").status_code == 200


def test_api_visibility_profile_roundtrip(client):
    r = client.post(f"{PREFIX}/fusion/cameras/CAM-07/visibility",
                    json={"visibility": {"face": False, "head": False, "torso": False,
                                          "hands": False, "feet": True}})
    assert r.status_code == 200
    got = client.get(f"{PREFIX}/fusion/cameras/CAM-07/visibility").json()
    assert got["visibility"]["feet"] is True
    assert got["visibility"]["head"] is False


def test_api_metrics_and_state_endpoints(client):
    client.post(f"{PREFIX}/fusion/observations",
                json=_obs("CAM-01", "T1", "FUNC-000111",
                          {"helmet": {"status": "DETECTED", "confidence": 0.9}}))
    assert client.get(f"{PREFIX}/fusion/state").status_code == 200
    m = client.get(f"{PREFIX}/fusion/metrics").json()
    assert m["observations_total"] >= 1


def test_security_unknown_employee_stays_anonymous(client):
    # Identidade fraca (confiança baixa) não deve virar chave de junção.
    r = client.post(f"{PREFIX}/fusion/observations",
                    json=_obs("CAM-SEC-A", "SEC-A1", "FUNC-000234",
                              {"helmet": {"status": "DETECTED", "confidence": 0.9}},
                              conf=0.3))  # identidade fraca
    assert r.json()["employee_id"] is None  # não atribui com identidade fraca


def test_security_malformed_employee_id_not_joined(client):
    r = client.post(f"{PREFIX}/fusion/observations",
                    json=_obs("CAM-SEC-B", "SEC-B1", "EMPLOYEE-XYZ",  # formato inválido
                              {"helmet": {"status": "DETECTED", "confidence": 0.9}}))
    assert r.json()["employee_id"] is None
