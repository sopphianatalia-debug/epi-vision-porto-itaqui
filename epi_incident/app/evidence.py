"""
Evidência em imagem de um incidente: SÓ o recorte da pessoa (nunca o quadro inteiro).

Regras aprovadas:
- guarda 30 dias após a revisão (sem revisão: 30 dias após a captura);
- 7 dias após a revisão se DISMISSED (descartado) ou INSUFFICIENT_EVIDENCE;
- só o operador (dos incidentes que ele revisa) e o supervisor (todos) veem;
- todo acesso, envio, exclusão e apagamento automático ficam registrados;
- exige login (INC_AUTH_MODE=required): sem login, nenhuma imagem é guardada ou servida;
- não guarda reconhecimento facial, só pixels do recorte e as caixas de detecção.
"""
from __future__ import annotations

import json
import os
import sqlite3
import struct
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from app.config import Settings
from app.domain.models import Incident


class EvidenceError(Exception):
    pass


class EvidenceDisabled(EvidenceError):
    pass


class InvalidEvidence(EvidenceError):
    pass


class EvidenceNotFound(EvidenceError):
    pass


class EvidenceGone(EvidenceError):
    """A imagem já foi apagada pelo prazo de retenção (ou por um supervisor)."""


class EvidenceForbidden(EvidenceError):
    pass


def image_info(data: bytes) -> tuple[str, int, int]:
    """(tipo MIME, largura, altura) de um JPEG ou PNG; levanta InvalidEvidence para qualquer outra coisa."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24 and data[12:16] == b"IHDR":
        w, h = struct.unpack(">II", data[16:24])
        return "image/png", w, h
    if data[:3] == b"\xff\xd8\xff":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return "image/jpeg", w, h
            i += 2 + seg
    raise InvalidEvidence("a imagem precisa ser JPEG ou PNG válido")


def validate_detections(detections) -> list[dict]:
    """Caixas relativas ao recorte (0..1). A tela desenha por cima; a imagem original não é alterada."""
    if detections is None:
        return []
    if not isinstance(detections, list) or len(detections) > 20:
        raise InvalidEvidence("detections deve ser uma lista com até 20 itens")
    out = []
    for d in detections:
        if not isinstance(d, dict) or not isinstance(d.get("label"), str) or not d["label"] or len(d["label"]) > 40:
            raise InvalidEvidence("cada detecção precisa de um 'label' de até 40 caracteres")
        bbox = d.get("bbox")
        if (not isinstance(bbox, list) or len(bbox) != 4
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1 for v in bbox)
                or bbox[0] + bbox[2] > 1.001 or bbox[1] + bbox[3] > 1.001 or bbox[2] <= 0 or bbox[3] <= 0):
            raise InvalidEvidence("'bbox' deve ser [x, y, largura, altura] entre 0 e 1, dentro do recorte")
        item = {"label": d["label"], "bbox": [float(v) for v in bbox]}
        if d.get("status") is not None:
            if not isinstance(d["status"], str) or len(d["status"]) > 20:
                raise InvalidEvidence("'status' inválido")
            item["status"] = d["status"]
        if d.get("confidence") is not None:
            c = d["confidence"]
            if not isinstance(c, (int, float)) or isinstance(c, bool) or not 0 <= c <= 1:
                raise InvalidEvidence("'confidence' deve estar entre 0 e 1")
            item["confidence"] = float(c)
        out.append(item)
    return out


ALLOWED_FINDING_STATUS = {"PRESENT", "MISSING", "NOT_VISIBLE"}


def validate_findings(findings) -> list[dict]:
    """Resumo por EPI para o revisor: PRESENT | MISSING | NOT_VISIBLE (não ver != faltar). Sem posição."""
    if findings is None:
        return []
    if not isinstance(findings, list) or len(findings) > 10:
        raise InvalidEvidence("findings deve ser uma lista com até 10 itens")
    out = []
    for f in findings:
        if (not isinstance(f, dict) or not isinstance(f.get("label"), str) or not f["label"] or len(f["label"]) > 40
                or f.get("status") not in ALLOWED_FINDING_STATUS):
            raise InvalidEvidence("cada finding precisa de 'label' e 'status' (PRESENT, MISSING ou NOT_VISIBLE)")
        out.append({"label": f["label"], "status": f["status"]})
    return out


@dataclass
class EvidenceMeta:
    evidence_id: str
    incident_id: str
    captured_at: datetime
    mime: str
    width: int
    height: int
    size_bytes: int
    detections: list[dict]
    purged_at: Optional[datetime] = None
    findings: Optional[list] = None

    def public(self, expires_at: Optional[datetime] = None) -> dict:
        return {"evidence_id": self.evidence_id, "incident_id": self.incident_id,
                "captured_at": self.captured_at.isoformat(), "mime": self.mime,
                "width": self.width, "height": self.height, "size_bytes": self.size_bytes,
                "detections": self.detections, "findings": self.findings or [], "purged": self.purged_at is not None,
                "purged_at": self.purged_at.isoformat() if self.purged_at else None,
                "expires_at": expires_at.isoformat() if (expires_at and not self.purged_at) else None}


class EvidenceStore:
    """Metadados e registro de acesso em SQLite; os pixels ficam em arquivos (nome aleatório, modo 0600)."""

    def __init__(self, directory: str, db_path: str = "") -> None:
        self._dir = directory
        os.makedirs(directory, mode=0o700, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(db_path or ":memory:", check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS evidence (evidence_id TEXT PRIMARY KEY, incident_id TEXT NOT NULL, "
                         "captured_at TEXT NOT NULL, mime TEXT NOT NULL, width INTEGER, height INTEGER, size_bytes INTEGER, "
                         "detections TEXT NOT NULL, filename TEXT NOT NULL, purged_at TEXT, findings TEXT NOT NULL DEFAULT '[]')")
        if "findings" not in {r[1] for r in self._db.execute("PRAGMA table_info(evidence)")}:   # banco criado antes desta coluna
            self._db.execute("ALTER TABLE evidence ADD COLUMN findings TEXT NOT NULL DEFAULT '[]'")
        self._db.execute("CREATE TABLE IF NOT EXISTS evidence_access (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, "
                         "action TEXT NOT NULL, evidence_id TEXT, incident_id TEXT, username TEXT, role TEXT)")
        self._db.commit()

    @staticmethod
    def _meta(r) -> EvidenceMeta:
        return EvidenceMeta(r[0], r[1], datetime.fromisoformat(r[2]), r[3], r[4], r[5], r[6], json.loads(r[7]),
                            datetime.fromisoformat(r[9]) if r[9] else None, json.loads(r[10] or "[]"))

    _COLS = "evidence_id,incident_id,captured_at,mime,width,height,size_bytes,detections,filename,purged_at,findings"

    def add(self, meta: EvidenceMeta, data: bytes) -> None:
        filename = uuid.uuid4().hex + (".png" if meta.mime == "image/png" else ".jpg")
        fd = os.open(os.path.join(self._dir, filename), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        with self._lock:
            self._db.execute(f"INSERT INTO evidence ({self._COLS}) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             (meta.evidence_id, meta.incident_id, meta.captured_at.isoformat(), meta.mime, meta.width, meta.height,
                              meta.size_bytes, json.dumps(meta.detections), filename, None, json.dumps(meta.findings or [])))
            self._db.commit()

    def get(self, evidence_id: str) -> Optional[EvidenceMeta]:
        with self._lock:
            r = self._db.execute(f"SELECT {self._COLS} FROM evidence WHERE evidence_id=?", (evidence_id,)).fetchone()
        return self._meta(r) if r else None

    def for_incident(self, incident_id: str) -> list[EvidenceMeta]:
        with self._lock:
            rows = self._db.execute(f"SELECT {self._COLS} FROM evidence WHERE incident_id=? ORDER BY captured_at", (incident_id,)).fetchall()
        return [self._meta(r) for r in rows]

    def all_active(self) -> list[EvidenceMeta]:
        with self._lock:
            rows = self._db.execute(f"SELECT {self._COLS} FROM evidence WHERE purged_at IS NULL").fetchall()
        return [self._meta(r) for r in rows]

    def read(self, evidence_id: str) -> bytes:
        with self._lock:
            r = self._db.execute("SELECT filename FROM evidence WHERE evidence_id=? AND purged_at IS NULL", (evidence_id,)).fetchone()
        if not r:
            raise EvidenceGone(evidence_id)
        try:
            with open(os.path.join(self._dir, r[0]), "rb") as f:
                return f.read()
        except FileNotFoundError:
            raise EvidenceGone(evidence_id)

    def purge(self, evidence_id: str, when: datetime) -> bool:
        with self._lock:
            r = self._db.execute("SELECT filename FROM evidence WHERE evidence_id=? AND purged_at IS NULL", (evidence_id,)).fetchone()
            if not r:
                return False
            try:
                os.remove(os.path.join(self._dir, r[0]))
            except FileNotFoundError:
                pass
            self._db.execute("UPDATE evidence SET purged_at=? WHERE evidence_id=?", (when.isoformat(), evidence_id))
            self._db.commit()
            return True

    def log(self, at: datetime, action: str, evidence_id: Optional[str], incident_id: Optional[str],
            username: Optional[str], role: Optional[str]) -> None:
        with self._lock:
            self._db.execute("INSERT INTO evidence_access (at,action,evidence_id,incident_id,username,role) VALUES (?,?,?,?,?,?)",
                             (at.isoformat(), action, evidence_id, incident_id, username, role))
            self._db.commit()

    def access_log(self, incident_id: str) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT at,action,evidence_id,username,role FROM evidence_access WHERE incident_id=? ORDER BY id", (incident_id,)).fetchall()
        return [{"at": r[0], "action": r[1], "evidence_id": r[2], "username": r[3], "role": r[4]} for r in rows]


class EvidenceService:
    def __init__(self, settings: Settings, store: Optional[EvidenceStore]) -> None:
        self._s, self._store = settings, store

    @property
    def enabled(self) -> bool:
        return self._store is not None and self._s.auth_mode == "required"

    def _require(self) -> EvidenceStore:
        if self._store is None:
            raise EvidenceDisabled("Evidência desativada: defina INC_EVIDENCE_DIR.")
        if self._s.auth_mode != "required":
            raise EvidenceDisabled("Evidência exige login ativo (INC_AUTH_MODE=required): sem login nenhuma imagem é guardada ou servida.")
        return self._store

    # ---- regras de prazo e de acesso -----------------------------------------------------------
    def expires_at(self, incident: Incident, meta: EvidenceMeta) -> datetime:
        short = incident.review_status in ("DISMISSED", "INSUFFICIENT_EVIDENCE")
        days = self._s.evidence_days_dismissed if short else self._s.evidence_days
        return (incident.reviewed_at or meta.captured_at) + timedelta(days=days)

    @staticmethod
    def can_view(user: dict, incident: Incident) -> bool:
        if user["role"] == "SUPERVISOR":
            return True
        return incident.review_status == "PENDING" or incident.reviewed_by == user["username"]

    # ---- operações -----------------------------------------------------------------------------
    def add(self, incident: Incident, data: bytes, detections, now: datetime, findings=None) -> EvidenceMeta:
        store = self._require()
        if len(data) > self._s.evidence_max_bytes:
            raise InvalidEvidence(f"a imagem passa do limite de {self._s.evidence_max_bytes} bytes (envie só o recorte da pessoa)")
        mime, w, h = image_info(data)
        if max(w, h) > self._s.evidence_max_side:
            raise InvalidEvidence(f"o recorte passa de {self._s.evidence_max_side}px de lado; envie só a pessoa, não o quadro inteiro")
        if len(store.for_incident(incident.incident_id)) >= self._s.evidence_max_per_incident:
            raise InvalidEvidence(f"limite de {self._s.evidence_max_per_incident} imagens por incidente")
        meta = EvidenceMeta(uuid.uuid4().hex, incident.incident_id, now, mime, w, h, len(data), validate_detections(detections), None, validate_findings(findings))
        store.add(meta, data)
        store.log(now, "UPLOAD", meta.evidence_id, incident.incident_id, "service", None)
        return meta

    def list(self, incident: Incident, user: dict) -> list[dict]:
        store = self._require()
        if not self.can_view(user, incident):
            raise EvidenceForbidden("Este incidente já foi revisado por outra pessoa.")
        return [m.public(self.expires_at(incident, m)) for m in store.for_incident(incident.incident_id)]

    def image(self, incident: Incident, evidence_id: str, user: dict, now: datetime) -> tuple[bytes, str]:
        store = self._require()
        meta = store.get(evidence_id)
        if meta is None or meta.incident_id != incident.incident_id:
            raise EvidenceNotFound(evidence_id)
        if not self.can_view(user, incident):
            raise EvidenceForbidden("Este incidente já foi revisado por outra pessoa.")
        data = store.read(evidence_id)            # EvidenceGone se já apagada
        store.log(now, "VIEW", evidence_id, incident.incident_id, user["username"], user["role"])
        return data, meta.mime

    def delete(self, incident: Incident, evidence_id: str, user: dict, now: datetime) -> None:
        store = self._require()
        meta = store.get(evidence_id)
        if meta is None or meta.incident_id != incident.incident_id:
            raise EvidenceNotFound(evidence_id)
        if not store.purge(evidence_id, now):
            raise EvidenceGone(evidence_id)
        store.log(now, "DELETE", evidence_id, incident.incident_id, user["username"], user["role"])

    def access_log(self, incident_id: str) -> list[dict]:
        return self._require().access_log(incident_id)

    def purge_expired(self, get_incident, now: datetime) -> int:
        """Apaga imagens vencidas (o registro do incidente e a trilha de acesso permanecem)."""
        if self._store is None:
            return 0
        n = 0
        for meta in self._store.all_active():
            inc = get_incident(meta.incident_id)
            deadline = self.expires_at(inc, meta) if inc is not None else meta.captured_at + timedelta(days=self._s.evidence_days)
            if now >= deadline and self._store.purge(meta.evidence_id, now):
                self._store.log(now, "PURGE", meta.evidence_id, meta.incident_id, "system", None)
                n += 1
        return n
