"""
Testes unitários do Observation Builder (Fase 3.7) — não sobem nenhum
serviço, rodam em milissegundos. Cobrem a Fricção 4 documentada em
`app/observation_builder.py` e `docs/contracts.md`.
"""
from __future__ import annotations

from app.observation_builder import build_fusion_ppe

# Payload no formato que POST /pipeline/process-frame do epi_ppe devolve por
# pessoa (schema PersonResultOut) — ver VisionClient.process_frame.
FULL_COMPLIANCE_PERSON = {
    "person_track_id": "TRACK-000017",
    "employee_id": None,
    "person_confidence": 0.97,
    "person_bbox": [100, 50, 300, 500],
    "detections": [
        {"type": "HELMET", "confidence": 0.96, "bbox": [140, 60, 260, 150]},
        {"type": "SAFETY_VEST", "confidence": 0.93, "bbox": [130, 200, 270, 340]},
        {"type": "GLOVES", "confidence": 0.90, "bbox": [110, 300, 290, 340]},
        {"type": "SAFETY_BOOTS", "confidence": 0.91, "bbox": [120, 420, 280, 495]},
    ],
}


def test_all_ppe_detected_maps_to_detected_status():
    ppe = build_fusion_ppe(FULL_COMPLIANCE_PERSON)
    assert ppe == {
        "helmet": {"status": "DETECTED", "confidence": 0.96},
        "vest": {"status": "DETECTED", "confidence": 0.93},
        "gloves": {"status": "DETECTED", "confidence": 0.90},
        "boots": {"status": "DETECTED", "confidence": 0.91},
    }


def test_class_name_translation_safety_vest_to_vest():
    """SAFETY_VEST (Módulo 2) -> vest (Fusion) — não é um simples .lower()."""
    person = {**FULL_COMPLIANCE_PERSON, "detections": [
        {"type": "SAFETY_VEST", "confidence": 0.9, "bbox": [130, 200, 270, 340]},
    ]}
    ppe = build_fusion_ppe(person)
    assert "vest" in ppe
    assert "safety_vest" not in ppe


def test_undetected_ppe_becomes_explicit_missing_not_silence():
    """Fricção 4 — a peça central desta fase: se o Módulo 2 rodou a
    detecção e não achou o EPI, isso é MISSING explícito, não silêncio
    (silêncio cairia em NOT_OBSERVED/INDETERMINATE no Fusion, e o sistema
    nunca abriria incidente por ausência real)."""
    person = {**FULL_COMPLIANCE_PERSON, "detections": [
        d for d in FULL_COMPLIANCE_PERSON["detections"] if d["type"] != "HELMET"
    ]}
    ppe = build_fusion_ppe(person)
    assert ppe["helmet"]["status"] == "MISSING"
    assert ppe["vest"]["status"] == "DETECTED"


def test_camera_that_cannot_see_region_omits_key_instead_of_missing():
    """Quando a câmera não enxerga a região (perfil de visibilidade), o
    builder OMITE a chave — quem decide NOT_VISIBLE é o Fusion, não aqui."""
    person = {**FULL_COMPLIANCE_PERSON, "detections": [
        d for d in FULL_COMPLIANCE_PERSON["detections"] if d["type"] != "SAFETY_BOOTS"
    ]}
    ppe = build_fusion_ppe(person, camera_can_see={"feet": False})
    assert "boots" not in ppe
    assert ppe["helmet"]["status"] == "DETECTED"  # demais tipos não afetados


def test_camera_that_can_see_region_but_finds_nothing_reports_missing():
    person = {**FULL_COMPLIANCE_PERSON, "detections": [
        d for d in FULL_COMPLIANCE_PERSON["detections"] if d["type"] != "SAFETY_BOOTS"
    ]}
    ppe = build_fusion_ppe(person, camera_can_see={"feet": True})
    assert ppe["boots"]["status"] == "MISSING"


def test_unknown_detection_class_is_ignored_not_a_crash():
    person = {**FULL_COMPLIANCE_PERSON, "detections": [
        {"type": "UNKNOWN_FUTURE_CLASS", "confidence": 0.9, "bbox": [0, 0, 10, 10]},
    ]}
    ppe = build_fusion_ppe(person)
    assert "unknown_future_class" not in ppe
    # Os quatro tipos rastreados continuam sendo reportados como MISSING
    # (o detector rodou; essa classe desconhecida não conta como detecção
    # de nenhum dos quatro).
    assert ppe["helmet"]["status"] == "MISSING"


def test_duplicate_detections_of_same_type_keeps_highest_confidence():
    person = {**FULL_COMPLIANCE_PERSON, "detections": [
        {"type": "HELMET", "confidence": 0.55, "bbox": [140, 60, 260, 150]},
        {"type": "HELMET", "confidence": 0.91, "bbox": [141, 61, 259, 149]},
    ]}
    ppe = build_fusion_ppe(person)
    assert ppe["helmet"]["confidence"] == 0.91


def test_optional_ppe_types_never_generate_missing_by_omission():
    """glasses/ear_protection não estão em tracked_ppe_types por padrão —
    a ausência deles nunca é reportada como MISSING (a regra padrão do
    Rules Engine não os exige; forçar MISSING geraria ruído sem sentido)."""
    ppe = build_fusion_ppe(FULL_COMPLIANCE_PERSON)
    assert "glasses" not in ppe
    assert "ear_protection" not in ppe
