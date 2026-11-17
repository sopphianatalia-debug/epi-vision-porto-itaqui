"""Testes unitários da observabilidade de saúde por câmera (extensão da Fase 3.1)."""
from app.observability.metrics import FusionMetrics


def feed(m: FusionMetrics, camera, n, matches=0, confidences=None, not_visible=0):
    """Injeta `n` observações numa câmera com um perfil de sinais controlado."""
    confidences = confidences or []
    for i in range(n):
        matched = i < matches
        conf = confidences[i] if i < len(confidences) else None
        nv = i < not_visible
        m.record_observation(camera, latency_ms=1.0, matched=matched,
                             employee_id=("FUNC-1" if matched else None),
                             confidence=conf, not_visible=nv)


def by_id(rows):
    return {r["camera_id"]: r for r in rows}


def test_aggregation_counts_observations_per_camera():
    m = FusionMetrics()
    feed(m, "CAM-01", 10, matches=10)
    feed(m, "CAM-02", 4, matches=1)
    h = by_id(m.camera_health())
    assert h["CAM-01"]["observations"] == 10
    assert h["CAM-02"]["observations"] == 4


def test_two_cameras_with_different_volumes_kept_separate():
    m = FusionMetrics()
    feed(m, "CAM-01", 100, matches=90)
    feed(m, "CAM-02", 5, matches=5)
    h = by_id(m.camera_health())
    assert h["CAM-01"]["observations"] == 100
    assert h["CAM-02"]["observations"] == 5


def test_identity_match_rate():
    m = FusionMetrics()
    feed(m, "CAM-01", 200, matches=100)
    assert by_id(m.camera_health())["CAM-01"]["identity_match_rate"] == 0.5


def test_anonymous_counts():
    m = FusionMetrics()
    feed(m, "CAM-01", 10, matches=3)
    row = by_id(m.camera_health())["CAM-01"]
    assert row["anonymous"] == 7
    assert row["identity_matches"] == 3


def test_conflicts_attributed_per_camera():
    m = FusionMetrics()
    feed(m, "CAM-01", 5, matches=5)
    feed(m, "CAM-02", 5, matches=5)
    m.record_conflict({"CAM-01", "CAM-02"})  # ambas participaram
    m.record_conflict({"CAM-01"})            # só CAM-01
    h = by_id(m.camera_health())
    assert h["CAM-01"]["conflicts"] == 2
    assert h["CAM-02"]["conflicts"] == 1


def test_avg_confidence():
    m = FusionMetrics()
    feed(m, "CAM-01", 3, matches=3, confidences=[0.8, 0.9, 1.0])
    assert by_id(m.camera_health())["CAM-01"]["avg_confidence"] == 0.9


def test_not_visible_and_rate():
    m = FusionMetrics()
    feed(m, "CAM-01", 10, matches=10, not_visible=4)
    row = by_id(m.camera_health())["CAM-01"]
    assert row["not_visible"] == 4
    assert row["not_visible_rate"] == 0.4


def test_health_score_in_range():
    m = FusionMetrics()
    feed(m, "CAM-01", 100, matches=95, confidences=[0.95] * 100, not_visible=1)
    score = by_id(m.camera_health())["CAM-01"]["health_score"]
    assert 0.0 <= score <= 100.0
    assert score > 80  # câmera saudável


def test_ordering_worst_first():
    m = FusionMetrics()
    feed(m, "GOOD", 100, matches=98, confidences=[0.95] * 100, not_visible=1)
    feed(m, "BAD", 100, matches=30, confidences=[0.6] * 100, not_visible=70)
    order = [r["camera_id"] for r in m.camera_health()]
    assert order.index("BAD") < order.index("GOOD")


def test_camera_without_observations_is_null():
    m = FusionMetrics()
    # câmera conhecida só por participar de conflito, sem observações
    m.record_conflict({"CAM-GHOST"})
    row = by_id(m.camera_health())["CAM-GHOST"]
    assert row["observations"] == 0
    assert row["identity_match_rate"] is None
    assert row["avg_confidence"] is None
    assert row["not_visible_rate"] is None
    assert row["health_score"] is None


def test_no_division_by_zero():
    m = FusionMetrics()
    m.record_conflict({"CAM-Z"})
    # não deve lançar
    rows = m.camera_health()
    assert any(r["camera_id"] == "CAM-Z" for r in rows)


def test_missing_confidence_yields_null_but_score_still_computed():
    m = FusionMetrics()
    feed(m, "CAM-01", 10, matches=8, confidences=[], not_visible=0)  # sem confidence
    row = by_id(m.camera_health())["CAM-01"]
    assert row["avg_confidence"] is None
    # score usa os componentes disponíveis (identidade, not_visible, conflito)
    assert row["health_score"] is not None
    assert 0 <= row["health_score"] <= 100


def test_zero_conflicts():
    m = FusionMetrics()
    feed(m, "CAM-01", 10, matches=10, confidences=[0.9] * 10)
    assert by_id(m.camera_health())["CAM-01"]["conflicts"] == 0


def test_zero_not_visible():
    m = FusionMetrics()
    feed(m, "CAM-01", 10, matches=10, confidences=[0.9] * 10, not_visible=0)
    assert by_id(m.camera_health())["CAM-01"]["not_visible_rate"] == 0.0


def test_multiple_cameras_all_present():
    m = FusionMetrics()
    for cam in ["A", "B", "C", "D"]:
        feed(m, cam, 10, matches=5, confidences=[0.8] * 10)
    assert len(m.camera_health()) == 4


def test_global_metrics_preserved():
    m = FusionMetrics()
    feed(m, "CAM-01", 10, matches=7, confidences=[0.9] * 10, not_visible=2)
    snap = m.snapshot()
    for field in ("observations_total", "observations_per_second", "fusion_latency_ms",
                  "active_employee_states", "anonymous_observations", "fusion_conflicts",
                  "expired_states", "identity_match_rate", "observations_by_camera",
                  "observations_by_employee"):
        assert field in snap
    assert snap["observations_total"] == 10


def test_consistency_sum_per_camera_matches_total():
    m = FusionMetrics()
    feed(m, "CAM-01", 6, matches=4)
    feed(m, "CAM-02", 4, matches=1)
    rows = m.camera_health()
    assert sum(r["observations"] for r in rows) == m.snapshot()["observations_total"]
    assert sum(r["identity_matches"] for r in rows) == 5  # 4 + 1
    assert sum(r["anonymous"] for r in rows) == m.snapshot()["anonymous_observations"]


def test_score_clamped_with_high_conflicts():
    m = FusionMetrics()
    feed(m, "CAM-01", 10, matches=10, confidences=[0.9] * 10)
    for _ in range(50):  # muito mais conflitos que observações
        m.record_conflict({"CAM-01"})
    row = by_id(m.camera_health())["CAM-01"]
    assert 0.0 <= row["health_score"] <= 100.0  # conflict_rate limitado a 1.0


def test_scenario_healthy_vs_low_identification():
    m = FusionMetrics()
    feed(m, "CAM-01", 1000, matches=980, confidences=[0.95] * 1000, not_visible=10)
    feed(m, "CAM-02", 1000, matches=300, confidences=[0.70] * 1000, not_visible=100)
    h = by_id(m.camera_health())
    assert h["CAM-01"]["health_score"] > h["CAM-02"]["health_score"]


def test_scenario_many_conflicts_penalized():
    m = FusionMetrics()
    feed(m, "CLEAN", 1000, matches=900, confidences=[0.9] * 1000, not_visible=20)
    feed(m, "CONFLICTED", 1000, matches=900, confidences=[0.9] * 1000, not_visible=20)
    for _ in range(250):
        m.record_conflict({"CONFLICTED"})
    h = by_id(m.camera_health())
    assert h["CONFLICTED"]["health_score"] < h["CLEAN"]["health_score"]
