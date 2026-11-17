from app.enums import ComplianceStatus, PPEStatus
from app.rules import ComplianceRulesEngine
from app.temporal import TemporalAggregator
from app.types import ComplianceResult, FrameAssessment, PPEResult
from tests.conftest import default_settings


def fa(status, conf=0.9):
    return FrameAssessment(status, conf)


def test_temporal_builds_high_confidence_after_consistent_frames():
    s = default_settings(temporal_window=4, temporal_min_frames=3, confidence_threshold=0.6)
    agg = TemporalAggregator(s)
    result = None
    for _ in range(4):
        result = agg.push("T1", "helmet", fa(PPEStatus.PROPER, 0.95))
    assert result.status == PPEStatus.PROPER
    assert result.note == "HIGH_CONFIDENCE_PROPER_USE"


def test_temporal_low_confidence_becomes_unknown():
    s = default_settings(temporal_min_frames=3, confidence_threshold=0.9)
    agg = TemporalAggregator(s)
    r = agg.push("T1", "vest", fa(PPEStatus.PROPER, 0.4))  # janela rasa + conf baixa
    assert r.status == PPEStatus.UNKNOWN


def test_temporal_not_visible_stays_not_visible():
    s = default_settings(confidence_threshold=0.9)
    agg = TemporalAggregator(s)
    r = agg.push("T1", "boots", fa(PPEStatus.NOT_VISIBLE, 0.9))
    assert r.status == PPEStatus.NOT_VISIBLE  # nunca vira UNKNOWN


def _result(**over):
    base = dict(
        person_track_id="T1", employee_id="FUNC-1", camera_id="CAM", timestamp="2026-01-01T00:00:00",
        helmet=PPEResult(PPEStatus.PROPER, 0.9), vest=PPEResult(PPEStatus.PROPER, 0.9),
        glove_left=PPEResult(PPEStatus.PROPER, 0.9), glove_right=PPEResult(PPEStatus.PROPER, 0.9),
        glasses=PPEResult(PPEStatus.NOT_VISIBLE, 0.9), boots=PPEResult(PPEStatus.PROPER, 0.9),
        overall=ComplianceStatus.UNDETERMINED,
    )
    base.update(over)
    return ComplianceResult(**base)


def test_rules_all_proper_is_compliant():
    engine = ComplianceRulesEngine(["helmet", "vest", "gloves", "boots"])
    assert engine.evaluate(_result()) == ComplianceStatus.COMPLIANT


def test_rules_right_glove_missing_is_partial():
    # Exemplo do spec: capacete/colete/luva esq. PROPER, luva dir. MISSING.
    engine = ComplianceRulesEngine(["helmet", "vest", "gloves", "boots"])
    r = _result(glove_right=PPEResult(PPEStatus.MISSING, 0.8))
    assert engine.evaluate(r) == ComplianceStatus.PARTIAL_NON_COMPLIANCE


def test_rules_undetermined_when_required_not_visible():
    engine = ComplianceRulesEngine(["helmet", "vest", "gloves", "boots"])
    r = _result(boots=PPEResult(PPEStatus.NOT_VISIBLE, 0.9))
    assert engine.evaluate(r) == ComplianceStatus.UNDETERMINED


def test_rules_all_missing_is_non_compliant():
    engine = ComplianceRulesEngine(["helmet", "vest", "boots"])
    r = _result(
        helmet=PPEResult(PPEStatus.MISSING, 0.8),
        vest=PPEResult(PPEStatus.MISSING, 0.8),
        boots=PPEResult(PPEStatus.MISSING, 0.8),
    )
    assert engine.evaluate(r) == ComplianceStatus.NON_COMPLIANT
