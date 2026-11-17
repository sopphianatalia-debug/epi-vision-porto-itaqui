import React from "react";
import { Panel, Table, LoadingState, ErrorState } from "../components/Common.jsx";

export function Inconsistencies(props) {
  const { inconsistencies, loading, error, onRetry } = props;
  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;

  const list = inconsistencies || [];

  return (
    <Panel title="Possíveis inconsistências entre câmera e tracker">
      <div style={{ marginBottom: 16, fontSize: 13, color: "#5a6270", background: "#fff8e8", border: "1px solid #f1dfaf", borderRadius: 8, padding: 12, lineHeight: 1.6 }}>
        <strong>Atenção:</strong> uma inconsistência não significa automaticamente uma violação de segurança.
        Ela indica que a localização informada pelo tracker do EPI diverge da localização observada
        pela câmera e deve ser investigada.
      </div>
      {list.length === 0 ? (
        <div style={{ padding: "36px 20px", textAlign: "center" }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#3d4148", marginBottom: 6 }}>Nenhuma inconsistência registrada</div>
          <div style={{ fontSize: 13, color: "#8a919c" }}>O sistema não identificou divergências entre a localização do tracker e a observação da câmera.</div>
        </div>
      ) : (
        <Table
          columns={[
            { key: "timestamp", label: "Horário", render: (r) => new Date(r.timestamp).toLocaleTimeString("pt-BR") },
            { key: "employee_id", label: "Funcionário", render: (r) => r.employee_id || "Não informado" },
            { key: "area_id", label: "Área observada pela camera" },
            { key: "ppe_id", label: "EPI" },
            { key: "ppe_area_id", label: "Localização do tracker do EPI" },
          ]}
          rows={list.map((i, idx) => Object.assign({}, i, { __key: idx }))}
        />
      )}
    </Panel>
  );
}
