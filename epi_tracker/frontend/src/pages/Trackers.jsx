import React, { useState, useEffect } from "react";
import { Panel, Table, Modal, SearchInput, LoadingState, ErrorState } from "../components/Common.jsx";
import { StatusBadge, BatteryIndicator, SignalIndicator } from "../components/StatusIndicators.jsx";
import { translatePPEType, translateTechnology } from "../utils/labels.js";
import { api } from "../services/api.js";

export function Trackers(props) {
  const { trackers, ppeList, loading, error, onRetry } = props;
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [history, setHistory] = useState(null);

  useEffect(() => {
    if (!selected) return;
    setHistory(null);
    api.getTrackerHistory(selected.tracker_id).then(setHistory).catch(() => setHistory([]));
  }, [selected]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;

  const ppeByTracker = {};
  (ppeList || []).forEach((p) => {
    if (p.tracker_id) ppeByTracker[p.tracker_id] = p;
  });

  const filtered = (trackers || []).filter((t) => !search || t.tracker_id.toLowerCase().includes(search.toLowerCase()));

  return (
    <div>
      <Panel title="Rastreadores" actions={<SearchInput value={search} onChange={setSearch} placeholder="Buscar tracker" />}>
        <Table
          columns={[
            { key: "tracker_id", label: "Tracker", render: (r) => <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>{r.tracker_id}</span> },
            { key: "ppe", label: "EPI", render: (r) => (ppeByTracker[r.tracker_id] ? translatePPEType(ppeByTracker[r.tracker_id].ppe_type) : "Sem EPI associado") },
            { key: "employee", label: "Funcionário", render: (r) => (ppeByTracker[r.tracker_id] ? (ppeByTracker[r.tracker_id].employee_id || "Não atribuído") : "-" ) },
            { key: "technology", label: "Tecnologia", render: (r) => translateTechnology(r.technology) },
            { key: "area", label: "Área", render: (r) => r.last_area_id || "Não informada" },
            { key: "status", label: "Status do dispositivo", render: (r) => <StatusBadge status={r.status} /> },
            { key: "battery", label: "Bateria", render: (r) => <BatteryIndicator level={r.battery_level} /> },
            { key: "signal", label: "Sinal", render: (r) => <SignalIndicator strength={r.signal_strength} /> },
          ]}
          rows={filtered.map((t) => Object.assign({}, t, { __key: t.tracker_id }))}
          onRowClick={setSelected}
          emptyMessage="Nenhum tracker cadastrado ainda."
        />
      </Panel>

      {selected && (
        <Modal title={selected.tracker_id} onClose={() => setSelected(null)}>
          <div style={{ fontSize: 13, lineHeight: 1.9 }}>
            <Row label="Tecnologia" value={translateTechnology(selected.technology)} />
            <Row label="Status do dispositivo" value={<StatusBadge status={selected.status} />} />
            <Row label="Bateria" value={<BatteryIndicator level={selected.battery_level} />} />
            <Row label="Sinal" value={<SignalIndicator strength={selected.signal_strength} />} />
            <Row label="EPI associado" value={ppeByTracker[selected.tracker_id] ? translatePPEType(ppeByTracker[selected.tracker_id].ppe_type) : "Nenhum"} />
            <Row label="Funcionário atribuído" value={ppeByTracker[selected.tracker_id] ? (ppeByTracker[selected.tracker_id].employee_id || "Não atribuído") : "Não informado"} />
            <Row label="Área atual" value={selected.last_area_id || "Não informada"} />

            <div style={{ fontWeight: 600, margin: "16px 0 8px" }}>Histórico de localização</div>
            {history === null && <div style={{ color: "#9aa1ac", fontSize: 13 }}>Carregando...</div>}
            {history && history.length === 0 && <div style={{ color: "#9aa1ac", fontSize: 13 }}>Aguardando localização — este tracker ainda não enviou uma leitura válida.</div>}
            {history && history.map((h) => (
              <div key={h.observation_id} style={{ fontSize: 12, display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: "1px solid #f1f2f4" }}>
                <span>{new Date(h.timestamp).toLocaleTimeString("pt-BR")}</span>
                <span>{h.area_id || "Não informada"}</span>
                <StatusBadge status={h.status} />
              </div>
            ))}
          </div>
        </Modal>
      )}
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
