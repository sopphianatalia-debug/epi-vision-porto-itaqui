from app.domain import AlertType, Condition, Severity

PREFIX = "/api/v1"


def seed(service):
    service.reconcile("tracker", [Condition("k1", "tracker", AlertType.TRACKER_OFFLINE, Severity.WARNING,
                                            "Rastreador offline", "msg", {})])


def test_health(client):
    c, _ = client
    assert c.get(f"{PREFIX}/health").json()["status"] == "ok"
    assert c.get("/health").status_code == 200


def test_list_and_summary(client):
    c, service = client
    seed(service)
    items = c.get(f"{PREFIX}/alerts").json()
    assert len(items) == 1 and items[0]["status"] == "OPEN"
    assert c.get(f"{PREFIX}/alerts/summary").json()["open_total"] == 1


def test_filters(client):
    c, service = client
    seed(service)
    assert c.get(f"{PREFIX}/alerts", params={"severity": "CRITICAL"}).json() == []
    assert len(c.get(f"{PREFIX}/alerts", params={"source": "tracker"}).json()) == 1


def test_acknowledge_and_404(client):
    c, service = client
    seed(service)
    alert_id = c.get(f"{PREFIX}/alerts").json()[0]["alert_id"]
    r = c.post(f"{PREFIX}/alerts/{alert_id}/ack")
    assert r.status_code == 200 and r.json()["status"] == "ACKNOWLEDGED"
    assert c.post(f"{PREFIX}/alerts/ALERT-NAO-EXISTE/ack").status_code == 404


def test_force_sync_returns_summary(client):
    c, _ = client
    r = c.post(f"{PREFIX}/alerts/sync")
    assert r.status_code == 200 and r.json()["open_total"] == 0
