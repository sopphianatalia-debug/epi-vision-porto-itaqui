"""
Modelo do dashboard interno (seção 15 do spec).

Traduz o ComplianceResult em uma visão amigável com sinalização por cor/emoji.
"""
from __future__ import annotations

from app.enums import ComplianceStatus, PPEStatus
from app.types import ComplianceResult

_PPE_VIEW = {
    PPEStatus.PROPER: ("🟢", "Correto"),
    PPEStatus.PRESENT: ("🟢", "Presente"),
    PPEStatus.MISSING: ("🔴", "Ausente"),
    PPEStatus.IMPROPER: ("🔴", "Incorreto"),
    PPEStatus.NOT_VISIBLE: ("⚪", "Não verificável"),
    PPEStatus.UNKNOWN: ("🟡", "Indeterminado"),
}

_OVERALL_VIEW = {
    ComplianceStatus.COMPLIANT: ("✅", "CONFORME"),
    ComplianceStatus.PARTIAL_NON_COMPLIANCE: ("⚠️", "PARCIALMENTE NÃO CONFORME"),
    ComplianceStatus.NON_COMPLIANT: ("⚠️", "NÃO CONFORME"),
    ComplianceStatus.UNDETERMINED: ("❓", "NÃO DETERMINADO"),
}


def _item(label: str, status: PPEStatus, detail: str = "") -> dict:
    emoji, text = _PPE_VIEW[status]
    return {"label": label, "status": status.value, "emoji": emoji,
            "text": f"{text}{(' — ' + detail) if detail else ''}"}


def build_dashboard(result: ComplianceResult) -> dict:
    gl, gr = result.glove_left.status, result.glove_right.status
    glove_detail = ""
    if gl != gr:
        missing = "esquerda" if gl in (PPEStatus.MISSING, PPEStatus.IMPROPER) else "direita"
        glove_detail = f"mão {missing} sem luva"
    gloves_status = gl if gl == gr else (
        PPEStatus.MISSING if PPEStatus.MISSING in (gl, gr) else PPEStatus.UNKNOWN
    )

    overall_emoji, overall_text = _OVERALL_VIEW[result.overall]
    return {
        "person": {"employee_id": result.employee_id, "person_track_id": result.person_track_id},
        "items": [
            _item("Capacete", result.helmet.status),
            _item("Colete", result.vest.status),
            _item("Luvas", gloves_status, glove_detail),
            _item("Óculos", result.glasses.status),
            _item("Botas", result.boots.status),
        ],
        "overall": {"status": result.overall.value, "emoji": overall_emoji, "text": overall_text},
    }
