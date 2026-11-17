import React, { useState } from "react";
import { Card, Panel, Table, LoadingState, EmptyState } from "../components/Common.jsx";
import { StatusBadge } from "../components/StatusIndicators.jsx";
import { alertsApi } from "../services/api.js";

const SOURCE_LABELS = { tracker: "Rastreadores", fusion: "Fusion (câmeras)", incident: "Incidentes" };
const TYPE_LABELS = {
  INCIDENT_OPEN: "Incidente aberto",
  PPE_LOCATION_INCONSISTENCY: "Possível inconsistência",
  TRACKER_OFFLINE: "Rastreador offline",
  TRACKER_LOW_BATTERY: "Bateria baixa",
  TRACKER_LOCATION_EXPIRED: "Localização expirada",
};

function filterButton(active, label, onClick) {
  return (
    <button
      key={label}
      onClick={onClick}
      style={{
        padding: "5px 12px", fontSize: 12, borderRadius: 999, cursor: "pointer",
        border: "1px solid " + (active ? "#4c8dff" : "#dde1e6"),
        background: active ? "#eaf1fd" : "#fff", color: active ? "#1c50a8" : "#57606a", fontWeight: 600,
      }}
    >
      {label}
    </button>
  );
}

function formatTime(iso) {
  return iso ? new Date(iso).toLocaleTimeString("pt-BR") : "—";
}

export function Alerts({ alerts, summary, offline, loading, onChanged, notify }) {
  const [severity, setSeverity] = useState("ALL");
  const [showResolved, setShowResolved] = useState(false);

  if (loading && !alerts) return <LoadingState />;

  if (offline) {
    return (
      <Panel title="Alertas">
        <div style={{ padding: "36px 20px", textAlign: "center" }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#3d4148", marginBottom: 6 }}>Serviço de alertas indisponível</div>
          <div style={{ fontSize: 13, color: "#8a919c" }}>
            O restante do sistema continua funcionando. Inicie o serviço de alertas (porta 8005) para ver os avisos.
          </div>
        </div>
      </Panel>
    );
  }

  const list = (alerts || []).filter((a) => (showResolved ? true : a.status !== "RESOLVED"))
    .filter((a) => severity === "ALL" || a.severity === severity);
  const by = (summary && summary.by_severity) || { CRITICAL: 0, WARNING: 0, INFO: 0 };
  const sources = (summary && summary.sources) || {};
  const downSources = Object.keys(sources).filter((k) => !sources[k].online);

  async function acknowledge(alert) {
    try {
      await alertsApi.acknowledge(alert.alert_id);
      notify("Alerta marcado como visto.");
      onChanged();
    } catch (e) {
      notify("Não foi possível atualizar o alerta.", "error");
    }
  }

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 14, marginBottom: 20 }}>
        <Card title="Alertas abertos" value={summary ? summary.open_total : 0}
          hint={summary && summary.open_total === 0 ? "Nenhum alerta no momento" : "Aguardando atenção"} accent="#4c8dff" />
        <Card title="Críticos" value={by.CRITICAL} hint="Exigem ação imediata" accent={by.CRITICAL > 0 ? "#c92a2a" : "#1a7f37"} />
        <Card title="Atenção" value={by.WARNING} hint="Merecem conferência" accent={by.WARNING > 0 ? "#d48806" : "#1a7f37"} />
        <Card title="Não vistos" value={summary ? summary.unacknowledged : 0} hint="Ainda sem confirmação" />
      </div>

      {downSources.length > 0 && (
        <div style={{ marginBottom: 16, fontSize: 13, color: "#5a6270", background: "#fff8e8", border: "1px solid #f1dfaf", borderRadius: 8, padding: 12, lineHeight: 1.6 }}>
          <strong>Atenção:</strong> não foi possível consultar {downSources.map((k) => SOURCE_LABELS[k] || k).join(", ")}.
          Enquanto isso, os alertas dessa origem ficam como estavam — a ausência de alertas dela não significa que está tudo certo.
        </div>
      )}

      <Panel
        title="Alertas"
        actions={
          <label style={{ fontSize: 12, color: "#57606a", cursor: "pointer" }}>
            <input type="checkbox" checked={showResolved} onChange={(e) => setShowResolved(e.target.checked)} /> Mostrar resolvidos
          </label>
        }
      >
        <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
          {filterButton(severity === "ALL", "Todos", () => setSeverity("ALL"))}
          {filterButton(severity === "CRITICAL", "Críticos", () => setSeverity("CRITICAL"))}
          {filterButton(severity === "WARNING", "Atenção", () => setSeverity("WARNING"))}
          {filterButton(severity === "INFO", "Informativos", () => setSeverity("INFO"))}
        </div>
        {list.length === 0 ? (
          <div style={{ padding: "30px 20px", textAlign: "center" }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#3d4148", marginBottom: 6 }}>Nenhum alerta aberto</div>
            <div style={{ fontSize: 13, color: "#8a919c" }}>
              Os alertas aparecem aqui quando um rastreador fica offline, a bateria baixa, uma localização expira,
              há divergência entre câmera e rastreador ou um incidente é aberto.
            </div>
          </div>
        ) : (
          <Table
            columns={[
              { key: "severity", label: "Gravidade", render: (r) => <StatusBadge status={r.severity} /> },
              { key: "title", label: "Alerta", render: (r) => (
                <div>
                  <div style={{ fontWeight: 600, color: "#1b1f24" }}>{r.title}</div>
                  <div style={{ fontSize: 12, color: "#57606a", marginTop: 2 }}>{r.message}</div>
                  <div style={{ fontSize: 11, color: "#8a919c", marginTop: 2 }}>
                    {TYPE_LABELS[r.type] || r.type} · {SOURCE_LABELS[r.source] || r.source}
                  </div>
                </div>
              ) },
              { key: "status", label: "Situação", render: (r) => <StatusBadge status={r.status} /> },
              { key: "opened_at", label: "Aberto às", render: (r) => formatTime(r.opened_at) },
              { key: "occurrences", label: "Verificações", render: (r) => r.occurrences },
              { key: "action", label: "", render: (r) => r.status === "OPEN" ? (
                <button
                  onClick={() => acknowledge(r)}
                  style={{ padding: "4px 10px", fontSize: 12, borderRadius: 6, border: "1px solid #dde1e6", background: "#fff", cursor: "pointer" }}
                >
                  Marcar como visto
                </button>
              ) : null },
            ]}
            rows={list.map((a) => Object.assign({}, a, { __key: a.alert_id }))}
          />
        )}
      </Panel>
    </div>
  );
}
