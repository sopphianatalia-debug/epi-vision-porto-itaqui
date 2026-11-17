"""
Avaliadores por EPI (avaliação de UM frame).

Cada avaliador combina três sinais, não apenas a existência da caixa:
1. VISIBILIDADE da região corporal (senão -> NOT_VISIBLE, nunca MISSING);
2. PRESENÇA do EPI associado àquela região;
3. POSICIONAMENTO (o EPI está na região certa? -> PROPER vs IMPROPER).

Retornam FrameAssessment (status + confiança + motivo), que depois é agregado
temporalmente.
"""
from __future__ import annotations

from app.config import Settings
from app.enums import BodyRegion, PPEStatus, Visibility
from app.geometry import BoundingBox, center_inside, containment, coverage
from app.types import FrameAssessment, PersonObservation, PPEObservation

# Confiança padrão para uma região comprovadamente não visível.
_NOT_VISIBLE_CONF = 0.9
# Confiança de "ausente" (região visível, nada detectado).
_MISSING_CONF = 0.75


def _ppe_of(obs: PersonObservation, ppe_type: str) -> list[PPEObservation]:
    return [p for p in obs.ppe if p.ppe_type == ppe_type]


def _best_for_region(cands: list[PPEObservation], region: BoundingBox) -> tuple[PPEObservation | None, float]:
    """Retorna o EPI mais sobreposto à região e o quanto ele a cobre (0..1)."""
    best, best_ov = None, 0.0
    for c in cands:
        ov = max(coverage(c.bbox, region), containment(c.bbox, region))
        if ov > best_ov:
            best, best_ov = c, ov
    return best, best_ov


def _not_visible() -> FrameAssessment:
    return FrameAssessment(PPEStatus.NOT_VISIBLE, _NOT_VISIBLE_CONF, "region_not_visible")


def evaluate_helmet(obs, regions, vis, s: Settings) -> FrameAssessment:
    if vis[BodyRegion.HEAD] == Visibility.NOT_VISIBLE:
        return _not_visible()
    head = regions[BodyRegion.HEAD]
    cands = _ppe_of(obs, "helmet")
    if not cands:
        return FrameAssessment(PPEStatus.MISSING, _MISSING_CONF, "no_helmet_detected")
    helmet, _ = _best_for_region(cands, head)
    if helmet is None:  # detectado, mas sem overlap com a cabeça -> presente porém mal posicionado
        helmet = max(cands, key=lambda c: c.confidence)
    cont = containment(helmet.bbox, head)  # fração do capacete dentro da cabeça
    if center_inside(helmet.bbox, head) and cont >= s.helmet_head_overlap_threshold:
        conf = helmet.confidence * (0.6 + 0.4 * min(1.0, cont))
        return FrameAssessment(PPEStatus.PROPER, conf, "helmet_on_head")
    # capacete presente mas fora da cabeça: na mão, pendurado, etc.
    return FrameAssessment(PPEStatus.IMPROPER, helmet.confidence * 0.7, "helmet_not_on_head")


def evaluate_vest(obs, regions, vis, s: Settings) -> FrameAssessment:
    if vis[BodyRegion.TORSO] == Visibility.NOT_VISIBLE:
        return _not_visible()
    torso = regions[BodyRegion.TORSO]
    cands = _ppe_of(obs, "vest")
    if not cands:
        return FrameAssessment(PPEStatus.MISSING, _MISSING_CONF, "no_vest_detected")
    vest, _ = _best_for_region(cands, torso)
    if vest is None:
        vest = max(cands, key=lambda c: c.confidence)
    cov = coverage(vest.bbox, torso)  # fração do torso coberta
    if cov >= s.vest_torso_coverage_threshold:
        conf = vest.confidence * (0.5 + 0.5 * min(1.0, cov))
        return FrameAssessment(PPEStatus.PROPER, conf, "vest_covers_torso")
    return FrameAssessment(PPEStatus.IMPROPER, vest.confidence * 0.7, "vest_low_coverage")


def _evaluate_glove(obs, regions, vis, s: Settings, region: BodyRegion) -> FrameAssessment:
    if vis[region] == Visibility.NOT_VISIBLE:
        return _not_visible()
    hand = regions[region]
    cands = _ppe_of(obs, "gloves")
    glove, ov = _best_for_region(cands, hand)
    if glove is not None and ov >= s.glove_hand_overlap_threshold:
        return FrameAssessment(PPEStatus.PROPER, glove.confidence * (0.6 + 0.4 * min(1.0, ov)), "glove_on_hand")
    return FrameAssessment(PPEStatus.MISSING, _MISSING_CONF, "no_glove_on_hand")


def evaluate_glove_left(obs, regions, vis, s):
    return _evaluate_glove(obs, regions, vis, s, BodyRegion.LEFT_HAND)


def evaluate_glove_right(obs, regions, vis, s):
    return _evaluate_glove(obs, regions, vis, s, BodyRegion.RIGHT_HAND)


def evaluate_glasses(obs, regions, vis, s: Settings) -> FrameAssessment:
    if vis[BodyRegion.EYES] == Visibility.NOT_VISIBLE:
        return _not_visible()
    eyes = regions[BodyRegion.EYES]
    cands = _ppe_of(obs, "glasses")
    if not cands:
        return FrameAssessment(PPEStatus.MISSING, _MISSING_CONF, "no_glasses_detected")
    glasses, ov = _best_for_region(cands, eyes)
    if glasses is None:
        glasses, ov = max(cands, key=lambda c: c.confidence), 0.0
    if center_inside(glasses.bbox, eyes) or ov > 0.1:
        return FrameAssessment(PPEStatus.PROPER, glasses.confidence * 0.85, "glasses_on_eyes")
    return FrameAssessment(PPEStatus.IMPROPER, glasses.confidence * 0.7, "glasses_misplaced")


def evaluate_boots(obs, regions, vis, s: Settings) -> FrameAssessment:
    # Regra explícita: se os pés não estão no campo de visão -> NOT_VISIBLE.
    if vis[BodyRegion.FEET] == Visibility.NOT_VISIBLE:
        return _not_visible()
    feet = regions[BodyRegion.FEET]
    cands = _ppe_of(obs, "boots")
    if not cands:
        return FrameAssessment(PPEStatus.MISSING, _MISSING_CONF, "no_boots_detected")
    boots, ov = _best_for_region(cands, feet)
    if boots is None:
        boots, ov = max(cands, key=lambda c: c.confidence), 0.0
    if ov >= s.boots_feet_overlap_threshold:
        return FrameAssessment(PPEStatus.PROPER, boots.confidence * (0.6 + 0.4 * min(1.0, ov)), "boots_on_feet")
    return FrameAssessment(PPEStatus.IMPROPER, boots.confidence * 0.7, "boots_misplaced")


# Chave -> função avaliadora. A ordem define as chaves do resultado.
EVALUATORS = {
    "helmet": evaluate_helmet,
    "vest": evaluate_vest,
    "glove_left": evaluate_glove_left,
    "glove_right": evaluate_glove_right,
    "glasses": evaluate_glasses,
    "boots": evaluate_boots,
}


def evaluate_frame(obs, regions, vis, s: Settings) -> dict[str, FrameAssessment]:
    return {key: fn(obs, regions, vis, s) for key, fn in EVALUATORS.items()}
