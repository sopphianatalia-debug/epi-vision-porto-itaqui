import os

os.environ.setdefault("CMP_ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.geometry import BoundingBox
from app.main import app
from app.types import PersonObservation, PPEObservation

PREFIX = "/api/v1"


@pytest.fixture
def client():
    return TestClient(app)


def bbox(x1, y1, x2, y2):
    return BoundingBox(x1, y1, x2, y2)


def ppe(ppe_type, x1, y1, x2, y2, conf=0.92):
    return PPEObservation(ppe_type, bbox(x1, y1, x2, y2), conf)


# Pessoa "de corpo inteiro" num frame 1000x1000: [300,100,500,900] (h=800).
# Regiões (frações da pessoa):
#   HEAD  y: 100..260   EYES 140..228   TORSO 260..540
#   HANDS y: 460..700   FEET  820..900
def full_body_obs(track="TRACK-000001", ppe_list=None, frame=(1000, 1000), **kw):
    return PersonObservation(
        person_track_id=track,
        person_bbox=bbox(300, 100, 500, 900),
        frame_width=frame[0],
        frame_height=frame[1],
        ppe=ppe_list or [],
        **kw,
    )


def default_settings(**over):
    return Settings(environment="test", **over)
