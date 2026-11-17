"""Ajuste de persistência (debounce/histerese) das regras, via API do Rules Engine.

O Rules Engine já sabe confirmar uma violação só depois de `min_violation_seconds`
contínuos e só confirmar a recuperação após `min_recovery_seconds` contínuos. As
regras de exemplo vêm com 0 s (para testes que avaliam um estado por vez), o que
faz uma câmera real abrir/fechar incidentes a cada oscilação da detecção.

Aqui criamos uma NOVA VERSÃO da regra (as antigas ficam para auditoria) com os
tempos desejados. Nenhuma decisão de conformidade é tomada neste módulo.
"""
from __future__ import annotations

import httpx

_REQ_FIELDS = ("ppe_type", "required", "minimum_confidence", "not_visible_policy", "unknown_policy", "severity")


def apply_persistence(rules_base_url: str, rule_ids, violation_seconds: float,
                      recovery_seconds: float, timeout: float = 5.0,
                      min_confidence: float | None = None) -> dict[str, int]:
    """Retorna {rule_id: nova_versão}. Regras inexistentes são ignoradas.

    `min_confidence` (opcional) substitui a confiança mínima da regra e de cada requisito.
    Detecção abaixo dela continua INDETERMINATE (nunca vira violação nem conformidade)."""
    out: dict[str, int] = {}
    with httpx.Client(base_url=rules_base_url.rstrip("/"), timeout=timeout) as c:
        for rule_id in rule_ids:
            r = c.get(f"/rules/{rule_id}")
            if r.status_code == 404:
                continue
            r.raise_for_status()
            cur = r.json()
            body = {k: cur[k] for k in ("rule_id", "name", "active", "priority", "area", "operation", "role",
                                        "minimum_confidence", "severity", "indeterminate_rollup")}
            body["min_violation_seconds"] = float(violation_seconds)
            body["min_recovery_seconds"] = float(recovery_seconds)
            body["requirements"] = [{k: req[k] for k in _REQ_FIELDS if k in req} for req in cur["requirements"]]
            if min_confidence is not None:
                body["minimum_confidence"] = float(min_confidence)
                for req in body["requirements"]:
                    if "minimum_confidence" in req:
                        req["minimum_confidence"] = float(min_confidence)
            put = c.put(f"/rules/{rule_id}", json=body)
            put.raise_for_status()
            out[rule_id] = put.json()["version"]
    return out
