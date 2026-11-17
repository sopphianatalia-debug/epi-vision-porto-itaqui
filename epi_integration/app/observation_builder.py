"""
Observation Builder — Fase 3.7.

Traduz `PersonResult` (saída real do Módulo 2 — YOLO/tracker/associador) para
o formato `ppe: dict[str, dict]` que `POST /fusion/observations` espera.

Reaproveita inteiramente o que o Módulo 2 já produz — não refaz detecção,
tracking nem associação. Só traduz o vocabulário de um lado para o outro,
seguindo o mesmo padrão das pontes das Fases 3.5/3.6 (`bridge.py`).

==================================================================
Ponto de fricção 4 — silêncio do detector NÃO é silêncio de câmera
==================================================================
O Fusion já tinha, desde a Fase 3.1, uma regra para "câmera que não fala
nada sobre um EPI": se o perfil de visibilidade da câmera diz que ela não
enxerga aquela região do corpo, o silêncio vira NOT_VISIBLE; se a câmera
enxerga mas fica em silêncio, o silêncio vira NOT_OBSERVED (não MISSING!).
NOT_OBSERVED é tratado pelo Rules Engine como INDETERMINATE, igual a
NOT_VISIBLE — ou seja, silêncio nunca abre incidente, custe o que custar.

Isso é correto para o caso original (câmera que nunca reportou nada sobre
aquele funcionário). Mas o Módulo 2 é diferente: ele RODA a detecção em
todo frame. Se o YOLO analisou a pessoa inteira e não achou capacete, isso
não é "a câmera ficou em silêncio" — é uma ausência real, observada. Se o
Observation Builder simplesmente omitisse a chave "helmet" nesses casos,
todo frame sem capacete detectado cairia em NOT_OBSERVED/INDETERMINATE, e
o sistema NUNCA abriria um incidente por EPI ausente — o que anularia a
funcionalidade inteira.

A regra que este módulo aplica, então, é:

- Módulo 2 detectou o EPI na pessoa -> DETECTED, com a confidence real.
- Módulo 2 rodou a detecção e NÃO achou o EPI, E a câmera (por perfil de
  visibilidade, configurado uma vez por câmera, não por frame) consegue
  enxergar aquela região do corpo -> MISSING explícito (ausência real,
  observada pelo detector).
- A câmera não enxerga aquela região por enquadramento (perfil de
  visibilidade) -> a chave é omitida; o Fusion decide NOT_VISIBLE sozinho,
  exatamente como já fazia antes desta fase.

Ou seja: o perfil de visibilidade continua sendo a única fonte de verdade
sobre "o que a câmera consegue fisicamente enxergar" (configurado uma vez,
via POST /fusion/cameras/{id}/visibility, já existente desde a Fase 3.1) —
este módulo só decide, a cada frame, se o que FOI enxergado tinha o EPI ou
não.
"""
from __future__ import annotations

from typing import Optional

# Módulo 2 usa nomes de enum (SAFETY_VEST, SAFETY_BOOTS, ...); o Fusion usa
# slugs curtos (vest, boots, ...). Mapeamento explícito — nunca `.lower()`
# ingênuo, porque os nomes não seguem o mesmo padrão (SAFETY_VEST -> vest,
# não safety_vest).
DETECTION_CLASS_TO_PPE_TYPE: dict[str, str] = {
    "HELMET": "helmet",
    "SAFETY_VEST": "vest",
    "GLOVES": "gloves",
    "SAFETY_BOOTS": "boots",
    "SAFETY_GLASSES": "glasses",
    "EAR_PROTECTION": "ear_protection",
}

# Regiões corporais associadas a cada tipo de EPI, para cruzar com o perfil
# de visibilidade da câmera (mesmas regiões que o epi_fusion já usa em
# CameraVisibilityProfile: face, head, torso, hands, feet).
PPE_TYPE_TO_BODY_REGION: dict[str, str] = {
    "helmet": "head",
    "vest": "torso",
    "gloves": "hands",
    "boots": "feet",
    "glasses": "face",
    "ear_protection": "head",
}


def build_fusion_ppe(
    person_result_dict: dict,
    *,
    camera_can_see: Optional[dict[str, bool]] = None,
    tracked_ppe_types: tuple[str, ...] = ("helmet", "vest", "gloves", "boots"),
) -> dict[str, dict]:
    """Constrói o `ppe` para POST /fusion/observations a partir de um item
    de `persons` na resposta de POST /pipeline/process-frame do epi_ppe
    (schema `PersonResultOut`: person_track_id, employee_id,
    person_confidence, person_bbox, detections: [{type, confidence, bbox}]).

    `camera_can_see`: mapa opcional {ppe_type: bool}, tipicamente obtido do
    mesmo perfil de visibilidade já cadastrado no Fusion para essa câmera
    (ver `docs/contracts.md`, Fricção 4). Se None, assume que a câmera
    enxerga todas as regiões (comportamento seguro-por-padrão: qualquer
    ausência detectada é reportada como MISSING).

    `tracked_ppe_types`: quais tipos de EPI este builder deve reportar
    ausência explícita quando não detectados. Tipos fora dessa lista nunca
    geram MISSING por omissão — só DETECTED quando o Módulo 2 realmente os
    encontra (útil para EPIs opcionais, ex. óculos/proteção auricular, que
    a regra padrão do Rules Engine não exige).
    """
    detected_by_type: dict[str, dict] = {}
    for det in person_result_dict.get("detections", []):
        ppe_type = DETECTION_CLASS_TO_PPE_TYPE.get(det["type"])
        if ppe_type is None:
            continue  # classe desconhecida para o Fusion — ignorada, não quebra o pipeline
        # Se o mesmo tipo aparecer mais de uma vez associado à pessoa (raro,
        # mas possível), fica a detecção de maior confidence.
        existing = detected_by_type.get(ppe_type)
        if existing is None or det["confidence"] > existing["confidence"]:
            detected_by_type[ppe_type] = det

    out: dict[str, dict] = {}
    for ppe_type, det in detected_by_type.items():
        out[ppe_type] = {"status": "DETECTED", "confidence": round(det["confidence"], 4)}

    person_confidence = person_result_dict.get("person_confidence", 0.5)
    for ppe_type in tracked_ppe_types:
        if ppe_type in out:
            continue
        region = PPE_TYPE_TO_BODY_REGION.get(ppe_type)
        can_see = True if camera_can_see is None or region is None else camera_can_see.get(region, True)
        if can_see:
            # Detector rodou, não achou -> ausência real e observada.
            out[ppe_type] = {"status": "MISSING", "confidence": round(person_confidence, 4)}
        # else: silêncio estrutural — chave omitida, Fusion decide NOT_VISIBLE.

    return out


def regions_cut_by_frame(person_bbox, frame_width: float, frame_height: float,
                         margin: float = 0.01) -> dict[str, bool]:
    """Regiões do corpo que o ENQUADRAMENTO corta para esta pessoa neste quadro.

    Caixa encostada na borda de cima -> a cabeça pode estar fora do quadro: um
    capacete que falta não pode ser afirmado (-> "não observável", nunca
    "ausente"). Caixa encostada na borda de baixo -> idem para os pés/botas.
    Só devolve regiões cortadas (valor False); regiões visíveis não aparecem,
    para combinar com o perfil de visibilidade fixo da câmera sem sobrescrevê-lo.
    """
    if not person_bbox or len(person_bbox) != 4 or frame_width <= 0 or frame_height <= 0:
        return {}
    _x1, y1, _x2, y2 = person_bbox
    cut: dict[str, bool] = {}
    if y1 <= margin * frame_height:
        cut["head"] = False
        cut["face"] = False
    if y2 >= (1.0 - margin) * frame_height:
        cut["feet"] = False
    return cut
