"""
TrackerService - o coracao do epi_tracker.

Principio central (secao 6, 16, 23, 24 do pedido): este servico NUNCA
decide conformidade. Ele so registra trackers/EPIs/areas/checkpoints,
simula/recebe observacoes de localizacao, aplica TTL, detecta
inconsistencias (sem transforma-las em violacao), e representa Safety
Checks que foram decididos em outro lugar (Rules Engine, fora deste
modulo nesta fase).
"""
from __future__ import annotations

from typing import Optional

from app.domain.enums import (
    InconsistencyType,
    LocationState,
    ObservationStatus,
    PPEAssetStatus,
    PPEType,
    SafetyCheckStatus,
    TrackerStatus,
    TrackerTechnology,
)
from app.domain.models import (
    Camera,
    CameraAlreadyRegisteredError,
    CameraNotFoundError,
    Area,
    LocationInconsistency,
    LocationReader,
    PPEAsset,
    SafetyCheck,
    SafetyCheckpoint,
    Tracker,
    TrackerAlreadyRegisteredError,
    TrackerObservation,
    location_state,
)
from app.infrastructure.clock import Clock
from app.infrastructure.event_bus import EventType, InMemoryEventBus
from app.infrastructure.repositories import (
    AreaRepository,
    CameraRepository,
    CheckpointRepository,
    InconsistencyRepository,
    ObservationRepository,
    PPEAssetRepository,
    ReaderRepository,
    SafetyCheckRepository,
    TrackerRepository,
)
from app.observability.logging import log_event
from app.observability.metrics import TrackerMetrics


class TrackerNotFoundError(Exception):
    pass


class PPEAssetNotFoundError(Exception):
    pass


class AreaNotFoundError(Exception):
    pass


class ReaderNotFoundError(Exception):
    pass


class CheckpointNotFoundError(Exception):
    pass


class TrackerService:
    def __init__(
        self,
        clock: Clock,
        event_bus: InMemoryEventBus,
        metrics: TrackerMetrics,
        location_provider,
        fresh_seconds: float = 10.0,
        ttl_seconds: float = 30.0,
        low_battery_threshold: float = 0.15,
        cameras_file: Optional[str] = None,
    ) -> None:
        self._clock = clock
        self._bus = event_bus
        self._metrics = metrics
        self._provider = location_provider
        self._fresh_seconds = fresh_seconds
        self._ttl_seconds = ttl_seconds
        self._low_battery_threshold = low_battery_threshold

        self._trackers = TrackerRepository()
        self._ppe_assets = PPEAssetRepository()
        self._areas = AreaRepository()
        self._cameras = CameraRepository(cameras_file)
        self._readers = ReaderRepository()
        self._checkpoints = CheckpointRepository()
        self._observations = ObservationRepository()
        self._safety_checks = SafetyCheckRepository()
        self._inconsistencies = InconsistencyRepository()
        # employee_id -> area_id atual (para EMPLOYEE_ENTERED_AREA/EXITED_AREA - seção 12/13)
        self._employee_current_area: dict[str, str] = {}

    # ------------------------------------------------------------------ #
    # Trackers (seção 14, 26)
    # ------------------------------------------------------------------ #
    def register_tracker(self, technology: TrackerTechnology, tracker_id: Optional[str] = None,
                          metadata: Optional[dict] = None) -> Tracker:
        tid = tracker_id or self._trackers.ids.next_id()
        if self._trackers.exists(tid):
            raise TrackerAlreadyRegisteredError(f"Tracker {tid} já registrado.")
        tracker = Tracker(tracker_id=tid, technology=technology, registered_at=self._clock.now(),
                           metadata=metadata or {})
        self._trackers.add(tid, tracker)
        self._metrics.record_tracker_registered()
        log_event("TRACKER_REGISTERED", tracker_id=tid, technology=technology.value)
        return tracker

    def get_tracker(self, tracker_id: str) -> Tracker:
        tracker = self._trackers.get(tracker_id)
        if tracker is None:
            raise TrackerNotFoundError(f"Tracker {tracker_id} não encontrado.")
        return tracker

    def list_trackers(self) -> list[Tracker]:
        return self._trackers.list()

    def update_tracker(self, tracker_id: str, status: Optional[TrackerStatus] = None,
                        metadata: Optional[dict] = None) -> Tracker:
        tracker = self.get_tracker(tracker_id)
        if status is not None and status != tracker.status:
            self._metrics.record_status_change(tracker.status.value, status.value)
            tracker.status = status
        if metadata is not None:
            tracker.metadata.update(metadata)
        return tracker

    # ------------------------------------------------------------------ #
    # PPE Assets (seção 15, 16)
    # ------------------------------------------------------------------ #
    def register_ppe_asset(self, ppe_type: PPEType, tracker_id: Optional[str] = None,
                            metadata: Optional[dict] = None) -> PPEAsset:
        if tracker_id is not None:
            self.get_tracker(tracker_id)  # valida existência — levanta TrackerNotFoundError se não existir
        pid = self._ppe_assets.ids.next_id()
        asset = PPEAsset(ppe_id=pid, ppe_type=ppe_type, tracker_id=tracker_id,
                          registered_at=self._clock.now(), metadata=metadata or {})
        self._ppe_assets.add(pid, asset)
        log_event("PPE_ASSET_REGISTERED", ppe_id=pid, ppe_type=ppe_type.value)
        return asset

    def get_ppe_asset(self, ppe_id: str) -> PPEAsset:
        asset = self._ppe_assets.get(ppe_id)
        if asset is None:
            raise PPEAssetNotFoundError(f"PPE {ppe_id} não encontrado.")
        return asset

    def list_ppe_assets(self) -> list[PPEAsset]:
        return self._ppe_assets.list()

    def assign_ppe_to_employee(self, ppe_id: str, employee_id: str) -> PPEAsset:
        """ASSIGNED != WORN (seção 16) — só registra a atribuição
        administrativa. Uso real continua sendo provado pela câmera, em
        outro módulo."""
        asset = self.get_ppe_asset(ppe_id)
        asset.employee_id = employee_id
        asset.status = PPEAssetStatus.ASSIGNED
        asset.assigned_at = self._clock.now()
        log_event("PPE_ASSIGNED", ppe_id=ppe_id, employee_id=employee_id)
        return asset

    # ------------------------------------------------------------------ #
    # Areas, Readers, Checkpoints (seção 17, 9, 26)
    # ------------------------------------------------------------------ #
    def register_area(self, area_id: str, name: str, type: str = "GENERIC",
                       description: str = "") -> Area:
        area = Area(area_id=area_id, name=name, type=type, description=description)
        self._areas.add(area_id, area)
        log_event("AREA_REGISTERED", area_id=area_id)
        return area

    def get_area(self, area_id: str) -> Area:
        area = self._areas.get(area_id)
        if area is None:
            raise AreaNotFoundError(f"Área {area_id} não encontrada.")
        return area

    def list_areas(self) -> list[Area]:
        return self._areas.list()

    # ------------------------------------------------------------------ #
    # Câmeras (cadastro administrativo; a tela Câmeras lê daqui)
    # ------------------------------------------------------------------ #
    def register_camera(self, camera_id: str, name: str, sector=None, kind: str = "INTERNA",
                        pos_x: float = 50.0, pos_y: float = 50.0, active: bool = True,
                        example: bool = False) -> Camera:
        if self._cameras.exists(camera_id):
            raise CameraAlreadyRegisteredError(f"Câmera {camera_id} já cadastrada.")
        cam = Camera(camera_id=camera_id, name=name, sector=sector, kind=kind,
                     pos_x=pos_x, pos_y=pos_y, active=active, example=example)
        self._cameras.add(camera_id, cam)
        self._cameras.save()
        log_event("CAMERA_REGISTERED", camera_id=camera_id, sector=sector, kind=kind)
        return cam

    def get_camera(self, camera_id: str) -> Camera:
        cam = self._cameras.get(camera_id)
        if cam is None:
            raise CameraNotFoundError(f"Câmera {camera_id} não encontrada.")
        return cam

    @property
    def cameras_loaded_from_file(self) -> bool:
        return self._cameras.loaded_from_file

    def list_cameras(self) -> list[Camera]:
        return sorted(self._cameras.list(), key=lambda c: c.camera_id)

    def update_camera(self, camera_id: str, name: str, sector=None, kind: str = "INTERNA",
                      pos_x: float = 50.0, pos_y: float = 50.0, active: bool = True,
                      example: bool = False) -> Camera:
        cam = self.get_camera(camera_id)
        cam.name, cam.sector, cam.kind = name, sector, kind
        cam.pos_x, cam.pos_y, cam.active, cam.example = pos_x, pos_y, active, example
        self._cameras.save()
        log_event("CAMERA_UPDATED", camera_id=camera_id, sector=sector, kind=kind)
        return cam

    def delete_camera(self, camera_id: str) -> None:
        self.get_camera(camera_id)
        self._cameras.remove(camera_id)
        self._cameras.save()
        log_event("CAMERA_DELETED", camera_id=camera_id)

    def register_reader(self, area_id: str, technology: TrackerTechnology,
                         reader_id: Optional[str] = None) -> LocationReader:
        self.get_area(area_id)  # valida existência
        rid = reader_id or self._readers.ids.next_id()
        reader = LocationReader(reader_id=rid, area_id=area_id, technology=technology,
                                 installed_at=self._clock.now())
        self._readers.add(rid, reader)
        return reader

    def get_reader(self, reader_id: str) -> LocationReader:
        reader = self._readers.get(reader_id)
        if reader is None:
            raise ReaderNotFoundError(f"Reader {reader_id} não encontrado.")
        return reader

    def list_readers(self) -> list[LocationReader]:
        return self._readers.list()

    def register_checkpoint(self, area_id: str, name: str, checkpoint_id: Optional[str] = None,
                             camera_id: Optional[str] = None, reader_id: Optional[str] = None) -> SafetyCheckpoint:
        self.get_area(area_id)
        if reader_id is not None:
            self.get_reader(reader_id)
        cid = checkpoint_id or self._checkpoints.ids.next_id()
        checkpoint = SafetyCheckpoint(checkpoint_id=cid, area_id=area_id, name=name,
                                       camera_id=camera_id, reader_id=reader_id)
        self._checkpoints.add(cid, checkpoint)
        return checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> SafetyCheckpoint:
        checkpoint = self._checkpoints.get(checkpoint_id)
        if checkpoint is None:
            raise CheckpointNotFoundError(f"Checkpoint {checkpoint_id} não encontrado.")
        return checkpoint

    def list_checkpoints(self) -> list[SafetyCheckpoint]:
        return self._checkpoints.list()

    # ------------------------------------------------------------------ #
    # Observações de localização (seção 18, 19, 25)
    # ------------------------------------------------------------------ #
    def poll_provider(self, tracker_id: str) -> TrackerObservation:
        """Consulta o provider (mock ou, futuramente, BLE/RFID/UWB real) e
        registra uma TrackerObservation a partir do que ele responder —
        incluindo o caso de tracker desconhecido (seção 25/18)."""
        tracker = self.get_tracker(tracker_id)  # levanta se não registrado NO SERVIÇO
        reading = self._provider.read_location(tracker_id)

        now = self._clock.now()
        if reading is None:
            # UNKNOWN_TRACKER do PONTO DE VISTA DO PROVIDER (nunca simulado) —
            # diferente de tracker não registrado no serviço, que já barrou acima.
            obs = self._record_observation(tracker, area_id=tracker.last_area_id or "UNKNOWN",
                                            status=ObservationStatus.UNKNOWN, now=now)
            return obs

        if reading.get("offline"):
            if tracker.status != TrackerStatus.OFFLINE:
                self._metrics.record_status_change(tracker.status.value, TrackerStatus.OFFLINE.value)
                tracker.status = TrackerStatus.OFFLINE
                self._bus.publish(EventType.TRACKER_OFFLINE, {"tracker_id": tracker_id})
                log_event("TRACKER_OFFLINE", tracker_id=tracker_id)
            return self._record_observation(tracker, area_id=tracker.last_area_id or "UNKNOWN",
                                             status=ObservationStatus.NOT_DETECTED, now=now)

        battery = reading.get("battery_level")
        if battery is not None:
            tracker.battery_level = battery
            was_low = tracker.status == TrackerStatus.LOW_BATTERY
            is_low = battery < self._low_battery_threshold
            if is_low and not was_low:
                self._metrics.record_status_change(tracker.status.value, TrackerStatus.LOW_BATTERY.value)
                tracker.status = TrackerStatus.LOW_BATTERY
                self._bus.publish(EventType.TRACKER_LOW_BATTERY, {"tracker_id": tracker_id, "battery_level": battery})
                log_event("TRACKER_LOW_BATTERY", tracker_id=tracker_id, battery_level=battery)
            elif not is_low and was_low:
                self._metrics.record_status_change(tracker.status.value, TrackerStatus.ACTIVE.value)
                tracker.status = TrackerStatus.ACTIVE

        area_id = reading.get("area_id")
        if area_id is None:
            return self._record_observation(tracker, area_id=tracker.last_area_id or "UNKNOWN",
                                              status=ObservationStatus.UNKNOWN, now=now)

        previous_area = tracker.last_area_id
        obs = self._record_observation(tracker, area_id=area_id, status=ObservationStatus.DETECTED,
                                        now=now, signal_strength=reading.get("signal_strength"))
        tracker.last_area_id = area_id
        tracker.last_seen_at = now
        if tracker.status in (TrackerStatus.UNKNOWN, TrackerStatus.OFFLINE):
            # Voltou a responder com localização: deixa de estar offline.
            if tracker.status == TrackerStatus.OFFLINE:
                self._metrics.record_status_change(TrackerStatus.OFFLINE.value, TrackerStatus.ACTIVE.value)
            tracker.status = TrackerStatus.ACTIVE

        self._bus.publish(EventType.TRACKER_LOCATION_UPDATED, {"tracker_id": tracker_id, "area_id": area_id})
        if previous_area and previous_area != area_id:
            self._bus.publish(EventType.TRACKER_EXITED_AREA, {"tracker_id": tracker_id, "area_id": previous_area})
            self._bus.publish(EventType.TRACKER_ENTERED_AREA, {"tracker_id": tracker_id, "area_id": area_id})
        elif previous_area is None:
            self._bus.publish(EventType.TRACKER_ENTERED_AREA, {"tracker_id": tracker_id, "area_id": area_id})

        return obs

    def _record_observation(self, tracker: Tracker, area_id: str, status: ObservationStatus, now,
                             signal_strength: Optional[float] = None) -> TrackerObservation:
        oid = self._observations.ids.next_id()
        ppe_asset = next((a for a in self._ppe_assets.list() if a.tracker_id == tracker.tracker_id), None)
        obs = TrackerObservation(
            observation_id=oid, tracker_id=tracker.tracker_id,
            reader_id=self._reader_id_for_area(area_id), area_id=area_id, timestamp=now,
            ppe_id=ppe_asset.ppe_id if ppe_asset else None,
            ppe_type=ppe_asset.ppe_type if ppe_asset else None,
            employee_id=ppe_asset.employee_id if ppe_asset else None,
            signal_strength=signal_strength, status=status,
        )
        self._observations.add(oid, obs)
        self._metrics.record_observation(area_id)
        self._bus.publish(EventType.TRACKER_DETECTED, {"tracker_id": tracker.tracker_id, "area_id": area_id})
        return obs

    def _reader_id_for_area(self, area_id: str) -> str:
        for reader in self._readers.list():
            if reader.area_id == area_id:
                return reader.reader_id
        return "UNKNOWN"

    def get_tracker_location(self, tracker_id: str) -> dict:
        """Seção 19 — nunca afirma presença permanente. Classifica a última
        observação em CURRENT/LAST_KNOWN/EXPIRED conforme o TTL."""
        self.get_tracker(tracker_id)
        latest = self._observations.latest_for_tracker(tracker_id)
        if latest is None:
            return {"tracker_id": tracker_id, "state": LocationState.EXPIRED.value, "area_id": None,
                     "last_observation": None}
        state = location_state(latest, self._clock.now(), self._fresh_seconds, self._ttl_seconds)
        if state == LocationState.EXPIRED:
            self._metrics.record_expiration()
            self._bus.publish(EventType.TRACKER_LOCATION_EXPIRED, {"tracker_id": tracker_id})
        return {
            "tracker_id": tracker_id, "state": state.value,
            "area_id": latest.area_id if state != LocationState.EXPIRED else None,
            "last_observation": latest.to_dict(),
        }

    def get_tracker_history(self, tracker_id: str) -> list[dict]:
        self.get_tracker(tracker_id)
        return [obs.to_dict() for obs in self._observations.history_for_tracker(tracker_id)]

    def get_trackers_in_area(self, area_id: str) -> list[dict]:
        """`GET /areas/{id}/trackers` — só trackers cuja última leitura
        NAQUELA área ainda está dentro do TTL (não LAST_KNOWN/EXPIRED de
        uma área diferente onde ele esteja agora)."""
        self.get_area(area_id)
        now = self._clock.now()
        result = []
        for obs in self._observations.latest_for_area(area_id):
            latest_overall = self._observations.latest_for_tracker(obs.tracker_id)
            if latest_overall is not obs:
                continue  # o tracker já se moveu para outra área depois dessa leitura
            state = location_state(obs, now, self._fresh_seconds, self._ttl_seconds)
            if state != LocationState.EXPIRED:
                result.append({"tracker_id": obs.tracker_id, "state": state.value, "observation": obs.to_dict()})
        return result

    # ------------------------------------------------------------------ #
    # Safety Check (seção 27) — representa, não decide
    # ------------------------------------------------------------------ #
    def record_safety_check(
        self, employee_id: Optional[str], area_id: str, checkpoint_id: str, status: SafetyCheckStatus,
        camera_id: Optional[str] = None, evaluation_id: Optional[str] = None,
        detected_ppe: Optional[list] = None, missing_ppe: Optional[list] = None,
    ) -> SafetyCheck:
        self.get_area(area_id)
        self.get_checkpoint(checkpoint_id)
        self._bus.publish(EventType.SAFETY_CHECK_STARTED,
                           {"employee_id": employee_id, "area_id": area_id, "checkpoint_id": checkpoint_id})

        check_id = self._safety_checks.ids.next_id()
        check = SafetyCheck(
            check_id=check_id, employee_id=employee_id, area_id=area_id, checkpoint_id=checkpoint_id,
            timestamp=self._clock.now(), status=status, camera_id=camera_id, evaluation_id=evaluation_id,
            detected_ppe=detected_ppe or [], missing_ppe=missing_ppe or [],
        )
        self._safety_checks.add(check_id, check)
        self._metrics.record_safety_check(status.value)

        if employee_id:
            previous_area = self._employee_current_area.get(employee_id)
            if previous_area and previous_area != area_id:
                self._bus.publish(EventType.EMPLOYEE_EXITED_AREA, {"employee_id": employee_id, "area_id": previous_area})
            if previous_area != area_id:
                self._bus.publish(EventType.EMPLOYEE_ENTERED_AREA, {"employee_id": employee_id, "area_id": area_id})
            self._employee_current_area[employee_id] = area_id

        self._bus.publish(EventType.SAFETY_CHECK_COMPLETED, {"check_id": check_id, "status": status.value})
        log_event("SAFETY_CHECK_COMPLETED", check_id=check_id, employee_id=employee_id, status=status.value)
        return check

    def get_employee_history(self, employee_id: str) -> list[dict]:
        return [c.to_dict() for c in self._safety_checks.history_for_employee(employee_id)]

    # ------------------------------------------------------------------ #
    # Inconsistência de localização (seção 20) — nunca vira violação sozinha
    # ------------------------------------------------------------------ #
    def check_location_inconsistency(self, employee_id: str, expected_area_id: str,
                                       ppe_id: str) -> Optional[LocationInconsistency]:
        """Compara onde a câmera confirmou que o funcionário está com onde
        o tracker do EPI atribuído a ele diz estar. Diferença -> preserva
        como POSSIBLE_INCONSISTENCY, NUNCA gera incidente por conta própria
        (isso é decisão do Rules/Incident Service, em outra fase)."""
        asset = self.get_ppe_asset(ppe_id)
        if asset.tracker_id is None:
            return None  # sem tracker associado, nada a comparar
        location = self.get_tracker_location(asset.tracker_id)
        tracker_area = location["area_id"]
        if tracker_area is None or tracker_area == expected_area_id:
            return None
        inconsistency = LocationInconsistency(
            type=InconsistencyType.POSSIBLE_INCONSISTENCY, employee_id=employee_id,
            area_id=expected_area_id, ppe_id=ppe_id, ppe_area_id=tracker_area, timestamp=self._clock.now(),
        )
        inconsistency_id = self._inconsistencies.ids.next_id()
        self._inconsistencies.add(inconsistency_id, inconsistency)
        self._bus.publish(EventType.POSSIBLE_PPE_LOCATION_INCONSISTENCY, inconsistency.to_dict())
        log_event("POSSIBLE_PPE_LOCATION_INCONSISTENCY", employee_id=employee_id, ppe_id=ppe_id,
                   expected_area=expected_area_id, actual_area=tracker_area)
        return inconsistency

    def list_inconsistencies(self) -> list[LocationInconsistency]:
        """Fase 3.8B — histórico persistido (ver InconsistencyRepository)."""
        return self._inconsistencies.list()

    # ------------------------------------------------------------------ #
    # Contrato de compatibilidade com o Fusion (seção 22, 26) — só monta o
    # payload; NÃO chama o Fusion de verdade nesta fase.
    # ------------------------------------------------------------------ #
    def build_fusion_compatible_observation(self, tracker_id: str) -> dict:
        """Formato que uma futura integração enviaria ao Fusion como
        PPE_LOCATION_OBSERVATION (seção 22) — validável/testável sem que o
        Fusion precise estar rodando."""
        location = self.get_tracker_location(tracker_id)
        tracker = self.get_tracker(tracker_id)
        asset = next((a for a in self._ppe_assets.list() if a.tracker_id == tracker_id), None)
        return {
            "source": "tracker",
            "tracker_id": tracker_id,
            "ppe_id": asset.ppe_id if asset else None,
            "ppe_type": asset.ppe_type.value if asset else None,
            "employee_id_assigned": asset.employee_id if asset else None,  # ASSIGNED, não WORN
            "area_id": location["area_id"],
            "location_state": location["state"],
            "confidence": location["last_observation"]["confidence"] if location["last_observation"] else None,
            "timestamp": location["last_observation"]["timestamp"] if location["last_observation"] else None,
        }

    # ------------------------------------------------------------------ #
    # Agregações de leitura para a interface (Fase 3.8B) — nenhuma decide
    # nada; só juntam dados que já existiam em repositórios separados.
    # Não duplicam a lógica de negócio de nenhum outro método.
    # ------------------------------------------------------------------ #
    def list_employees(self) -> list[dict]:
        """Deriva a lista de funcionários conhecidos a partir de duas
        fontes que já existiam: EPIs atribuídos e histórico de Safety
        Checks. Não há uma entidade `Employee` própria neste módulo — a
        identidade continua sendo responsabilidade do epi_identity, este
        módulo só sabe "a quem" um EPI foi atribuído e "quem" passou por
        um checkpoint."""
        employee_ids: set[str] = set()
        for asset in self._ppe_assets.list():
            if asset.employee_id:
                employee_ids.add(asset.employee_id)
        for check in self._safety_checks.list():
            if check.employee_id:
                employee_ids.add(check.employee_id)

        result = []
        for employee_id in sorted(employee_ids):
            result.append(self.get_employee_summary(employee_id))
        return result

    def get_employee_summary(self, employee_id: str) -> dict:
        history = self._safety_checks.history_for_employee(employee_id)
        latest_check = history[-1] if history else None
        assigned_ppe = [a for a in self._ppe_assets.list() if a.employee_id == employee_id]

        ppe_summary = []
        for asset in assigned_ppe:
            location = self.get_tracker_location(asset.tracker_id) if asset.tracker_id else None
            ppe_summary.append({
                "ppe_id": asset.ppe_id, "ppe_type": asset.ppe_type.value,
                "tracker_id": asset.tracker_id,
                "area_id": location["area_id"] if location else None,
                "location_state": location["state"] if location else None,
            })

        return {
            "employee_id": employee_id,
            "current_area_id": self._employee_current_area.get(employee_id),
            "last_check": latest_check.to_dict() if latest_check else None,
            "assigned_ppe": ppe_summary,
            "history": [c.to_dict() for c in history],
        }

    def list_events(self, limit: int = 100) -> list[dict]:
        """Fase 3.8B — expõe o histórico do EventBus (que já existia desde
        a Fase 3.8A, mas só em memória, sem endpoint HTTP) para a tela de
        Histórico (seção 24). Nenhuma lógica nova, só serialização."""
        history = self._bus.history()
        events = [{"event": et.value, "payload": payload} for et, payload in history]
        return events[-limit:]
