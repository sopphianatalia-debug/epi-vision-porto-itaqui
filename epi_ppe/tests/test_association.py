from app.association import PersonPPEAssociator, association_score
from app.enums import DetectionClass
from app.types import BoundingBox, Detection


def det(cls, x1, y1, x2, y2, conf=0.9):
    return Detection(cls=cls, confidence=conf, bbox=BoundingBox(x1, y1, x2, y2))


def make_assoc():
    return PersonPPEAssociator(containment_threshold=0.5, score_threshold=0.35)


def test_helmet_on_head_is_associated():
    # Exemplo do spec: pessoa [100,100,300,500], capacete [150,110,230,160].
    person = det(DetectionClass.PERSON, 100, 100, 300, 500)
    helmet = det(DetectionClass.HELMET, 150, 110, 230, 160)
    results = make_assoc().associate([("TRACK-000001", person)], [helmet])
    assert len(results[0].ppe) == 1
    assert results[0].ppe[0].cls == DetectionClass.HELMET


def test_distant_helmet_is_not_associated():
    person = det(DetectionClass.PERSON, 100, 100, 300, 500)
    far_helmet = det(DetectionClass.HELMET, 700, 300, 800, 360)
    results = make_assoc().associate([("TRACK-000001", person)], [far_helmet])
    assert results[0].ppe == []


def test_helmet_at_feet_scores_lower_than_at_head():
    person = det(DetectionClass.PERSON, 100, 100, 300, 500)
    at_head = det(DetectionClass.HELMET, 150, 110, 230, 160)
    at_feet = det(DetectionClass.HELMET, 150, 460, 230, 495)
    s_head = association_score(at_head, person, 0.5)
    s_feet = association_score(at_feet, person, 0.5)
    assert s_head > s_feet


def test_boots_associate_at_bottom():
    person = det(DetectionClass.PERSON, 100, 100, 300, 500)
    boots = det(DetectionClass.SAFETY_BOOTS, 130, 470, 270, 500)
    results = make_assoc().associate([("TRACK-000001", person)], [boots])
    assert len(results[0].ppe) == 1
    assert results[0].ppe[0].cls == DetectionClass.SAFETY_BOOTS


def test_ppe_goes_to_closest_of_two_people():
    p1 = det(DetectionClass.PERSON, 100, 100, 300, 500)
    p2 = det(DetectionClass.PERSON, 500, 100, 700, 500)
    helmet_on_p2 = det(DetectionClass.HELMET, 550, 110, 630, 160)
    results = make_assoc().associate(
        [("TRACK-000001", p1), ("TRACK-000002", p2)], [helmet_on_p2]
    )
    by_id = {r.person_track_id: r for r in results}
    assert by_id["TRACK-000002"].ppe and not by_id["TRACK-000001"].ppe


def test_module3_contract_reports_presence():
    person = det(DetectionClass.PERSON, 100, 100, 300, 500)
    helmet = det(DetectionClass.HELMET, 150, 110, 230, 160)
    vest = det(DetectionClass.SAFETY_VEST, 130, 230, 270, 380)
    results = make_assoc().associate([("TRACK-000001", person)], [helmet, vest])
    contract = results[0].to_module3_contract()
    assert contract["ppe"]["HELMET"] == "detected"
    assert contract["ppe"]["SAFETY_VEST"] == "detected"
    assert contract["ppe"]["GLOVES"] == "not_detected"
