from __future__ import annotations

from typing import Optional

from pydantic import field_validator, model_validator, BaseModel, Field

from app.domain.enums import PPEType, SafetyCheckStatus, TrackerStatus, TrackerTechnology


class RegisterTrackerIn(BaseModel):
    technology: TrackerTechnology = TrackerTechnology.MOCK
    tracker_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class UpdateTrackerIn(BaseModel):
    status: Optional[TrackerStatus] = None
    metadata: Optional[dict] = None


class RegisterPPEAssetIn(BaseModel):
    ppe_type: PPEType
    tracker_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class AssignPPEIn(BaseModel):
    employee_id: str


class RegisterAreaIn(BaseModel):
    area_id: str
    name: str
    type: str = "GENERIC"
    description: str = ""


class RegisterReaderIn(BaseModel):
    area_id: str
    technology: TrackerTechnology = TrackerTechnology.MOCK
    reader_id: Optional[str] = None


class RegisterCheckpointIn(BaseModel):
    area_id: str
    name: str
    checkpoint_id: Optional[str] = None
    camera_id: Optional[str] = None
    reader_id: Optional[str] = None


class SimulateLocationIn(BaseModel):
    tracker_id: str
    area_id: str
    signal_strength: float = 0.9


class SimulateBatteryIn(BaseModel):
    tracker_id: str
    level: float


class SimulateOfflineIn(BaseModel):
    tracker_id: str


class SafetyCheckIn(BaseModel):
    employee_id: Optional[str] = None
    area_id: str
    checkpoint_id: str
    status: SafetyCheckStatus
    camera_id: Optional[str] = None
    evaluation_id: Optional[str] = None
    detected_ppe: list[str] = Field(default_factory=list)
    missing_ppe: list[str] = Field(default_factory=list)


class InconsistencyCheckIn(BaseModel):
    employee_id: str
    expected_area_id: str
    ppe_id: str


class CameraIn(BaseModel):
    """Corpo de criação/edição de câmera. Setor e tipo são validados (nunca adivinhamos)."""
    camera_id: Optional[str] = None   # obrigatório na criação; na edição vem da URL
    name: str
    sector: Optional[str] = None
    kind: str = "INTERNA"
    pos: dict = {"x": 50.0, "y": 50.0}
    active: bool = True
    example: bool = False
    latitude: Optional[float] = None    # graus decimais (-90..90); informe junto com a longitude
    longitude: Optional[float] = None   # graus decimais (-180..180)

    @model_validator(mode="after")
    def _geo(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("informe latitude e longitude juntas (ou nenhuma)")
        if self.latitude is not None:
            if not (-90 <= self.latitude <= 90):
                raise ValueError("latitude deve estar entre -90 e 90")
            if not (-180 <= self.longitude <= 180):
                raise ValueError("longitude deve estar entre -180 e 180")
        return self

    @field_validator("sector")
    @classmethod
    def _sector(cls, v):
        from app.domain.sectors import SECTOR_CODES
        if v is None or str(v).strip() == "":
            return None
        v = str(v).strip().upper()
        if v not in SECTOR_CODES:
            raise ValueError(f"setor desconhecido: {v!r}. Use um de {list(SECTOR_CODES)}")
        return v

    @field_validator("kind")
    @classmethod
    def _kind(cls, v):
        from app.domain.sectors import CAMERA_KINDS
        v = str(v).strip().upper()
        if v not in CAMERA_KINDS:
            raise ValueError(f"tipo inválido: {v!r}. Use um de {list(CAMERA_KINDS)}")
        return v

    @field_validator("pos")
    @classmethod
    def _pos(cls, v):
        try:
            x, y = float(v["x"]), float(v["y"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("pos precisa ter x e y numéricos")
        if not (0 <= x <= 100 and 0 <= y <= 100):
            raise ValueError("pos.x e pos.y devem estar entre 0 e 100 (% do mapa)")
        return {"x": x, "y": y}

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        if not str(v).strip():
            raise ValueError("name não pode ser vazio")
        return str(v).strip()
