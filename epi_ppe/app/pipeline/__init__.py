from app.association import PersonPPEAssociator
from app.config import Settings
from app.detection import build_detection_service
from app.pipeline.pipeline import DetectionEventService, PPEPipeline
from app.tracking import PersonTracker


def build_pipeline(settings: Settings, events: DetectionEventService | None = None) -> PPEPipeline:
    return PPEPipeline(
        detector=build_detection_service(settings),
        tracker=PersonTracker(
            iou_threshold=settings.tracker_iou_threshold,
            track_ttl_frames=settings.track_ttl_frames,
        ),
        associator=PersonPPEAssociator(
            containment_threshold=settings.association_containment_threshold,
            score_threshold=settings.association_score_threshold,
        ),
        events=events,
    )


__all__ = ["PPEPipeline", "DetectionEventService", "build_pipeline"]
