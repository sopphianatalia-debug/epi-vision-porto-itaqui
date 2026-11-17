from app.config import Settings
from app.recognition.factory import build_provider
from app.recognition.matching import MatchingEngine
from app.recognition.quality import QualityGate
from app.recognition.service import FaceRecognitionService, QualityTooLowError


def build_recognition_service(settings: Settings) -> FaceRecognitionService:
    return FaceRecognitionService(
        provider=build_provider(settings),
        quality_gate=QualityGate(settings.quality_threshold),
        matching_engine=MatchingEngine(
            similarity_threshold=settings.similarity_threshold,
            confidence_threshold=settings.confidence_threshold,
            ambiguity_margin=settings.ambiguity_margin,
        ),
    )


__all__ = [
    "FaceRecognitionService",
    "QualityTooLowError",
    "build_recognition_service",
]
