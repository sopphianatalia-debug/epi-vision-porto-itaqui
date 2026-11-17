"""
Repositorios em memoria - um por entidade, todos com o mesmo padrao simples
(dict indexado por id + gerador de id sequencial com prefixo). Mesmo estilo
de epi_incident/app/infrastructure/repository.py.
"""
from __future__ import annotations

import json
import os

from itertools import count
from typing import Dict, Generic, Optional, TypeVar

T = TypeVar("T")


class IdGenerator:
    def __init__(self, prefix: str, width: int = 6) -> None:
        self._prefix = prefix
        self._width = width
        self._counter = count(1)

    def next_id(self) -> str:
        n = next(self._counter)
        return f"{self._prefix}-{n:0{self._width}d}"


class InMemoryRepository(Generic[T]):
    """Repositorio generico por id de string (usado para Area, que ja tem
    id fornecido pelo cliente, nao gerado)."""

    def __init__(self) -> None:
        self._store: Dict[str, T] = {}

    def add(self, entity_id: str, entity: T) -> T:
        self._store[entity_id] = entity
        return entity

    def get(self, entity_id: str) -> Optional[T]:
        return self._store.get(entity_id)

    def list(self) -> list:
        return list(self._store.values())

    def exists(self, entity_id: str) -> bool:
        return entity_id in self._store

    def remove(self, entity_id: str) -> bool:
        return self._store.pop(entity_id, None) is not None


class TrackerRepository(InMemoryRepository):
    def __init__(self) -> None:
        super().__init__()
        self.ids = IdGenerator("TRACKER")


class PPEAssetRepository(InMemoryRepository):
    def __init__(self) -> None:
        super().__init__()
        self.ids = IdGenerator("PPE")


class AreaRepository(InMemoryRepository):
    pass  # area_id fornecido pelo cliente (ex.: "PATIO-02"), sem geracao


class CameraRepository(InMemoryRepository):
    """camera_id fornecido pelo cliente (ex.: "CAM-ENTRY-02"). Se `path` for dado, o cadastro
    é gravado em JSON a cada mudança (escrita atômica) e relido ao iniciar."""

    def __init__(self, path: Optional[str] = None) -> None:
        super().__init__()
        self._path = path
        self.loaded_from_file = False
        if path and os.path.exists(path):
            self._load()

    def _load(self) -> None:
        from app.domain.models import Camera
        try:
            with open(self._path, encoding="utf-8") as fh:
                for d in json.load(fh):
                    pos = d.get("pos") or {}
                    cam = Camera(camera_id=d["camera_id"], name=d["name"], sector=d.get("sector"),
                                 kind=d.get("kind", "INTERNA"), pos_x=float(pos.get("x", 50)),
                                 pos_y=float(pos.get("y", 50)), active=bool(d.get("active", True)),
                                 example=bool(d.get("example", False)))
                    self._store[cam.camera_id] = cam
            self.loaded_from_file = True
        except (OSError, ValueError, KeyError, TypeError):
            # arquivo corrompido: guarda uma cópia e começa vazio (nunca derruba o serviço)
            try:
                os.replace(self._path, self._path + ".corrupt")
            except OSError:
                pass
            self._store.clear()

    def save(self) -> None:
        if not self._path:
            return
        os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump([c.to_dict() for c in self.list()], fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path)


class ReaderRepository(InMemoryRepository):
    def __init__(self) -> None:
        super().__init__()
        self.ids = IdGenerator("READER")


class CheckpointRepository(InMemoryRepository):
    def __init__(self) -> None:
        super().__init__()
        self.ids = IdGenerator("CHECKPOINT")


class ObservationRepository(InMemoryRepository):
    """Alem do indice por id, mantem um indice por tracker_id (ordenado por
    insercao = ordenado por tempo, ja que so inserimos observacoes novas)
    para responder rapido `GET /trackers/{id}/history` e `.../location`."""

    def __init__(self) -> None:
        super().__init__()
        self.ids = IdGenerator("OBS")
        self._by_tracker: Dict[str, list] = {}

    def add(self, entity_id, entity):
        super().add(entity_id, entity)
        self._by_tracker.setdefault(entity.tracker_id, []).append(entity)
        return entity

    def history_for_tracker(self, tracker_id: str) -> list:
        return list(self._by_tracker.get(tracker_id, []))

    def latest_for_tracker(self, tracker_id: str):
        history = self._by_tracker.get(tracker_id)
        return history[-1] if history else None

    def latest_for_area(self, area_id: str) -> list:
        """Ultima observacao conhecida de cada tracker que ja passou por
        essa area (para `GET /areas/{id}/trackers`)."""
        latest_by_tracker = {}
        for obs in self._store.values():
            if obs.area_id == area_id:
                current = latest_by_tracker.get(obs.tracker_id)
                if current is None or obs.timestamp > current.timestamp:
                    latest_by_tracker[obs.tracker_id] = obs
        return list(latest_by_tracker.values())


class InconsistencyRepository(InMemoryRepository):
    """Fase 3.8B — a Fase 3.8A já calculava LocationInconsistency sob
    demanda (POST /inconsistency-check), mas nunca guardava o resultado em
    lugar nenhum. A tela de Inconsistências (seção 23 do pedido) precisa de
    uma LISTA histórica, não só de uma checagem pontual — este repositório
    é a menor extensão possível para viabilizar isso, sem duplicar a
    lógica de detecção (que continua inteira em
    TrackerService.check_location_inconsistency)."""

    def __init__(self) -> None:
        super().__init__()
        self.ids = IdGenerator("INCONSISTENCY")


class SafetyCheckRepository(InMemoryRepository):
    def __init__(self) -> None:
        super().__init__()
        self.ids = IdGenerator("CHECK")
        self._by_employee: Dict[str, list] = {}

    def add(self, entity_id, entity):
        super().add(entity_id, entity)
        if entity.employee_id:
            self._by_employee.setdefault(entity.employee_id, []).append(entity)
        return entity

    def history_for_employee(self, employee_id: str) -> list:
        return list(self._by_employee.get(employee_id, []))
