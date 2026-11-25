"""Imagem real de rosto: validação do payload, fluxo cadastro -> reconhecimento -> apagar.

Não usa o modelo InsightFace (pesado e precisa de rosto real): um provider de teste decodifica a mesma imagem
pelo mesmo `decode_image` e gera um vetor determinístico. O que se testa aqui é o encanamento (validação,
filtro por versão do modelo, consentimento, apagar), não a qualidade do modelo.
"""
import base64
import struct

import cv2
import numpy as np
import pytest

from app.api.deps import get_recognition_service
from app.main import app
from app.recognition import FaceRecognitionService
from app.recognition.base import FaceRecognitionProvider
from app.recognition.image import InvalidImageError, decode_image
from app.recognition.matching import MatchingEngine
from app.recognition.quality import QualityGate
from app.recognition.types import BoundingBox, DetectedFace, FaceEmbedding, FaceQuality
from tests.conftest import auth_header  # noqa: F401
from tests.test_api import PREFIX, _create_employee, _frame


def _pattern(seed: int, noise: float = 0.0) -> np.ndarray:
    """Imagem 200x200 com estrutura própria (8x8 aleatório ampliado), para o vetor de teste distinguir 'pessoas'."""
    rng = np.random.default_rng(seed)
    small = rng.integers(0, 255, (8, 8), dtype=np.uint8)
    img = cv2.resize(small, (200, 200), interpolation=cv2.INTER_NEAREST)
    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR).astype(np.float32)
    if noise:
        img += np.random.default_rng(seed + 999).normal(0, noise, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def _payload(img: np.ndarray, fmt: str = ".jpg") -> dict:
    ok, buf = cv2.imencode(fmt, img)
    assert ok
    return {"image_base64": base64.b64encode(buf.tobytes()).decode()}


class _StubImageProvider(FaceRecognitionProvider):
    model_version = "stub-img-v1"
    embedding_dim = 64

    def _vec(self, frame) -> tuple[float, ...]:
        img = decode_image(frame)
        g = cv2.cvtColor(cv2.resize(img, (8, 8), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float64)
        v = (g - g.mean()).ravel()
        return tuple(float(x) for x in v / (np.linalg.norm(v) or 1.0))

    def detect_faces(self, frame):
        decode_image(frame)     # levanta InvalidImageError se a imagem for inválida
        return [DetectedFace(BoundingBox(0, 0, 200, 200), FaceQuality(score=0.9))]

    def assess_quality(self, frame, face):
        return face.quality

    def generate_embedding(self, frame, face):
        return FaceEmbedding(self._vec(frame), self.model_version, 0.9)


@pytest.fixture
def image_service():
    svc = FaceRecognitionService(_StubImageProvider(), QualityGate(0.6), MatchingEngine(0.55, 0.8, 0.05))
    app.dependency_overrides[get_recognition_service] = lambda: svc
    yield svc
    app.dependency_overrides.pop(get_recognition_service, None)


# ------------------------------------------------------------------ validação do payload
def test_decode_accepts_jpeg_and_png():
    for fmt in (".jpg", ".png"):
        assert decode_image(_payload(_pattern(1), fmt)).shape == (200, 200, 3)


@pytest.mark.parametrize("payload,why", [
    ({}, "ausente"),
    ({"image_base64": ""}, "vazio"),
    ({"image_base64": "isso não é base64!!"}, "base64"),
    ({"image_base64": base64.b64encode(b"texto qualquer, nao e imagem").decode()}, "formato"),
    ({"image_base64": base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 40).decode()}, "jpeg sem dimensões"),
])
def test_decode_rejects_bad_payloads(payload, why):
    with pytest.raises(InvalidImageError):
        decode_image(payload)


def test_decode_rejects_huge_dimensions_from_header_without_decoding():
    # PNG minúsculo em bytes que declara 20000x20000 pixels: tem que ser barrado pelo cabeçalho.
    header = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 20000, 20000) + b"\x08\x02\x00\x00\x00"
    with pytest.raises(InvalidImageError):
        decode_image({"image_base64": base64.b64encode(header + b"\x00" * 32).decode()})


def test_decode_rejects_tiny_and_oversized_bytes():
    with pytest.raises(InvalidImageError):
        decode_image(_payload(np.zeros((10, 10, 3), np.uint8)))
    with pytest.raises(InvalidImageError):
        decode_image({"image_base64": "A" * 3_000_000})


# ------------------------------------------------------------------ fluxo pela API
async def _enroll(client, header, emp, img, consent=True):
    return await client.post(f"{PREFIX}/employees/{emp['id']}/biometric-enrollment", headers=header,
                             json={"frame": _payload(img), "consent": consent})


async def _match(client, header, frame):
    return await client.post(f"{PREFIX}/recognition/match", headers=header,
                             json={"camera_id": "CAM-1", "person_track_id": "T1", "frame": frame})


@pytest.mark.asyncio
async def test_enroll_then_recognize_with_real_image_payload(client, sm_header, image_service):
    emp = await _create_employee(client, sm_header)
    assert (await _enroll(client, sm_header, emp, _pattern(1))).status_code == 200

    same = await _match(client, sm_header, _payload(_pattern(1, noise=6)))      # mesma "pessoa", outra foto
    assert same.status_code == 200 and same.json()["status"] == "MATCHED"
    assert same.json()["employee_id"] == emp["employee_code"]

    other = await _match(client, sm_header, _payload(_pattern(2)))              # outra pessoa
    assert other.json()["status"] == "UNKNOWN" and other.json()["employee_id"] is None


@pytest.mark.asyncio
async def test_enrollment_requires_consent_even_with_image(client, sm_header, image_service):
    emp = await _create_employee(client, sm_header)
    assert (await _enroll(client, sm_header, emp, _pattern(1), consent=False)).status_code == 412


@pytest.mark.asyncio
async def test_invalid_image_never_crashes(client, sm_header, image_service):
    emp = await _create_employee(client, sm_header)
    bad = {"image_base64": base64.b64encode(b"nao sou imagem").decode()}
    enroll = await client.post(f"{PREFIX}/employees/{emp['id']}/biometric-enrollment", headers=sm_header,
                               json={"frame": bad, "consent": True})
    assert enroll.status_code == 422 and "invalid_image" in str(enroll.json())
    match = await _match(client, sm_header, bad)
    assert match.status_code == 200 and match.json()["status"] == "UNAVAILABLE"      # não é "não identificado" nem erro 500


@pytest.mark.asyncio
async def test_gallery_only_uses_templates_from_the_current_model(client, sm_header, image_service):
    """Cadastro feito com o modelo de demonstração (seed) não pode entrar na comparação do modelo de imagem."""
    emp = await _create_employee(client, sm_header)
    app.dependency_overrides.pop(get_recognition_service, None)                 # volta ao provider mock
    demo = await client.post(f"{PREFIX}/employees/{emp['id']}/biometric-enrollment", headers=sm_header,
                             json={"frame": _frame(emp["employee_code"]), "consent": True})
    assert demo.status_code == 200
    app.dependency_overrides[get_recognition_service] = lambda: image_service   # agora o modelo "real"
    res = await _match(client, sm_header, _payload(_pattern(1)))
    assert res.status_code == 200 and res.json()["status"] == "UNKNOWN"         # galeria vazia para este modelo; sem erro


@pytest.mark.asyncio
async def test_revoke_deletes_template_and_stops_recognition(client, sm_header, image_service):
    emp = await _create_employee(client, sm_header)
    await _enroll(client, sm_header, emp, _pattern(1))
    assert (await _match(client, sm_header, _payload(_pattern(1)))).json()["status"] == "MATCHED"

    gone = await client.delete(f"{PREFIX}/employees/{emp['id']}/biometric", headers=sm_header)
    assert gone.status_code == 204
    st = (await client.get(f"{PREFIX}/employees/{emp['id']}/biometric-status", headers=sm_header)).json()
    assert st["biometric_status"] == "REVOKED" and st["enrolled_at"] is None
    assert (await _match(client, sm_header, _payload(_pattern(1)))).json()["status"] == "UNKNOWN"
    assert (await client.delete(f"{PREFIX}/employees/{emp['id']}/biometric", headers=sm_header)).status_code == 204   # idempotente
    # consentimento retirado: para recadastrar, é preciso consentir de novo
    assert (await _enroll(client, sm_header, emp, _pattern(1), consent=False)).status_code == 412


@pytest.mark.asyncio
async def test_revoke_requires_permission_and_existing_employee(client, sm_header, viewer_header, image_service):
    emp = await _create_employee(client, sm_header)
    assert (await client.delete(f"{PREFIX}/employees/{emp['id']}/biometric", headers=viewer_header)).status_code == 403
    assert (await client.delete(f"{PREFIX}/employees/nao-existe/biometric", headers=sm_header)).status_code == 404
