import React, { useState } from "react";
import { Panel, Table, Modal, SearchInput, LoadingState, ErrorState } from "../components/Common.jsx";
import { ComplianceBadge, StatusBadge } from "../components/StatusIndicators.jsx";
import { translatePPEType } from "../utils/labels.js";

export function Employees(props) {
  const { employees, loading, error, onRetry } = props;
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;

  const filtered = (employees || []).filter(
    (e) => !search || e.employee_id.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <Panel title="Funcionários" actions={<SearchInput value={search} onChange={setSearch} placeholder="Buscar funcionário" />}>
        <Table
          columns={[
            { key: "employee_id", label: "Funcionário", render: (r) => <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>{r.employee_id}</span> },
            { key: "area", label: "Área atual", render: (r) => r.current_area_id || "Não informada" },
            {
              key: "status",
              label: "Status",
              render: (r) => (r.current_area_id ? <StatusBadge status="ACTIVE" label="Em operacao" /> : <StatusBadge status="UNKNOWN" label="Sem localização" />),
            },
            {
              key: "last_check_time",
              label: "Última verificação",
              render: (r) => (r.last_check ? new Date(r.last_check.timestamp).toLocaleTimeString("pt-BR") : "Sem verificação"),
            },
            {
              key: "compliance",
              label: "Conformidade",
              render: (r) => <ComplianceBadge status={r.last_check ? r.last_check.status : null} />,
            },
            { key: "ppe_count", label: "EPIs", render: (r) => (r.assigned_ppe.length > 0 ? `${r.assigned_ppe.length} atribuído(s)` : "Nenhum") },
          ]}
          rows={filtered.map((e) => Object.assign({}, e, { __key: e.employee_id }))}
          onRowClick={setSelected}
          emptyMessage="Nenhum funcionário conhecido ainda. Funcionários aparecerão aqui quando um EPI for atribuído ou uma verificação for registrada."
        />
      </Panel>

      {selected && (
        <Modal title={selected.employee_id} onClose={() => setSelected(null)}>
          <div style={{ fontSize: 13, lineHeight: 1.9 }}>
            <Row label="Área atual" value={selected.current_area_id || "Não informada"} />
            {selected.last_check ? (
              <>
                <Row label="Último checkpoint" value={selected.last_check.checkpoint_id} />
                <Row label="Última verificação" value={new Date(selected.last_check.timestamp).toLocaleString("pt-BR")} />
                <Row label="Resultado" value={<ComplianceBadge status={selected.last_check.status} />} />
              </>
            ) : (
              <Row label="Verificações" value="Nenhuma verificação registrada ainda" />
            )}

            <div style={{ fontWeight: 600, margin: "16px 0 8px" }}>EPIs atribuídos</div>
            {selected.assigned_ppe.length === 0 && <div style={{ color: "#9aa1ac", fontSize: 13 }}>Nenhum EPI atribuído a este funcionário</div>}
            {selected.assigned_ppe.map((p) => (
              <div key={p.ppe_id} style={{ marginBottom: 8, padding: 10, background: "#f7f8f9", borderRadius: 8 }}>
                <div style={{ fontWeight: 600 }}>{translatePPEType(p.ppe_type)}</div>
                <div style={{ fontSize: 11, color: "#9aa1ac", fontFamily: "ui-monospace, monospace" }}>{p.ppe_id}</div>
                <div style={{ fontSize: 12, marginTop: 4 }}>
                  Localização: {p.area_id || "Não informada"}
                  {p.location_state && <span style={{ marginLeft: 6 }}><StatusBadge status={p.location_state} /></span>}
                </div>
              </div>
            ))}

            <div style={{ fontWeight: 600, margin: "16px 0 8px" }}>Histórico de verificações</div>
            {selected.history.length === 0 && <div style={{ color: "#9aa1ac", fontSize: 13 }}>Nenhum registro ainda</div>}
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {selected.history.map((h) => (
                <div key={h.check_id} style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                  <span>{new Date(h.timestamp).toLocaleTimeString("pt-BR")} - {h.area_id}</span>
                  <ComplianceBadge status={h.status} />
                </div>
              ))}
            </div>
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
