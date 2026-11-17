from __future__ import annotations

import itertools
import threading
from datetime import timedelta
from typing import Optional, Protocol

from app.clock import Clock
from app.domain import SEVERITY_ORDER, Alert, AlertStatus, Condition


class AlertNotFoundError(Exception):
    pass


class Source(Protocol):
    name: str

    def collect(self) -> list[Condition]: ...


class AlertService:
    """Reconcilia as condições ativas de cada fonte com os alertas.

    - condição nova            -> abre alerta
    - condição que continua    -> atualiza (sem duplicar)
    - condição que sumiu       -> resolve sozinho
    - fonte fora do ar         -> NÃO resolve nada (não sabemos se o problema
                                  passou) e o estado da fonte fica visível.
    """

    def __init__(self, clock: Clock, sync_min_interval: float = 3.0, keep_resolved_seconds: float = 3600.0) -> None:
        self._clock = clock
        self._interval = sync_min_interval
        self._keep_resolved = keep_resolved_seconds
        self._alerts: dict[str, Alert] = {}
        self._ids = itertools.count(1)
        self._lock = threading.RLock()
        self._last_sync = None
        self.source_status: dict[str, dict] = {}

    # ------------------------------------------------------------------ #
    def reconcile(self, source: str, conditions: list[Condition]) -> None:
        now = self._clock.now()
        with self._lock:
            seen = set()
            for cond in conditions:
                seen.add(cond.key)
                existing = self._active_by_key(cond.key)
                if existing is None:
                    alert_id = f"ALERT-{next(self._ids):06d}"
                    self._alerts[alert_id] = Alert(
                        alert_id=alert_id, key=cond.key, source=cond.source, type=cond.type,
                        severity=cond.severity, status=AlertStatus.OPEN, title=cond.title,
                        message=cond.message, entity=cond.entity, opened_at=now, last_seen_at=now,
                    )
                else:
                    existing.last_seen_at = now
                    existing.occurrences += 1
                    existing.severity = cond.severity
                    existing.message = cond.message
                    existing.entity = cond.entity
            for alert in self._alerts.values():
                if alert.active and alert.source == source and alert.key not in seen:
                    alert.status = AlertStatus.RESOLVED
                    alert.resolved_at = now

    def sync(self, sources: list[Source]) -> None:
        now = self._clock.now()
        for src in sources:
            try:
                conditions = src.collect()
            except Exception as exc:  # fonte fora do ar: não derruba nem resolve
                self.source_status[src.name] = {"online": False, "error": type(exc).__name__,
                                                "checked_at": now.isoformat()}
                continue
            self.reconcile(src.name, conditions)
            self.source_status[src.name] = {"online": True, "error": None, "checked_at": now.isoformat()}
        with self._lock:
            self._last_sync = now

    def sync_if_stale(self, sources: list[Source]) -> bool:
        now = self._clock.now()
        with self._lock:
            if self._last_sync is not None and (now - self._last_sync).total_seconds() < self._interval:
                return False
        self.sync(sources)
        return True

    # ------------------------------------------------------------------ #
    def acknowledge(self, alert_id: str) -> Alert:
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                raise AlertNotFoundError(alert_id)
            if alert.status == AlertStatus.OPEN:
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_at = self._clock.now()
            return alert

    def get(self, alert_id: str) -> Alert:
        alert = self._alerts.get(alert_id)
        if alert is None:
            raise AlertNotFoundError(alert_id)
        return alert

    def list(self, status: Optional[str] = None, severity: Optional[str] = None,
             source: Optional[str] = None, include_resolved: bool = False) -> list[Alert]:
        cutoff = self._clock.now() - timedelta(seconds=self._keep_resolved)
        with self._lock:
            items = list(self._alerts.values())
        out = []
        for a in items:
            if status:
                if a.status.value != status:
                    continue
            elif not include_resolved and not a.active:
                continue
            if a.status.value == "RESOLVED" and a.resolved_at and a.resolved_at < cutoff:
                continue
            if severity and a.severity.value != severity:
                continue
            if source and a.source != source:
                continue
            out.append(a)
        out.sort(key=lambda a: (SEVERITY_ORDER[a.severity], -a.opened_at.timestamp()))
        return out

    def summary(self) -> dict:
        with self._lock:
            active = [a for a in self._alerts.values() if a.active]
        by_sev = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}
        by_source: dict[str, int] = {}
        for a in active:
            by_sev[a.severity.value] += 1
            by_source[a.source] = by_source.get(a.source, 0) + 1
        return {
            "open_total": len(active),
            "unacknowledged": sum(1 for a in active if a.status == AlertStatus.OPEN),
            "by_severity": by_sev, "by_source": by_source,
            "sources": dict(self.source_status),
        }

    def reset(self) -> None:
        with self._lock:
            self._alerts.clear()
            self.source_status.clear()
            self._last_sync = None

    def _active_by_key(self, key: str) -> Optional[Alert]:
        for a in self._alerts.values():
            if a.key == key and a.active:
                return a
        return None
