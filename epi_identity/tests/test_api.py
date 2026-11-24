import pytest

from app.enums import Role
from tests.conftest import auth_header

PREFIX = "/api/v1"


def _frame(seed="FUNC-000001", quality=0.95):
    return {"faces": [{"bbox": [0, 0, 100, 100], "seed": seed, "quality": quality,
                       "single_face": True, "face_visible": True}]}


async def _create_employee(client, header, name="João Silva"):
    resp = await client.post(
        f"{PREFIX}/employees",
        headers=header,
        json={"registration": "0001", "name": name, "sector": "Pátio", "role_title": "Operador"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_employee_code_is_generated_not_name(client, sm_header):
    emp = await _create_employee(client, sm_header)
    assert emp["employee_code"].startswith("FUNC-")
    assert emp["biometric_status"] == "NOT_ENROLLED"


@pytest.mark.asyncio
async def test_enrollment_requires_consent(client, sm_header):
    emp = await _create_employee(client, sm_header)
    resp = await client.post(
        f"{PREFIX}/employees/{emp['id']}/biometric-enrollment",
        headers=sm_header,
        json={"frame": _frame(emp["employee_code"]), "consent": False},
    )
    assert resp.status_code == 412  # Precondition Failed (LGPD)


@pytest.mark.asyncio
async def test_enrollment_rejects_low_quality(client, sm_header):
    emp = await _create_employee(client, sm_header)
    resp = await client.post(
        f"{PREFIX}/employees/{emp['id']}/biometric-enrollment",
        headers=sm_header,
        json={"frame": _frame(emp["employee_code"], quality=0.2), "consent": True},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "IDENTIFICATION_UNAVAILABLE"


@pytest.mark.asyncio
async def test_full_flow_enroll_then_match(client, sm_header):
    emp = await _create_employee(client, sm_header)
    code = emp["employee_code"]

    enroll = await client.post(
        f"{PREFIX}/employees/{emp['id']}/biometric-enrollment",
        headers=sm_header,
        json={"frame": _frame(code), "consent": True},
    )
    assert enroll.status_code == 200
    assert enroll.json()["biometric_status"] == "ENROLLED"

    match = await client.post(
        f"{PREFIX}/recognition/match",
        headers=sm_header,
        json={"camera_id": "CAM-07", "person_track_id": "CAM07_PERSON_00127", "frame": _frame(code)},
    )
    assert match.status_code == 200, match.text
    body = match.json()
    assert body["status"] == "MATCHED"
    assert body["employee_id"] == code
    assert body["person_track_id"] == "CAM07_PERSON_00127"


@pytest.mark.asyncio
async def test_match_unknown_when_not_enrolled(client, sm_header):
    await _create_employee(client, sm_header)  # existe mas sem biometria
    match = await client.post(
        f"{PREFIX}/recognition/match",
        headers=sm_header,
        json={"camera_id": "CAM-01", "frame": _frame("ALGUEM-DESCONHECIDO")},
    )
    assert match.status_code == 200
    assert match.json()["status"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_human_review_overrides_ai(client, sm_header):
    emp = await _create_employee(client, sm_header)
    code = emp["employee_code"]
    await client.post(
        f"{PREFIX}/employees/{emp['id']}/biometric-enrollment",
        headers=sm_header,
        json={"frame": _frame(code), "consent": True},
    )
    match = await client.post(
        f"{PREFIX}/recognition/match",
        headers=sm_header,
        json={"camera_id": "CAM-07", "frame": _frame("DESCONHECIDO")},
    )
    event_id = match.json()["event_id"]

    review = await client.post(
        f"{PREFIX}/recognition/review",
        headers=sm_header,
        json={"event_id": event_id, "decision": "CONFIRM", "final_employee_code": code},
    )
    assert review.status_code == 200
    assert review.json()["final_employee_code"] == code


@pytest.mark.asyncio
async def test_rbac_viewer_cannot_write_or_enroll(client, viewer_header, sm_header):
    # VIEWER não pode criar funcionário.
    resp = await client.post(
        f"{PREFIX}/employees",
        headers=viewer_header,
        json={"registration": "9", "name": "X", "sector": "S", "role_title": "R"},
    )
    assert resp.status_code == 403

    # VIEWER não pode fazer enrollment.
    emp = await _create_employee(client, sm_header)
    resp = await client.post(
        f"{PREFIX}/employees/{emp['id']}/biometric-enrollment",
        headers=viewer_header,
        json={"frame": _frame(), "consent": True},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_operator_cannot_review(client):
    header = auth_header(Role.OPERATOR)
    resp = await client.post(
        f"{PREFIX}/recognition/review",
        headers=header,
        json={"event_id": "nao-existe", "decision": "CONFIRM"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_is_rejected(client):
    resp = await client.get(f"{PREFIX}/employees")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_lookup_by_employee_code(client, sm_header):
    emp = await _create_employee(client, sm_header, name="Maria Souza")
    ok = await client.get(f"{PREFIX}/employees/by-code/{emp['employee_code']}", headers=sm_header)
    assert ok.status_code == 200 and ok.json()["name"] == "Maria Souza" and ok.json()["sector"] == "Pátio"
    missing = await client.get(f"{PREFIX}/employees/by-code/FUNC-999999", headers=sm_header)
    assert missing.status_code == 404
