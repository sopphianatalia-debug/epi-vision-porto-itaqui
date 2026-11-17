from app.domain import AlertStatus, AlertType, Condition, Severity
from tests.conftest import FakeHttp  # noqa: F401


def cond(key="tracker_offline:T1", source="tracker", severity=Severity.WARNING, msg="m"):
    return Condition(key, source, AlertType.TRACKER_OFFLINE, severity, "Rastreador offline", msg, {"tracker_id": "T1"})


class Src:
    def __init__(self, name, conditions=None, fail=False):
        self.name, self.conditions, self.fail = name, conditions or [], fail

    def collect(self):
        if self.fail:
            raise ConnectionError("x")
        return list(self.conditions)


def test_new_condition_opens_one_alert(svc):
    svc.reconcile("tracker", [cond()])
    alerts = svc.list()
    assert len(alerts) == 1 and alerts[0].status == AlertStatus.OPEN


def test_same_condition_is_not_duplicated(svc, clock):
    svc.reconcile("tracker", [cond()])
    clock.advance(5)
    svc.reconcile("tracker", [cond(msg="atualizada")])
    alerts = svc.list()
    assert len(alerts) == 1
    assert alerts[0].occurrences == 2 and alerts[0].message == "atualizada"
    assert alerts[0].last_seen_at > alerts[0].opened_at


def test_condition_gone_resolves_alert(svc):
    svc.reconcile("tracker", [cond()])
    svc.reconcile("tracker", [])
    assert svc.list() == []
    resolved = svc.list(include_resolved=True)
    assert resolved[0].status == AlertStatus.RESOLVED and resolved[0].resolved_at is not None


def test_recurrence_after_resolution_opens_a_new_alert(svc):
    svc.reconcile("tracker", [cond()])
    svc.reconcile("tracker", [])
    svc.reconcile("tracker", [cond()])
    assert len(svc.list(include_resolved=True)) == 2
    assert len(svc.list()) == 1


def test_reconcile_only_touches_its_own_source(svc):
    svc.reconcile("tracker", [cond()])
    svc.reconcile("incident", [])
    assert len(svc.list()) == 1


def test_acknowledge_keeps_alert_active_and_does_not_reopen(svc):
    svc.reconcile("tracker", [cond()])
    alert = svc.list()[0]
    svc.acknowledge(alert.alert_id)
    svc.reconcile("tracker", [cond()])
    assert len(svc.list()) == 1
    assert svc.list()[0].status == AlertStatus.ACKNOWLEDGED
    assert svc.summary()["unacknowledged"] == 0 and svc.summary()["open_total"] == 1


def test_acknowledge_unknown_raises(svc):
    import pytest
    from app.service import AlertNotFoundError
    with pytest.raises(AlertNotFoundError):
        svc.acknowledge("ALERT-999999")


def test_source_down_does_not_resolve_existing_alerts(svc):
    svc.sync([Src("tracker", [cond()])])
    svc.sync([Src("tracker", fail=True)])
    assert len(svc.list()) == 1
    status = svc.summary()["sources"]["tracker"]
    assert status["online"] is False


def test_source_back_online_resolves_when_condition_gone(svc):
    svc.sync([Src("tracker", [cond()])])
    svc.sync([Src("tracker", fail=True)])
    svc.sync([Src("tracker", [])])
    assert svc.list() == []
    assert svc.summary()["sources"]["tracker"]["online"] is True


def test_one_failing_source_does_not_block_others(svc):
    svc.sync([Src("tracker", fail=True), Src("incident", [cond("incident:1", "incident")])])
    assert len(svc.list()) == 1


def test_sync_if_stale_respects_interval(svc, clock):
    s = Src("tracker", [cond()])
    assert svc.sync_if_stale([s]) is True
    assert svc.sync_if_stale([s]) is False
    clock.advance(3)
    assert svc.sync_if_stale([s]) is True


def test_ordering_critical_first_and_filters(svc):
    svc.reconcile("tracker", [cond("a", severity=Severity.INFO), cond("b", severity=Severity.CRITICAL),
                              cond("c", severity=Severity.WARNING)])
    assert [a.severity for a in svc.list()] == [Severity.CRITICAL, Severity.WARNING, Severity.INFO]
    assert len(svc.list(severity="WARNING")) == 1
    assert len(svc.list(source="incident")) == 0


def test_old_resolved_alerts_leave_history(svc, clock):
    svc.reconcile("tracker", [cond()])
    svc.reconcile("tracker", [])
    clock.advance(4000)
    assert svc.list(include_resolved=True) == []


def test_summary_counts(svc):
    svc.reconcile("tracker", [cond("a", severity=Severity.CRITICAL), cond("b", severity=Severity.INFO)])
    s = svc.summary()
    assert s["open_total"] == 2 and s["by_severity"] == {"CRITICAL": 1, "WARNING": 0, "INFO": 1}
    assert s["by_source"] == {"tracker": 2}
