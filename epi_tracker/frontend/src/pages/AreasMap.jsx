import React, { useState } from "react";
import { Modal, LoadingState, ErrorState, EmptyState, SearchInput } from "../components/Common.jsx";
import { Dot, StatusBadge, BatteryIndicator, SignalIndicator } from "../components/StatusIndicators.jsx";
import { translatePPEType, translateTechnology, translateEvent } from "../utils/labels.js";
import { zoneInfoForArea } from "../utils/portZones.js";
import { PortSceneBackground } from "../components/PortSceneBackground.jsx";
import { getMockCameraStatus, getMockCameraHistory } from "../mocks/cameraDemoData.js";

// Posicoes (em % do container) escolhidas para coincidir com as zonas
// desenhadas em PortSceneBackground.jsx -- cais/navios perto da agua (topo),
// patio de conteineres/carga ao centro, armazem/oficina a direita, portaria/
// caminhoes a esquerda, administrativa/abastecimento/obras/restrita embaixo.
const ZONE_POSITIONS = {
  CAIS: { left: "34%", top: "1%", width: "23%" },
  NAVIOS: { left: "70%", top: "1%", width: "23%" },
  PORTARIA: { left: "5%", top: "31%", width: "16%" },
  PATIO_ARMAZENAGEM: { left: "24%", top: "44%", width: "20%" },
  PATIO_CAMINHOES: { left: "5%", top: "58%", width: "16%" },
  CARGA_DESCARGA: { left: "58%", top: "40%", width: "20%" },
  ARMAZEM: { left: "83%", top: "30%", width: "16%" },
  OFICINA: { left: "83%", top: "56%", width: "16%" },
  ADMINISTRATIVA: { left: "24%", top: "76%", width: "14%" },
  RESTRITA: { left: "75%", top: "76%", width: "23%" },
};

function trackerHex(status) {
  return { ACTIVE: "#0f7938", LOW_BATTERY: "#93650a", OFFLINE: "#c0281f" }[status] || "#9aa1ac";
}

export function AreasMap(props) {
  const { areas, employees, trackers, ppeList, checkpoints, loading, error, onRetry } = props;
  const [selectedTracker, setSelectedTracker] = useState(null);
  const [selectedCheckpoint, setSelectedCheckpoint] = useState(null);
  const [selectedCamera, setSelectedCamera] = useState(null);
  const [filterAreaId, setFilterAreaId] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterEmployee, setFilterEmployee] = useState("");
  const [filterPPE, setFilterPPE] = useState("");
  const [showTrackers, setShowTrackers] = useState(true);
  const [showCheckpoints, setShowCheckpoints] = useState(true);
  const [showCameras, setShowCameras] = useState(true);
  const [zoom, setZoom] = useState(1);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;

  const areaList = areas || [];
  const employeeList = employees || [];
  const trackerList = trackers || [];
  const ppeListAll = ppeList || [];
  const checkpointList = checkpoints || [];

  const employeesByArea = {};
  employeeList.forEach((e) => {
    if (e.current_area_id) (employeesByArea[e.current_area_id] = employeesByArea[e.current_area_id] || []).push(e);
  });
  const ppeByTracker = {};
  ppeListAll.forEach((p) => { if (p.tracker_id) ppeByTracker[p.tracker_id] = p; });
  const trackersByArea = {};
  trackerList.forEach((t) => {
    if (t.last_area_id) (trackersByArea[t.last_area_id] = trackersByArea[t.last_area_id] || []).push(t);
  });
  const checkpointsByArea = {};
  checkpointList.forEach((c) => { (checkpointsByArea[c.area_id] = checkpointsByArea[c.area_id] || []).push(c); });
  const camerasByArea = {};
  checkpointList.forEach((c) => {
    if (!c.camera_id) return;
    (camerasByArea[c.area_id] = camerasByArea[c.area_id] || []).push(c);
  });
  const lastCheckByCheckpoint = {};
  employeeList.forEach((e) => {
    (e.history || []).forEach((h) => {
      const cur = lastCheckByCheckpoint[h.checkpoint_id];
      if (!cur || new Date(h.timestamp) > new Date(cur.timestamp)) lastCheckByCheckpoint[h.checkpoint_id] = h;
    });
  });

  const matchesFilters = (tracker) => {
    if (filterAreaId && tracker.last_area_id !== filterAreaId) return false;
    if (filterStatus && tracker.status !== filterStatus) return false;
    const ppe = ppeByTracker[tracker.tracker_id];
    if (filterEmployee && (!ppe || !ppe.employee_id || !ppe.employee_id.toLowerCase().includes(filterEmployee.toLowerCase()))) return false;
    if (filterPPE && (!ppe || ppe.ppe_type !== filterPPE)) return false;
    return true;
  };

  const positionedAreas = [];
  const otherAreas = [];
  areaList.forEach((area) => {
    const pos = ZONE_POSITIONS[(area.type || "").toUpperCase()];
    if (pos) positionedAreas.push({ area, pos });
    else otherAreas.push(area);
  });

  const ppeTypesPresent = Array.from(new Set(ppeListAll.map((p) => p.ppe_type)));
  const trackersOnline = trackerList.filter((t) => t.status === "ACTIVE").length;
  const trackersLowBattery = trackerList.filter((t) => t.status === "LOW_BATTERY").length;
  const trackersOffline = trackerList.filter((t) => t.status === "OFFLINE").length;
  const allCameras = checkpointList.filter((c) => c.camera_id);
  const camerasByStatus = { ONLINE: 0, ATTENTION: 0, OFFLINE: 0 };
  allCameras.forEach((c) => { camerasByStatus[getMockCameraStatus(c.camera_id)]++; });

  return (
    <div>
      <div style={{ marginBottom: 14 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: "#161a1f" }}>Planta operacional do terminal</h1>
        <div style={{ fontSize: 12, color: "#8a919c", marginTop: 4 }}>
          Representação esquemática do terminal portuário — não é um mapa com coordenadas GPS reais.
        </div>
      </div>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14, alignItems: "center" }}>
        <select value={filterAreaId} onChange={(e) => setFilterAreaId(e.target.value)} style={selectStyle}>
          <option value="">Todas as áreas</option>
          {areaList.map((a) => <option key={a.area_id} value={a.area_id}>{a.name}</option>)}
        </select>
        <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} style={selectStyle}>
          <option value="">Todos os status de tracker</option>
          <option value="ACTIVE">Ativo</option>
          <option value="LOW_BATTERY">Bateria baixa</option>
          <option value="OFFLINE">Offline</option>
        </select>
        <select value={filterPPE} onChange={(e) => setFilterPPE(e.target.value)} style={selectStyle}>
          <option value="">Todos os EPIs</option>
          {ppeTypesPresent.map((t) => <option key={t} value={t}>{translatePPEType(t)}</option>)}
        </select>
        <SearchInput value={filterEmployee} onChange={setFilterEmployee} placeholder="Buscar funcionário" />
        {(filterAreaId || filterStatus || filterPPE || filterEmployee) && (
          <button onClick={() => { setFilterAreaId(""); setFilterStatus(""); setFilterPPE(""); setFilterEmployee(""); }} style={btnStyle}>
            Limpar filtros
          </button>
        )}
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 14, alignItems: "center", fontSize: 12, color: "#5a6270" }}>
        <label style={toggleStyle}><input type="checkbox" checked={showTrackers} onChange={(e) => setShowTrackers(e.target.checked)} /> Trackers</label>
        <label style={toggleStyle}><input type="checkbox" checked={showCheckpoints} onChange={(e) => setShowCheckpoints(e.target.checked)} /> Checkpoints</label>
        <label style={toggleStyle}><input type="checkbox" checked={showCameras} onChange={(e) => setShowCameras(e.target.checked)} /> Câmeras</label>
        <div style={{ display: "flex", gap: 4, marginLeft: "auto" }}>
          <button onClick={() => setZoom((z) => Math.max(0.7, z - 0.15))} style={btnStyle}>−</button>
          <button onClick={() => setZoom(1)} style={btnStyle}>{Math.round(zoom * 100)}%</button>
          <button onClick={() => setZoom((z) => Math.min(1.5, z + 0.15))} style={btnStyle}>+</button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 14 }}>
        <div style={{ flex: 1, overflow: "auto", border: "1px solid #e6e8eb", borderRadius: 10 }}>
          {areaList.length === 0 ? (
            <EmptyState message="Nenhuma área cadastrada ainda. Rode scripts/seed_demo_data.py ou cadastre áreas via API para ver a planta." />
          ) : (
            <div style={{ position: "relative", width: "100%", aspectRatio: "1200 / 900", transform: `scale(${zoom})`, transformOrigin: "top left" }}>
              <PortSceneBackground />
              {positionedAreas.map(({ area, pos }) => (
                <div key={area.area_id} style={{ position: "absolute", left: pos.left, top: pos.top, width: pos.width }}>
                  <ZoneCard
                    area={area}
                    employees={employeesByArea[area.area_id] || []}
                    trackers={trackersByArea[area.area_id] || []}
                    checkpoints={checkpointsByArea[area.area_id] || []}
                    cameras={camerasByArea[area.area_id] || []}
                    ppeByTracker={ppeByTracker}
                    matchesFilters={matchesFilters}
                    onTrackerClick={setSelectedTracker}
                    onCheckpointClick={setSelectedCheckpoint}
                    onCameraClick={setSelectedCamera}
                    showTrackers={showTrackers} showCheckpoints={showCheckpoints} showCameras={showCameras}
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ width: 220, flexShrink: 0 }}>
          <SummaryPanel
            areaCount={areaList.length} employeeCount={employeeList.length}
            trackersOnline={trackersOnline} trackersLowBattery={trackersLowBattery} trackersOffline={trackersOffline}
            camerasByStatus={camerasByStatus} totalCameras={allCameras.length}
            checkpointCount={checkpointList.length} ppeCount={ppeListAll.length}
          />
        </div>
      </div>

      {otherAreas.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "#5a6270", marginBottom: 8 }}>Outras áreas (fora da planta)</div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {otherAreas.map((area) => (
              <div key={area.area_id} style={{ width: 220 }}>
                <ZoneCard
                  area={area}
                  employees={employeesByArea[area.area_id] || []}
                  trackers={trackersByArea[area.area_id] || []}
                  checkpoints={checkpointsByArea[area.area_id] || []}
                  cameras={camerasByArea[area.area_id] || []}
                  ppeByTracker={ppeByTracker}
                  matchesFilters={matchesFilters}
                  onTrackerClick={setSelectedTracker}
                  onCheckpointClick={setSelectedCheckpoint}
                  onCameraClick={setSelectedCamera}
                  showTrackers={showTrackers} showCheckpoints={showCheckpoints} showCameras={showCameras}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 18, fontSize: 12, color: "#5a6270", flexWrap: "wrap", padding: "12px 4px" }}>
        <span style={legendItemStyle}><Dot color="green" /> Tracker ativo</span>
        <span style={legendItemStyle}><Dot color="amber" /> Bateria baixa</span>
        <span style={legendItemStyle}><Dot color="red" /> Offline</span>
        <span style={legendItemStyle}><span style={{ width: 9, height: 7, background: "#3d6fd6", display: "inline-block", borderRadius: 2 }} /> Câmera (cor = status)</span>
        <span style={legendItemStyle}><span style={{ width: 8, height: 8, background: "#1c50a8", display: "inline-block", borderRadius: 2 }} /> Checkpoint</span>
      </div>

      {selectedTracker && (
        <Modal title={selectedTracker.tracker_id} onClose={() => setSelectedTracker(null)}>
          <TrackerDetail tracker={selectedTracker} ppe={ppeByTracker[selectedTracker.tracker_id]} />
        </Modal>
      )}
      {selectedCheckpoint && (
        <Modal title={selectedCheckpoint.name} onClose={() => setSelectedCheckpoint(null)}>
          <CheckpointDetail checkpoint={selectedCheckpoint} lastCheck={lastCheckByCheckpoint[selectedCheckpoint.checkpoint_id]} />
        </Modal>
      )}
      {selectedCamera && (
        <Modal title={`Câmera ${selectedCamera.camera_id}`} onClose={() => setSelectedCamera(null)}>
          <CameraDetail checkpoint={selectedCamera} />
        </Modal>
      )}
    </div>
  );
}

const selectStyle = { padding: "6px 8px", fontSize: 12, borderRadius: 6, border: "1px solid #d7dbe0" };
const btnStyle = { fontSize: 12, padding: "6px 10px", border: "1px solid #d7dbe0", borderRadius: 6, background: "#fff", cursor: "pointer" };
const toggleStyle = { display: "flex", alignItems: "center", gap: 6, cursor: "pointer" };
const legendItemStyle = { display: "flex", alignItems: "center", gap: 6, background: "#fff", padding: "3px 8px", borderRadius: 6, border: "1px solid #e6e8eb" };

function SummaryPanel(props) {
  return (
    <div style={{ background: "#fff", border: "1px solid #e6e8eb", borderRadius: 10, padding: 16, position: "sticky", top: 0 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: "#161a1f", marginBottom: 12 }}>Elementos do mapa</div>
      <SummaryGroup title="Trackers">
        <SummaryRow color="green" label="Ativos" value={props.trackersOnline} />
        <SummaryRow color="amber" label="Bateria baixa" value={props.trackersLowBattery} />
        <SummaryRow color="red" label="Offline" value={props.trackersOffline} />
      </SummaryGroup>
      <SummaryGroup title="Câmeras (simulado)">
        <SummaryRow color="green" label="Online" value={props.camerasByStatus.ONLINE} />
        <SummaryRow color="amber" label="Atenção" value={props.camerasByStatus.ATTENTION} />
        <SummaryRow color="red" label="Offline" value={props.camerasByStatus.OFFLINE} />
      </SummaryGroup>
      <SummaryGroup title="Áreas monitoradas">
        <SummaryPlain label="Áreas" value={props.areaCount} />
        <SummaryPlain label="Funcionários" value={props.employeeCount} />
        <SummaryPlain label="EPIs" value={props.ppeCount} />
        <SummaryPlain label="Checkpoints" value={props.checkpointCount} />
        <SummaryPlain label="Câmeras" value={props.totalCameras} />
      </SummaryGroup>
    </div>
  );
}
function SummaryGroup({ title, children }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 10, textTransform: "uppercase", color: "#9aa1ac", marginBottom: 6, letterSpacing: 0.4 }}>{title}</div>
      {children}
    </div>
  );
}
function SummaryRow({ color, label, value }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#3d4148", padding: "2px 0" }}>
      <Dot color={color} /> <span style={{ flex: 1 }}>{label}</span> <strong>{value}</strong>
    </div>
  );
}
function SummaryPlain({ label, value }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#3d4148", padding: "2px 0" }}>
      <span>{label}</span> <strong>{value}</strong>
    </div>
  );
}

function ZoneCard(props) {
  const { area, employees, trackers, checkpoints, cameras, ppeByTracker, matchesFilters, onTrackerClick,
    onCheckpointClick, onCameraClick, showTrackers, showCheckpoints, showCameras } = props;
  const info = zoneInfoForArea(area);
  const nonCompliant = employees.filter((e) => e.last_check && e.last_check.status === "NON_COMPLIANT").length;
  const borderColor = nonCompliant > 0 ? "#c0281f" : trackers.some((t) => t.status === "OFFLINE") ? "#93650a" : "#e6e8eb";

  return (
    <div style={{
      background: "rgba(255,255,255,0.97)", border: "1.5px solid " + borderColor, borderRadius: 10, padding: 10,
      boxShadow: "0 2px 10px rgba(20,25,35,0.18)", fontSize: 11,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 5, gap: 6 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "#161a1f", lineHeight: 1.25 }}>{area.name}</div>
        {nonCompliant > 0 && <StatusBadge status="NON_COMPLIANT" label={`${nonCompliant}`} />}
      </div>
      <div style={{ fontSize: 10, color: "#5a6270", marginBottom: 6 }}>
        {employees.length} func. · {trackers.length} tracker(s)
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 5, alignItems: "center" }}>
        {showCameras && cameras.map((c) => {
          const status = getMockCameraStatus(c.camera_id);
          const color = { ONLINE: "#0f7938", ATTENTION: "#93650a", OFFLINE: "#c0281f" }[status];
          return <div key={c.camera_id} onClick={() => onCameraClick(c)} title={c.camera_id}
            style={{ width: 10, height: 8, background: color, borderRadius: 2, cursor: "pointer" }} />;
        })}
        {showCheckpoints && checkpoints.map((c) => (
          <div key={c.checkpoint_id} onClick={() => onCheckpointClick(c)} title={c.name}
            style={{ width: 9, height: 9, background: "#1c50a8", borderRadius: 2, cursor: "pointer" }} />
        ))}
        {showTrackers && trackers.map((t) => {
          const dim = !matchesFilters(t);
          return <div key={t.tracker_id} onClick={() => onTrackerClick(t)} title={t.tracker_id}
            style={{ width: 11, height: 11, borderRadius: "50%", cursor: "pointer", opacity: dim ? 0.25 : 1, background: trackerHex(t.status) }} />;
        })}
      </div>
    </div>
  );
}

function TrackerDetail({ tracker, ppe }) {
  return (
    <div style={{ fontSize: 13, lineHeight: 2 }}>
      <Row label="Status" value={<StatusBadge status={tracker.status} />} />
      <Row label="Funcionário" value={ppe && ppe.employee_id ? ppe.employee_id : "Não atribuído"} />
      <Row label="EPI" value={ppe ? `${translatePPEType(ppe.ppe_type)} (${ppe.ppe_id})` : "Nenhum EPI associado"} />
      <Row label="Área atual" value={tracker.last_area_id || "Não informada"} />
      <Row label="Tecnologia" value={translateTechnology(tracker.technology)} />
      <Row label="Bateria" value={<BatteryIndicator level={tracker.battery_level} />} />
      <Row label="Sinal" value={<SignalIndicator strength={tracker.signal_strength} />} />
    </div>
  );
}

function CheckpointDetail({ checkpoint, lastCheck }) {
  return (
    <div style={{ fontSize: 13, lineHeight: 2 }}>
      <Row label="Área" value={checkpoint.area_id} />
      <Row label="Câmera associada" value={checkpoint.camera_id || "Não informada"} />
      <Row label="Status" value={<StatusBadge status={checkpoint.active ? "ONLINE" : "OFFLINE"} label={checkpoint.active ? "Ativo" : "Inativo"} />} />
      <Row label="Última verificação" value={lastCheck ? new Date(lastCheck.timestamp).toLocaleString("pt-BR") : "Nenhuma verificação registrada"} />
      {lastCheck && <Row label="Resultado" value={<StatusBadge status={lastCheck.status} />} />}
    </div>
  );
}

function CameraDetail({ checkpoint }) {
  const status = getMockCameraStatus(checkpoint.camera_id);
  const history = getMockCameraHistory(checkpoint.camera_id);
  const days = Array.from(new Set(history.map((h) => h.timestamp.slice(0, 10))));
  const [selectedDay, setSelectedDay] = useState(days[0] || "");
  const filtered = history.filter((h) => !selectedDay || h.timestamp.startsWith(selectedDay));

  return (
    <div style={{ fontSize: 13 }}>
      <div style={{ background: "#fff8e8", border: "1px solid #f1dfaf", borderRadius: 8, padding: 10, fontSize: 11, color: "#5a6270", marginBottom: 14 }}>
        Identificador e área desta câmera vêm do cadastro real do checkpoint. Status e histórico abaixo são
        simulados — o backend ainda não tem uma integração real de câmeras.
      </div>
      <div style={{ lineHeight: 2, marginBottom: 14 }}>
        <Row label="Local" value={checkpoint.name} />
        <Row label="Área" value={checkpoint.area_id} />
        <Row label="Status (simulado)" value={<StatusBadge status={status} />} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div style={{ fontWeight: 600 }}>Histórico de registros</div>
        {days.length > 1 && (
          <select value={selectedDay} onChange={(e) => setSelectedDay(e.target.value)} style={{ fontSize: 12, padding: "4px 6px", borderRadius: 6, border: "1px solid #d7dbe0" }}>
            {days.map((d) => <option key={d} value={d}>{new Date(d + "T00:00:00").toLocaleDateString("pt-BR")}</option>)}
          </select>
        )}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 220, overflow: "auto" }}>
        {filtered.length === 0 && <div style={{ color: "#9aa1ac", fontSize: 12 }}>Nenhum registro nesta data.</div>}
        {filtered.map((h, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "6px 8px", background: "#f7f8f9", borderRadius: 6 }}>
            <span>{new Date(h.timestamp).toLocaleTimeString("pt-BR")}</span>
            <span>{translateEvent(h.event)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid #f1f2f4", padding: "4px 0" }}>
      <span style={{ color: "#8a919c" }}>{label}</span>
      <span>{value}</span>
    </div>
  );
}
