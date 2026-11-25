"""
RealCameraPipeline — Fase 3.7.

Orquestra, para cada frame de uma câmera real (ou simulada), a passagem
completa: Módulo 2 / epi_ppe (detecção+tracking+associação, consumido via
HTTP — POST /pipeline/process-frame, já existente, não reimplementado) ->
Observation Builder -> Identity (com cache) -> Fusion -> Rules -> Incident.

Todas as cinco chamadas de rede (Vision/Identity/Fusion/Rules/Incident) são
feitas passo a passo, cada uma no seu próprio try/except — não via
`bridge.identify_ingest_and_evaluate` (que já existe e cobre o caso
"tudo-ou-nada" dos testes de integração) — porque aqui, diferente de um
teste, uma falha em UM serviço não pode impedir o restante do frame de ser
processado nem derrubar o loop da câmera (seção 31 do pedido). Cada etapa
reaproveita as MESMAS funções de tradução de contrato que `bridge.py` já
tem (`identity_result_to_fusion_identity`, `build_rules_evaluate_payload`,
`enrich_violations_with_cameras`) — nada é duplicado, só a orquestração do
try/except é diferente.

Princípios respeitados (seção 4 do pedido):
- Este módulo NÃO decide conformidade, NÃO decide identidade, NÃO decide
  fusão — só encaminha, na ordem certa, para quem já decide isso.
- Falha de um serviço downstream nunca derruba o loop da câmera (seção 31).
- Nem todo frame aciona a cadeia completa (seção 17-18, 37) — controlado
  por `process_every_n_frames`. Como o Módulo 2 agora é consumido por HTTP
  (não mais em processo), a AMOSTRAGEM se aplica à cadeia inteira, incluindo
  a própria chamada de detecção — não só às etapas de negócio. Isso é o que
  a seção 37 pede explicitamente: "vídeo a 30 FPS, análise a 2-10/s".
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from app.bridge import (
    build_rules_evaluate_payload,
    enrich_violations_with_cameras,
    identity_result_to_fusion_identity,
)
from app.identity_cache import IdentityCache
from app.observation_builder import build_fusion_ppe, regions_cut_by_frame

logger = logging.getLogger("epi_pipeline")


EVIDENCE_MAX_RETRIES = 90   # quadros (~6 s) esperando uma imagem com luz suficiente antes de aceitar a que houver


@dataclass
class PipelineMetrics:
    """Seção 28 do pedido. Métricas próprias desta camada — não confundir
    com /fusion/metrics, /rules/metrics/snapshot etc., que continuam
    intactas e são responsabilidade de cada serviço."""

    frames_received: int = 0
    frames_processed: int = 0          # frames em que a cadeia completa rodou (não pulados)
    detections_total: int = 0          # pessoas detectadas, somado por frame processado
    observations_generated: int = 0    # observações enviadas ao Fusion
    identity_requests: int = 0         # chamadas reais a POST /recognition/match (sem contar cache)
    identity_cache_hits: int = 0
    identity_matches: int = 0
    identity_unmatched: int = 0
    fusion_updates: int = 0
    rules_evaluations: int = 0
    incidents_created: int = 0
    incidents_resolved: int = 0
    tracker_evidence_sent: int = 0    # evidências de localização de EPI enviadas ao Fusion
    errors_by_service: dict = field(default_factory=dict)
    pipeline_latency_ms_total: float = 0.0
    pipeline_latency_samples: int = 0

    @property
    def avg_pipeline_latency_ms(self) -> float:
        if self.pipeline_latency_samples == 0:
            return 0.0
        return round(self.pipeline_latency_ms_total / self.pipeline_latency_samples, 2)

    def record_error(self, service: str) -> None:
        self.errors_by_service[service] = self.errors_by_service.get(service, 0) + 1

    def snapshot(self) -> dict:
        return {
            "frames_received": self.frames_received,
            "frames_processed": self.frames_processed,
            "detections_total": self.detections_total,
            "observations_generated": self.observations_generated,
            "identity_requests": self.identity_requests,
            "identity_cache_hits": self.identity_cache_hits,
            "identity_matches": self.identity_matches,
            "identity_unmatched": self.identity_unmatched,
            "fusion_updates": self.fusion_updates,
            "rules_evaluations": self.rules_evaluations,
            "incidents_created": self.incidents_created,
            "tracker_evidence_sent": self.tracker_evidence_sent,
            "incidents_resolved": self.incidents_resolved,
            "errors_by_service": dict(self.errors_by_service),
            "pipeline_latency_ms_avg": self.avg_pipeline_latency_ms,
        }


class ServiceStatusBoard:
    """Seção 21 — status visual simples por serviço downstream."""

    SERVICES = ("vision", "identity", "fusion", "rules", "incident", "tracker")

    def __init__(self) -> None:
        self._status: dict[str, str] = {s: "UNKNOWN" for s in self.SERVICES}

    def mark_ok(self, service: str) -> None:
        self._status[service] = "ONLINE"

    def mark_error(self, service: str) -> None:
        self._status[service] = "ERROR"

    def snapshot(self) -> dict:
        return dict(self._status)


@dataclass
class PersonPipelineResult:
    """O que a camada de visualização (seção 20) precisa para desenhar o
    overlay de uma pessoa: identidade (já traduzida, nunca um status cru
    que possa ser mal-interpretado como confirmado), EPIs, conformidade."""

    person_track_id: str
    employee_id: Optional[str]
    identity_status: str
    identity_confidence: float
    identity_from_cache: bool
    ppe: dict[str, dict]
    overall_status: Optional[str]
    incident_actions: list[dict]

    @property
    def display_identity_label(self) -> str:
        """Seções 20/26: nunca mostrar um employee_id como confirmado a
        menos que o status seja MATCHED — mesmo que o Identity retorne um
        employee_id candidato em outros estados."""
        if self.identity_status == "MATCHED" and self.employee_id:
            return self.employee_id
        if self.identity_status == "LOW_CONFIDENCE":
            return "uncertain"
        if self.identity_status == "AMBIGUOUS":
            return "ambiguous"
        return "unknown"


class RealCameraPipeline:
    _PRIMARY_SWITCH_MARGIN = 0.15

    def __init__(
        self,
        vision_client: Any,
        identity_client: Any,
        fusion_client: Any,
        rules_client: Any,
        incident_client: Any,
        *,
        identity_cache: Optional[IdentityCache] = None,
        process_every_n_frames: int = 5,
        camera_visibility: Optional[dict[str, bool]] = None,
        area: str = "PATIO_CARGA",
        operation: str = "MOVIMENTACAO_CARGA",
        role: str = "OPERADOR",
        identity_seed_provider: Optional[Callable[[str, str], Optional[str]]] = None,
        clock: Callable[[], float] = time.monotonic,
        demo_ppe_override: Optional[dict[str, dict]] = None,
        use_real_images: bool = False,
        tracker_client: Any = None,
        tracker_area_id: Optional[str] = None,
        tracker_sync_interval_seconds: float = 2.0,
        single_identity_per_frame: bool = False,
        send_evidence: bool = False,
        face_recognition: bool = False,
        face_matched_ttl_seconds: float = 15.0,
        face_retry_seconds: float = 2.0,
    ) -> None:
        self._vision = vision_client
        self._identity = identity_client
        self._fusion = fusion_client
        self._rules = rules_client
        self._incident = incident_client
        self._identity_cache = identity_cache or IdentityCache()
        self._every_n = max(1, process_every_n_frames)
        self._camera_visibility = camera_visibility
        self._area = area
        self._operation = operation
        self._role = role
        # DEMO_MODE / provider mock: como o mock não deriva identidade da
        # imagem, algo precisa decidir qual "seed" mandar para /recognition/
        # match. Por padrão, ninguém é reconhecido (retorna None -> UNKNOWN);
        # ver camera_config.demo_employee_seed para o cenário de demonstração
        # com um funcionário pré-cadastrado.
        self._identity_seed_provider = identity_seed_provider or (lambda camera_id, track_id: None)
        self._clock = clock
        # DEMO_SCENARIO (seção 6 do pedido da Fase 3.7): permite forçar um
        # cenário controlado (ex.: {"helmet": {"status": "MISSING",
        # "confidence": 0.95}}) SÓ para fins de demonstração, sem tocar em
        # Rules Engine nem inventar a ausência dentro do YOLO. Aplicado
        # DEPOIS da detecção real, sobre o payload real — nunca no lugar
        # dela. Fica None (desligado) por padrão; nenhum teste ou uso normal
        # é afetado a menos que alguém passe isso explicitamente.
        self._demo_ppe_override = demo_ppe_override
        # Fase 3.7: quando True, `process_frame` espera uma imagem real
        # (array BGR do OpenCV) em vez do dict de cena mock/demo, e chama
        # `vision_client.process_frame_image` em vez de `process_frame`.
        self._use_real_images = use_real_images
        # Demonstração com identidade FIXA (um funcionário para qualquer
        # pessoa vista): sem isso, uma "pessoa" falsa (sombra, reflexo, mão)
        # herdaria o mesmo funcionário e manteria incidentes abertos mesmo
        # com o trabalhador real em conformidade. Com a flag, só a pessoa de
        # maior confiança do quadro recebe a identidade; as demais ficam NÃO
        # identificadas (e não são avaliadas), como numa câmera real.
        self._single_identity = single_identity_per_frame
        # Evidência em imagem: só o recorte da pessoa, ao abrir o incidente. Desligado por padrão.
        self._send_evidence = send_evidence
        # Reconhecimento facial real (opt-in): manda o recorte do rosto ao Identity; ignora o seed de demonstração.
        self._face_recognition = face_recognition
        self._face_matched_ttl = face_matched_ttl_seconds
        self._face_retry = face_retry_seconds
        self._evidence_pending: dict[str, int] = {}   # incidente -> quadros já tentados (esperando um quadro bom)
        self._evidence_best: dict[str, tuple] = {}    # incidente -> (brilho, recorte) do quadro mais claro até agora
        self._primary_track: Optional[str] = None

        self.metrics = PipelineMetrics()
        self.status = ServiceStatusBoard()
        self._frame_index = 0
        self.last_frame_processed = True

        # Evidência de LOCALIZAÇÃO de EPI (epi_tracker -> Fusion). Opcional:
        # sem tracker_client o comportamento é idêntico ao anterior. O
        # tracker nunca decide conformidade e sua falha nunca derruba o
        # frame — só deixa de haver essa evidência.
        self._tracker = tracker_client
        self._tracker_area_id = tracker_area_id
        self._tracker_sync_interval = tracker_sync_interval_seconds
        self._tracker_last_sync: dict[str, float] = {}
        self._camera_area_registered: set[str] = set()
        if tracker_client is None:
            self.status._status["tracker"] = "DISABLED"

    def process_frame(self, camera_id: str, frame: Any) -> list[PersonPipelineResult]:
        """`frame` é o dict de cena (mock/demo) OU uma imagem real (array
        BGR do OpenCV) se `use_real_images=True` foi passado ao construtor.
        A amostragem por `process_every_n_frames` acontece ANTES de
        qualquer chamada de rede — inclusive a de detecção — porque o
        Módulo 2 agora também é um serviço HTTP remoto (seção 37: evitar
        chamadas desnecessárias em todo frame, para qualquer serviço)."""
        self.metrics.frames_received += 1
        self._frame_index += 1

        if self._frame_index % self._every_n != 0:
            # Frame pulado pela amostragem: NÃO é "zero pessoas". Quem desenha
            # na tela deve manter o último resultado (ver last_frame_processed).
            self.last_frame_processed = False
            return []

        self.last_frame_processed = True
        self.metrics.frames_processed += 1
        start = self._clock()

        try:
            if self._use_real_images:
                vision_response = self._vision.process_frame_image(camera_id, frame)
            else:
                vision_response = self._vision.process_frame(camera_id, frame)
            self.status.mark_ok("vision")
        except Exception:
            self.status.mark_error("vision")
            self.metrics.record_error("vision")
            logger.exception("Falha ao consultar o Módulo 2 / Vision (camera=%s)", camera_id)
            return []

        person_results = vision_response.get("persons", [])
        self.metrics.detections_total += len(person_results)

        hw = getattr(frame, "shape", None)
        frame_size = (float(hw[1]), float(hw[0])) if hw is not None and len(hw) >= 2 else None
        primary_track = None
        if self._single_identity and person_results:
            present = {r["person_track_id"] for r in person_results}
            # "Pegajoso": mantém quem já era o principal enquanto ele estiver
            # no quadro (evita a identidade pular entre duas pessoas a cada frame).
            best = max(person_results, key=lambda r: r.get("person_confidence", 0.0))
            current = next((r for r in person_results if r["person_track_id"] == self._primary_track), None)
            # ...mas cede o lugar se outra pessoa for CLARAMENTE mais confiável
            # (uma "fantasma" que chegou primeiro não pode travar a identidade).
            if current is not None and best.get("person_confidence", 0.0) - current.get(
                    "person_confidence", 0.0) < self._PRIMARY_SWITCH_MARGIN:
                primary_track = self._primary_track
            else:
                primary_track = best["person_track_id"]
            self._primary_track = primary_track
        results = [self._process_person(camera_id, r, force_unidentified=(
            self._single_identity and r["person_track_id"] != primary_track), frame_size=frame_size, frame=frame)
            for r in person_results]
        elapsed_ms = (self._clock() - start) * 1000.0
        self.metrics.pipeline_latency_ms_total += elapsed_ms
        self.metrics.pipeline_latency_samples += 1
        return results

    def _process_person(self, camera_id: str, person_result: dict,
                        force_unidentified: bool = False,
                        frame_size: Optional[tuple[float, float]] = None,
                        frame: Any = None) -> PersonPipelineResult:
        track_id = person_result["person_track_id"]
        # Visibilidade deste quadro = perfil fixo da câmera + o que o
        # enquadramento corta para ESTA pessoa agora (ex.: cabeça fora do quadro).
        visibility = self._camera_visibility
        if frame_size is not None:
            cut = regions_cut_by_frame(person_result.get("person_bbox"), frame_size[0], frame_size[1])
            if cut:
                visibility = {**(self._camera_visibility or {}), **cut}
        ppe_payload = build_fusion_ppe(person_result, camera_can_see=visibility)
        if self._demo_ppe_override:
            # DEMO_SCENARIO — seção 6: aplicado por CIMA da detecção real,
            # nunca no lugar dela. O Rules Engine recebe exatamente o mesmo
            # payload que receberia de uma câmera real reportando essa
            # ausência; ele não sabe (nem precisa saber) que veio de um
            # override de demonstração. logger.info deixa isso rastreável.
            logger.info("DEMO_SCENARIO override aplicado (camera=%s track=%s): %s",
                        camera_id, track_id, self._demo_ppe_override)
            ppe_payload = {**ppe_payload, **self._demo_ppe_override}
        self.metrics.observations_generated += 1

        if force_unidentified:
            identity_fields, from_cache = (
                {"employee_id": None, "identity_status": "UNKNOWN", "identity_confidence": 0.0}, False)
        else:
            identity_fields, from_cache = self._resolve_identity(
                camera_id, track_id, frame, person_result.get("person_bbox"))
        if identity_fields is None:
            # Identity indisponível (erro) — ainda assim seguimos com a
            # pessoa como não identificada, em vez de travar o frame
            # inteiro (seção 31: erro não deve virar conformidade nem
            # travar a câmera).
            identity_fields = {"employee_id": None, "identity_status": "UNKNOWN", "identity_confidence": 0.0}

        if identity_fields["identity_status"] == "MATCHED":
            self.metrics.identity_matches += 1
        elif identity_fields["employee_id"] is None:
            self.metrics.identity_unmatched += 1

        overall_status = None
        incident_actions: list[dict] = []
        employee_id = identity_fields["employee_id"]

        try:
            self._fusion.ingest(
                camera_id=camera_id, person_track_id=track_id, ppe=ppe_payload,
                employee_id=employee_id, identity_status=identity_fields["identity_status"],
                identity_confidence=identity_fields["identity_confidence"],
            )
            self.status.mark_ok("fusion")
            self.metrics.fusion_updates += 1
            _log_event("FUSION_UPDATED", camera_id=camera_id, employee_id=employee_id)
        except Exception:
            self.status.mark_error("fusion")
            self.metrics.record_error("fusion")
            logger.exception("Falha ao atualizar o Fusion (camera=%s track=%s)", camera_id, track_id)
            return PersonPipelineResult(
                person_track_id=track_id, employee_id=employee_id,
                identity_status=identity_fields["identity_status"],
                identity_confidence=identity_fields["identity_confidence"], identity_from_cache=from_cache,
                ppe=ppe_payload, overall_status=None, incident_actions=[],
            )

        if employee_id and identity_fields["identity_status"] == "MATCHED":
            self._sync_tracker_evidence(camera_id, employee_id)

        if employee_id:
            try:
                fusion_state = self._fusion.get_employee_state(employee_id)
            except Exception:
                self.status.mark_error("fusion")
                self.metrics.record_error("fusion")
                fusion_state = None
        else:
            fusion_state = None

        try:
            if fusion_state is not None:
                payload = build_rules_evaluate_payload(
                    fusion_state, area=self._area, operation=self._operation, role=self._role,
                )
            else:
                payload = {
                    "employee_id": employee_id, "identity_status": identity_fields["identity_status"],
                    "area": self._area, "operation": self._operation, "role": self._role,
                    "evaluation_id": None, "ppe": {},
                }
            evaluation = self._rules.evaluate(
                employee_id=payload["employee_id"], ppe=payload["ppe"], area=payload["area"],
                operation=payload["operation"], role=payload["role"],
                identity_status=payload["identity_status"], evaluation_id=payload.get("evaluation_id"),
            )
            self.status.mark_ok("rules")
            self.metrics.rules_evaluations += 1
            overall_status = evaluation["overall_status"]
            _log_event("COMPLIANCE_EVALUATED", camera_id=camera_id, employee_id=employee_id,
                       status=overall_status)
            if overall_status == "NON_COMPLIANT":
                _log_event("VIOLATION_DETECTED", camera_id=camera_id, employee_id=employee_id)
        except Exception:
            self.status.mark_error("rules")
            self.metrics.record_error("rules")
            logger.exception("Falha ao avaliar regras (camera=%s track=%s)", camera_id, track_id)
            return PersonPipelineResult(
                person_track_id=track_id, employee_id=employee_id,
                identity_status=identity_fields["identity_status"],
                identity_confidence=identity_fields["identity_confidence"], identity_from_cache=from_cache,
                ppe=ppe_payload, overall_status=None, incident_actions=[],
            )

        try:
            enriched = enrich_violations_with_cameras(evaluation, fusion_state)
            incident_results = self._incident.process_evaluation(enriched)
            self.status.mark_ok("incident")
            for r in incident_results:
                action = r.get("action")
                incident = r.get("incident", {})
                incident_actions.append({"action": action, "incident_id": incident.get("incident_id")})
                if action == "CREATED":
                    self.metrics.incidents_created += 1
                    self._attach_evidence(incident.get("incident_id"), frame, person_result, ppe_payload, visibility)
                elif action == "UPDATED" and incident.get("incident_id") in self._evidence_pending:
                    # o primeiro quadro estava escuro/sem ajuste: tenta de novo nos próximos, até um bom (ou o limite)
                    self._attach_evidence(incident.get("incident_id"), frame, person_result, ppe_payload, visibility)
                    _log_event("INCIDENT_CREATED", camera_id=camera_id, employee_id=employee_id,
                               incident_id=incident.get("incident_id"), rule_id=incident.get("rule_id"),
                               ppe_type=incident.get("ppe_type"))
                elif action == "RESOLVED":
                    self.metrics.incidents_resolved += 1
                    _log_event("INCIDENT_RESOLVED", camera_id=camera_id, employee_id=employee_id,
                               incident_id=incident.get("incident_id"))
        except Exception:
            self.status.mark_error("incident")
            self.metrics.record_error("incident")
            logger.exception("Falha no Incident Service (camera=%s track=%s)", camera_id, track_id)

        return PersonPipelineResult(
            person_track_id=track_id, employee_id=employee_id,
            identity_status=identity_fields["identity_status"],
            identity_confidence=identity_fields["identity_confidence"], identity_from_cache=from_cache,
            ppe=ppe_payload, overall_status=overall_status, incident_actions=incident_actions,
        )

    def _attach_evidence(self, incident_id, frame, person_result: dict, ppe_payload: dict, visibility=None) -> None:
        """Recorta a pessoa e envia ao Incident. Best-effort: a evidência é complemento da revisão,
        nunca decide conformidade, e qualquer falha só deixa de haver imagem.

        Quadro escuro (webcam ainda ajustando a luz) não vira prova: espera um quadro com luz nos próximos
        quadros e, se nenhum aparecer no limite, envia o MAIS CLARO que viu (melhor um escuro que nenhum)."""
        if not (self._send_evidence and incident_id and frame is not None):
            return
        try:
            from app.evidence_crop import MIN_BRIGHTNESS, build_evidence, build_findings, person_brightness
            bbox = person_result.get("person_bbox")
            status = {k: v.get("status") for k, v in (ppe_payload or {}).items() if isinstance(v, dict)}
            tries = self._evidence_pending.get(incident_id, 0)
            bright = person_brightness(frame, bbox)
            dark = bright is not None and bright < MIN_BRIGHTNESS

            if dark and tries < EVIDENCE_MAX_RETRIES:
                if tries == 0:
                    logger.warning("Evidência adiada (incidente=%s): quadro escuro (brilho %.0f < %d); aguardando luz.",
                                   incident_id, bright, MIN_BRIGHTNESS)
                self._evidence_pending[incident_id] = tries + 1
                best = self._evidence_best.get(incident_id)
                if best is None or bright > best[0]:                 # guarda o mais claro visto até agora
                    cand = build_evidence(frame, bbox, person_result.get("detections"), status)
                    if cand is not None:
                        self._evidence_best[incident_id] = (bright, cand)
                return

            waited = self._evidence_pending.pop(incident_id, 0)
            best = self._evidence_best.pop(incident_id, None)
            built = build_evidence(frame, bbox, person_result.get("detections"), status)
            sent_bright = bright
            if dark and best is not None and (bright is None or best[0] > bright):
                built, sent_bright = best[1], best[0]                 # o melhor que houve na espera
            if built is None:
                return
            if self._incident.upload_evidence(incident_id, built[0], built[1], build_findings(ppe_payload, visibility)):
                if waited:
                    logger.warning("Evidência enviada (incidente=%s) após %d quadros de espera; brilho %s.",
                                   incident_id, waited, "?" if sent_bright is None else f"{sent_bright:.0f}")
            else:
                logger.warning("Incident recusou a evidência (incidente=%s)", incident_id)
        except Exception:
            logger.exception("Falha ao enviar evidência (incidente=%s)", incident_id)

    def _sync_tracker_evidence(self, camera_id: str, employee_id: str) -> None:
        """Lê no epi_tracker a localização dos EPIs ATRIBUÍDOS ao funcionário
        e entrega ao Fusion como evidência separada. Não decide nada; falha
        isolada (nunca interrompe o frame)."""
        if self._tracker is None:
            return
        now = self._clock()
        last = self._tracker_last_sync.get(employee_id)
        if last is not None and (now - last) < self._tracker_sync_interval:
            return
        self._tracker_last_sync[employee_id] = now
        try:
            if self._tracker_area_id and camera_id not in self._camera_area_registered:
                self._fusion.set_camera_area(camera_id, self._tracker_area_id)
                self._camera_area_registered.add(camera_id)
            summary = self._tracker.get_employee_summary(employee_id)
            sent = 0
            for ppe in summary.get("assigned_ppe", []):
                tracker_id = ppe.get("tracker_id")
                if not tracker_id:
                    continue
                observation = self._tracker.get_fusion_observation(tracker_id)
                self._fusion.send_ppe_location(observation)
                sent += 1
            self.status.mark_ok("tracker")
            self.metrics.tracker_evidence_sent += sent
            if sent:
                _log_event("PPE_LOCATION_SYNCED", camera_id=camera_id, employee_id=employee_id, count=sent)
        except Exception:
            self.status.mark_error("tracker")
            self.metrics.record_error("tracker")
            logger.exception("Falha ao sincronizar evidência do tracker (camera=%s)", camera_id)

    def _resolve_identity(self, camera_id: str, track_id: str, frame: Any = None,
                          person_bbox=None) -> tuple[Optional[dict], bool]:
        cached = self._identity_cache.get(camera_id, track_id)
        if cached is not None:
            self.metrics.identity_cache_hits += 1
            return cached.to_identity_fields(), True
        if self._face_recognition:
            return self._resolve_identity_by_face(camera_id, track_id, frame, person_bbox)

        seed = self._identity_seed_provider(camera_id, track_id)
        try:
            # Se o provider de seed não decidiu nada (None — o padrão), usamos
            # o próprio track_id como seed. Isso NÃO é um atalho para
            # "reconhecer a pessoa pelo track" — o mock nunca vai encontrar
            # um funcionário cadastrado com esse valor (employee_code é
            # sempre "FUNC-XXXXXX", nunca "TRACK-XXXXXX"), então o resultado
            # é sempre UNKNOWN de forma determinística. É só um valor
            # qualquer, estável por track, para a chamada nunca falhar por
            # payload vazio.
            match_response = self._identity.match(camera_id=camera_id, seed=seed or track_id,
                                                    person_track_id=track_id)
            self.status.mark_ok("identity")
            self.metrics.identity_requests += 1
            identity_fields = identity_result_to_fusion_identity(match_response)
            self._identity_cache.put(camera_id, track_id, identity_fields)
            status = identity_fields["identity_status"]
            if status == "MATCHED":
                _log_event("IDENTITY_MATCHED", camera_id=camera_id, employee_id=identity_fields["employee_id"])
            else:
                _log_event("IDENTITY_UNMATCHED", camera_id=camera_id, status=status)
            return identity_fields, False
        except Exception:
            self.status.mark_error("identity")
            self.metrics.record_error("identity")
            logger.exception("Falha ao consultar o Identity (camera=%s track=%s)", camera_id, track_id)
            return None, False

    def _resolve_identity_by_face(self, camera_id: str, track_id: str, frame: Any,
                                  person_bbox) -> tuple[Optional[dict], bool]:
        """Reconhecimento facial real. Não identificado != violação: rosto ausente/ruim vira NOT_IDENTIFIED."""
        from app.face_probe import face_probe_b64  # noqa: PLC0415
        not_identified = {"employee_id": None, "identity_status": "NOT_IDENTIFIED", "identity_confidence": 0.0}
        probe = face_probe_b64(frame, person_bbox)
        if probe is None:
            self._identity_cache.put(camera_id, track_id, not_identified, ttl_seconds=self._face_retry)
            return not_identified, False
        try:
            response = self._identity.match_image(camera_id=camera_id, image_base64=probe, person_track_id=track_id)
            self.status.mark_ok("identity")
            self.metrics.identity_requests += 1
            fields = identity_result_to_fusion_identity(response)
            ttl = self._face_matched_ttl if fields["identity_status"] == "MATCHED" else self._face_retry
            self._identity_cache.put(camera_id, track_id, fields, ttl_seconds=ttl)
            if fields["identity_status"] == "MATCHED":
                _log_event("IDENTITY_MATCHED", camera_id=camera_id, employee_id=fields["employee_id"], source="face")
            else:
                _log_event("IDENTITY_UNMATCHED", camera_id=camera_id, status=fields["identity_status"], source="face")
            return fields, False
        except Exception:
            self.status.mark_error("identity")
            self.metrics.record_error("identity")
            logger.exception("Falha ao consultar o Identity por rosto (camera=%s track=%s)", camera_id, track_id)
            return None, False


def _log_event(event: str, **fields: Any) -> None:
    """Log estruturado (seção 30). Só metadados — nunca imagem, frame,
    embedding ou dado biométrico bruto, mesmo que passados por engano a
    esta função (o filtro abaixo é defensivo)."""
    forbidden = {"frame", "image", "embedding", "biometric", "face"}
    safe_fields = {k: v for k, v in fields.items() if k.lower() not in forbidden}
    logger.info("%s %s", event, safe_fields)
