from app.config import Settings
from app.domain.enums import IncidentStatus
from app.infrastructure import FakeClock, InMemoryEventBus, SqliteIncidentRepository
from app.service import IncidentService
from tests.conftest import viol


def _svc(path, clock=None):
    s = Settings(environment="test")
    clock = clock or FakeClock()
    repo = SqliteIncidentRepository(str(path), s.id_prefix, s.id_width)
    return IncidentService(s, clock, InMemoryEventBus(), repo), clock, repo


def test_incident_survives_restart(tmp_path):
    db = tmp_path / "inc.db"
    svc, _c, repo = _svc(db)
    inc, _ = svc.record_violation(viol(evaluation_id="E1", cameras=("CAM-1",)))
    repo.close()
    svc2, _c2, _r2 = _svc(db)
    got = svc2.get(inc.incident_id)
    assert got is not None and got.status == IncidentStatus.OPEN
    assert got.source_cameras == ["CAM-1"] and got.ppe_type == "helmet"


def test_review_and_resolution_survive_restart(tmp_path):
    db = tmp_path / "inc.db"
    svc, clock, repo = _svc(db)
    inc, _ = svc.record_violation(viol(evaluation_id="E1"))
    svc.review_incident(inc.incident_id, "CONFIRMED", "Visto no vídeo.", "op.maria")
    clock.advance(10)
    svc.resolve_incident(inc.incident_id)
    repo.close()
    svc2, _c2, _r2 = _svc(db)
    got = svc2.get(inc.incident_id)
    assert got.review_status == "CONFIRMED" and got.reviewed_by == "op.maria"
    assert got.status == IncidentStatus.RESOLVED and len(got.review_history) == 1


def test_ids_continue_and_dedup_works_after_restart(tmp_path):
    db = tmp_path / "inc.db"
    svc, _c, repo = _svc(db)
    svc.record_violation(viol(evaluation_id="E1"))
    repo.close()
    svc2, _c2, _r2 = _svc(db)
    again, action = svc2.record_violation(viol(evaluation_id="E2"))   # mesmo incidente aberto
    assert action.value == "UPDATED" and again.occurrence_count == 2
    other, action2 = svc2.record_violation(viol(employee="FUNC-009", evaluation_id="E3"))
    assert action2.value == "CREATED" and other.incident_id == "INC-000002"


def test_evaluation_idempotency_survives_restart(tmp_path):
    db = tmp_path / "inc.db"
    svc, _c, repo = _svc(db)
    svc.record_violation(viol(evaluation_id="E1"))
    repo.close()
    svc2, _c2, _r2 = _svc(db)
    _inc, action = svc2.record_violation(viol(evaluation_id="E1"))
    assert action.value == "NOOP"


def test_verified_reviewer_survives_restart(tmp_path):
    db = tmp_path / "inc.db"
    svc, _c, repo = _svc(db)
    inc, _ = svc.record_violation(viol(evaluation_id="E1"))
    svc.review_incident(inc.incident_id, "CONFIRMED", "visto no vídeo", "bruno", role="OPERADOR", verified=True)
    repo.close()
    got = _svc(db)[0].get(inc.incident_id)
    assert got.reviewed_by == "bruno" and got.reviewed_by_role == "OPERADOR" and got.reviewer_verified is True
