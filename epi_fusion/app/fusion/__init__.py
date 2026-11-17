from app.config import Settings
from app.fusion.service import FusionService, IngestResult, ValidationError
from app.identity import (
    IdentityResolver,
    PermissiveEmployeeDirectory,
    build_identity_resolver,
)
from app.identity.resolver import EmployeeDirectory
from app.infrastructure import (
    AnonymousRepository,
    Clock,
    ConflictRepository,
    InMemoryEventBus,
    ObservationRepository,
    StateRepository,
    VisibilityProfileRepository,
)


def build_fusion_service(
    settings: Settings,
    clock: Clock | None = None,
    directory: EmployeeDirectory | None = None,
    event_bus: InMemoryEventBus | None = None,
) -> FusionService:
    clock = clock or Clock()
    directory = directory or PermissiveEmployeeDirectory()
    resolver: IdentityResolver = build_identity_resolver(
        settings.identity_resolver, directory, settings.identity_confidence_threshold
    )
    return FusionService(
        settings=settings,
        resolver=resolver,
        clock=clock,
        event_bus=event_bus or InMemoryEventBus(),
        observations=ObservationRepository(),
        states=StateRepository(),
        anonymous=AnonymousRepository(),
        conflicts=ConflictRepository(),
        visibility=VisibilityProfileRepository(),
    )


__all__ = ["FusionService", "IngestResult", "ValidationError", "build_fusion_service"]
