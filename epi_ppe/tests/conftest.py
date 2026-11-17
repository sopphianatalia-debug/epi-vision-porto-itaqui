import os

os.environ.setdefault("PPE_DETECTOR_PROVIDER", "mock")
os.environ.setdefault("PPE_ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient

from app.main import app

PREFIX = "/api/v1"


@pytest.fixture
def client():
    return TestClient(app)


def person(x1, y1, x2, y2, conf=0.95):
    return {"cls": "PERSON", "confidence": conf, "bbox": [x1, y1, x2, y2]}


def ppe(cls, x1, y1, x2, y2, conf=0.9):
    return {"cls": cls, "confidence": conf, "bbox": [x1, y1, x2, y2]}


def frame(*detections):
    return {"detections": list(detections)}
