import React, { useState } from "react";
import { Panel, Table, Modal, SearchInput, LoadingState, ErrorState } from "../components/Common.jsx";
import { StatusBadge } from "../components/StatusIndicators.jsx";
import { translatePPEType } from "../utils/labels.js";

export function PPEList(props) {
  const { ppeList, trackerLocations, loading, error, onRetry } = props;
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;

  const filtered = (ppeList || []).filter(
    (p) => !search || p.ppe_id.toLowerCase().includes(search.toLowerCase()) || translatePPEType(p.ppe_type).toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <Panel title="EPIs" actions={<SearchInput value={search} onChange={setSearch} placeholder="Buscar EPI" />}>
        <Table
          columns={[
            {
              key: "ppe_type", label: "EPI",
              render: (r) => (
                <div>
                  <div>{translatePPEType(r.ppe_type)}</div>
                  <div style={{ fontSize: 11, color: "#9aa1ac", fontFamily: "ui-monospace, monospace" }}>{r.ppe_id}</div>
                </div>
              ),
            },
            { key: "employee_id", label: "Funcionário (atribuído)", render: (r) => r.employee_id || "Não atribuído" },
            { key: "tracker_id", label: "Tracker", render: (r) => r.tracker_id || "Sem tracker" },
            {
              key: "area",
              label: "Última localização conhecida",
              render: (r) => {
                const loc = r.tracker_id && trackerLocations ? trackerLocations[r.tracker_id] : null;
                if (!loc || !loc.area_id) return "Não informada";
                return `${loc.area_id}`;
              },
            },
            { key: "status", label: "Status", render: (r) => <StatusBadge status={r.status} /> },
          ]}
          rows={filtered.map((p) => Object.assign({}, p, { __key: p.ppe_id }))}
          onRowClick={setSelected}
          emptyMessage="Nenhum EPI cadastrado ainda."
        />
      </Panel>

      {selected && (
        <Modal title={translatePPEType(selected.ppe_type)} onClose={() => setSelected(null)}>
          <div style={{ fontSize: 13, lineHeight: 1.9 }}>
            <Row label="Identificador" value={selected.ppe_id} mono />
            <Row label="Status" value={<StatusBadge status={selected.status} />} />
            <Row label="Tracker associado" value={selected.tracker_id || "Nenhum"} />

            <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
              <div style={{ flex: 1, padding: 10, background: "#f7f8f9", borderRadius: 8 }}>
                <div style={{ fontSize: 11, textTransform: "uppercase", color: "#9aa1ac", marginBottom: 4 }}>Atribuído a (administrativo)</div>
                <div style={{ fontWeight: 600 }}>{selected.employee_id || "Ninguem"}</div>
              </div>
              <div style={{ flex: 1, padding: 10, background: "#f7f8f9", borderRadius: 8 }}>
                <div style={{ fontSize: 11, textTransform: "uppercase", color: "#9aa1ac", marginBottom: 4 }}>Uso confirmado por câmera</div>
                <div style={{ fontWeight: 600, color: "#9aa1ac", fontSize: 12 }}>Verificado em outro módulo (Safety Check)</div>
              </div>
            </div>
            <div style={{ fontSize: 11, color: "#9aa1ac", marginTop: 10 }}>
              Atribuído indica associação administrativa do EPI ao funcionário — não confirma que o EPI está sendo usado no momento.
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Row({ label, value, mono }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid #f1f2f4", padding: "4px 0" }}>
      <span style={{ color: "#8a919c" }}>{label}</span>
      <span style={mono ? { fontFamily: "ui-monospace, monospace", fontSize: 12 } : undefined}>{value}</span>
    </div>
  );
}
