import numpy as np

from app.enums import RecognitionStatus
from app.recognition.matching import MatchingEngine, cosine_similarity


def _vec(seed: str, dim: int = 64) -> tuple[float, ...]:
    rng = np.random.default_rng(abs(hash(seed)) % (2**32))
    v = rng.standard_normal(dim)
    v = v / np.linalg.norm(v)
    return tuple(float(x) for x in v)


def make_engine(**kw):
    defaults = dict(similarity_threshold=0.55, confidence_threshold=0.80, ambiguity_margin=0.05)
    defaults.update(kw)
    return MatchingEngine(**defaults)


def test_cosine_identity():
    v = _vec("a")
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6


def test_matched_when_probe_equals_gallery():
    engine = make_engine(confidence_threshold=0.5)
    target = _vec("FUNC-000234")
    gallery = [("FUNC-000234", target), ("FUNC-000111", _vec("other"))]
    result = engine.match(target, gallery, model_version="mock-v1", quality_score=0.95)
    assert result.status == RecognitionStatus.MATCHED
    assert result.employee_code == "FUNC-000234"
    assert result.confidence_score >= 0.5


def test_unknown_when_no_gallery():
    engine = make_engine()
    result = engine.match(_vec("x"), [], model_version="mock-v1", quality_score=0.9)
    assert result.status == RecognitionStatus.UNKNOWN
    assert result.employee_code is None


def test_unknown_when_below_similarity_threshold():
    engine = make_engine(similarity_threshold=0.99)
    gallery = [("FUNC-1", _vec("a")), ("FUNC-2", _vec("b"))]
    result = engine.match(_vec("totally-different"), gallery, model_version="m", quality_score=0.9)
    assert result.status == RecognitionStatus.UNKNOWN


def test_ambiguous_when_two_close_candidates():
    # Constrói probe equidistante de dois vetores muito próximos entre si.
    base = np.array(_vec("base"))
    a = base + 0.01 * np.array(_vec("na"))
    b = base + 0.01 * np.array(_vec("nb"))
    a = tuple(a / np.linalg.norm(a))
    b = tuple(b / np.linalg.norm(b))
    probe = tuple(base / np.linalg.norm(base))
    engine = make_engine(similarity_threshold=0.3, ambiguity_margin=0.2)
    result = engine.match(probe, [("A", a), ("B", b)], model_version="m", quality_score=0.9)
    assert result.status == RecognitionStatus.AMBIGUOUS
    assert result.employee_code is None
    assert result.requires_review is True


def test_low_confidence_between_thresholds():
    # Constrói probe com cosseno controlado (~0.70) em relação ao alvo:
    # acima do similarity_threshold (0.55) mas com confiança abaixo de 0.80.
    dim = 64
    e1 = np.zeros(dim); e1[0] = 1.0
    e2 = np.zeros(dim); e2[1] = 1.0
    cos = 0.70
    probe = tuple(cos * e1 + np.sqrt(1 - cos**2) * e2)
    target = tuple(e1)
    engine = make_engine(similarity_threshold=0.55, confidence_threshold=0.80)
    gallery = [("FUNC-1", target), ("FUNC-2", tuple(-e1))]  # runner bem distante
    result = engine.match(probe, gallery, model_version="m", quality_score=0.9)
    assert result.status == RecognitionStatus.LOW_CONFIDENCE
    assert result.employee_code == "FUNC-1"
    assert result.requires_review is True
