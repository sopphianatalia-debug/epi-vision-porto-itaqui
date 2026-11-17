import React from "react";
import { Panel, Table, LoadingState, ErrorState } from "../components/Common.jsx";
import { StatusBadge } from "../components/StatusIndicators.jsx";
import { zoneInfoForArea } from "../utils/portZones.js";

export function Areas(props) {
  const { areas, employees, trackers, ppeList, checkpoints, loading, error, onRetry } = props;
  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;

  const employeeList = employees || [];
  const trackerList = trackers || [];
  const ppeListAll = ppeList || [];
  const checkpointList = checkpoints || [];

  const employeesByArea = {};
  employeeList.forEach((e) => {
    if (e.current_area_id) employeesByArea[e.current_area_id] = (employeesByArea[e.current_area_id] || 0) + 1;
  });
  const trackersByArea = {};
  trackerList.forEach((t) => {
    if (t.last_area_id) trackersByArea[t.last_area_id] = (trackersByArea[t.last_area_id] || 0) + 1;
  });
  const ppeByTrackerArea = {}; // conta EPIs cujo tracker esta na area
  const trackerToArea = {};
  trackerList.forEach((t) => { trackerToArea[t.tracker_id] = t.last_area_id; });
  ppeListAll.forEach((p) => {
    const areaId = p.tracker_id ? trackerToArea[p.tracker_id] : null;
    if (areaId) ppeByTrackerArea[areaId] = (ppeByTrackerArea[areaId] || 0) + 1;
  });
  const checkpointsByArea = {};
  checkpointList.forEach((c) => { checkpointsByArea[c.area_id] = (checkpointsByArea[c.area_id] || 0) + 1; });

  const rows = (areas || []).map((a) => {
    const info = zoneInfoForArea(a);
    return Object.assign({}, a, {
      __key: a.area_id,
      __tipo: info.label,
      __funcionarios: employeesByArea[a.area_id] || 0,
      __trackers: trackersByArea[a.area_id] || 0,
      __epis: ppeByTrackerArea[a.area_id] || 0,
      __checkpoints: checkpointsByArea[a.area_id] || 0,
    });
  });

  return (
    <Panel title="Áreas operacionais">
      <Table
        columns={[
          { key: "name", label: "Nome" },
          { key: "__tipo", label: "Tipo" },
          { key: "active", label: "Status", render: (r) => <StatusBadge status={r.active ? "ONLINE" : "OFFLINE"} label={r.active ? "Ativa" : "Inativa"} /> },
          { key: "__funcionarios", label: "Funcionários" },
          { key: "__trackers", label: "Trackers" },
          { key: "__epis", label: "EPIs monitorados" },
          { key: "__checkpoints", label: "Checkpoints" },
        ]}
        rows={rows}
        emptyMessage="Nenhuma área cadastrada ainda. As áreas operacionais aparecerão aqui quando forem cadastradas."
      />
    </Panel>
  );
}

export function Checkpoints(props) {
  const { checkpoints, loading, error, onRetry } = props;
  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;
  return (
    <Panel title="Checkpoints">
      <Table
        columns={[
          { key: "name", label: "Nome" },
          { key: "area_id", label: "Área" },
          { key: "camera_id", label: "Câmera", render: (r) => r.camera_id || "Não informada" },
          { key: "reader_id", label: "Leitor", render: (r) => r.reader_id || "Não informado" },
          { key: "active", label: "Status", render: (r) => <StatusBadge status={r.active ? "ONLINE" : "OFFLINE"} label={r.active ? "Ativo" : "Inativo"} /> },
        ]}
        rows={(checkpoints || []).map((c) => Object.assign({}, c, { __key: c.checkpoint_id }))}
        emptyMessage="Nenhum checkpoint cadastrado ainda."
      />
    </Panel>
  );
}
