import React from "react";
import { Panel, LoadingState, ErrorState, EmptyState } from "../components/Common.jsx";
import { Dot } from "../components/StatusIndicators.jsx";

function areaStatus(employeeCount, nonCompliantCount, hasTrackers) {
  if (nonCompliantCount > 0) return { label: "Atenção", color: "red" };
  if (employeeCount === 0 && !hasTrackers) return { label: "Sem movimento", color: "gray" };
  return { label: "Normal", color: "green" };
}

function MetricCard({ title, value, context, color }) {
  const dotColor = color || "gray";
  return (
    <div style={{ background: "#fff", border: "1px solid #e6e8eb", borderRadius: 10, padding: "18px 20px", flex: "1 1 200px", minWidth: 190 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ fontSize: 13, color: "#5a6270", fontWeight: 500 }}>{title}</div>
        <Dot color={dotColor} />
      </div>
      <div style={{ fontSize: 30, fontWeight: 700, color: "#161a1f", marginTop: 6, lineHeight: 1 }}>{value}</div>
      {context && <div style={{ fontSize: 12, color: "#8a919c", marginTop: 8 }}>{context}</div>}
    </div>
  );
}

export function Dashboard(props) {
  const { trackers, employees, ppeList, inconsistencies, events, areas, checkpoints, loading, error, onRetry, onNavigate } = props;
  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;

  const trackerList = trackers || [];
  const employeeList = employees || [];
  const ppeListAll = ppeList || [];
  const inconsistencyList = inconsistencies || [];
  const eventList = events || [];
  const areaList = areas || [];
  const checkpointList = checkpoints || [];

  const trackersOnline = trackerList.filter((t) => t.status === "ACTIVE").length;
  const trackersOffline = trackerList.filter((t) => t.status === "OFFLINE").length;
  const trackersLowBattery = trackerList.filter((t) => t.status === "LOW_BATTERY").length;

  const employeesWithCheck = employeeList.filter((e) => e.last_check);
  const compliantCount = employeesWithCheck.filter((e) => e.last_check.status === "COMPLIANT").length;
  const nonCompliantCount = employeesWithCheck.filter((e) => e.last_check.status === "NON_COMPLIANT").length;

  const employeesByArea = {};
  employeeList.forEach((e) => {
    if (!e.current_area_id) return;
    (employeesByArea[e.current_area_id] = employeesByArea[e.current_area_id] || []).push(e);
  });
  const trackersByArea = {};
  trackerList.forEach((t) => {
    if (!t.last_area_id) return;
    (trackersByArea[t.last_area_id] = trackersByArea[t.last_area_id] || []).push(t);
  });

  return (
    <div>
      <div style={{ marginBottom: 22 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0, color: "#161a1f" }}>Visão geral da operação</h1>
        <div style={{ fontSize: 13, color: "#8a919c", marginTop: 4 }}>
          Monitoramento de EPIs por localização de rastreadores, complementar à verificação por câmera.
        </div>
      </div>

      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 26 }}>
        <MetricCard title="Funcionários monitorados" value={employeeList.length} color="blue"
          context={employeeList.length === 0 ? "Nenhum funcionário associado ainda" : `${Object.keys(employeesByArea).length} área(s) com movimento`} />
        <MetricCard title="Trackers ativos" value={trackersOnline} color="green" context={`${trackerList.length} cadastrado(s) no total`} />
        <MetricCard title="Trackers offline" value={trackersOffline} color={trackersOffline > 0 ? "red" : "gray"} />
        <MetricCard title="Bateria baixa" value={trackersLowBattery} color={trackersLowBattery > 0 ? "amber" : "gray"} />
        <MetricCard title="EPIs monitorados" value={ppeListAll.length} color="blue" />
        <MetricCard title="Inconsistências" value={inconsistencyList.length} color={inconsistencyList.length > 0 ? "orange" : "gray"}
          context="Divergências entre câmera e tracker" />
      </div>

      <div style={{ display: "flex", gap: 14, marginBottom: 26 }}>
        <div style={{ flex: 1, background: "#fff", border: "1px solid #e6e8eb", borderRadius: 10, padding: "18px 20px" }}>
          <div style={{ fontSize: 13, color: "#5a6270", fontWeight: 500, marginBottom: 6 }}>Conformidade</div>
          {employeesWithCheck.length === 0 ? (
            <div>
              <div style={{ fontSize: 22, fontWeight: 700, color: "#8a919c" }}>Aguardando verificações</div>
              <div style={{ fontSize: 12, color: "#8a919c", marginTop: 4 }}>Nenhuma verificação de segurança foi registrada ainda.</div>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 30, fontWeight: 700, color: "#0f7938" }}>{compliantCount}<span style={{ fontSize: 15, color: "#8a919c", fontWeight: 500 }}> de {employeesWithCheck.length} verificações conformes</span></div>
              <div style={{ fontSize: 12, color: nonCompliantCount > 0 ? "#c0281f" : "#8a919c", marginTop: 6 }}>
                {nonCompliantCount > 0 ? `${nonCompliantCount} verificação(ões) não conforme(s)` : "Nenhuma não conformidade registrada"}
              </div>
            </div>
          )}
        </div>
      </div>

      <Panel title="Visão operacional" actions={<button onClick={() => onNavigate("map")} style={{ fontSize: 12, padding: "5px 12px", border: "1px solid #d7dbe0", borderRadius: 6, background: "#fff", cursor: "pointer", color: "#3d4148" }}>Ver mapa completo</button>}>
        {areaList.length === 0 ? (
          <EmptyState message="Nenhuma área cadastrada ainda. As áreas operacionais aparecerão aqui quando forem cadastradas." />
        ) : (
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {areaList.map((area) => {
              const emps = employeesByArea[area.area_id] || [];
              const trks = trackersByArea[area.area_id] || [];
              const nc = emps.filter((e) => e.last_check && e.last_check.status === "NON_COMPLIANT").length;
              const status = areaStatus(emps.length, nc, trks.length > 0);
              const areaCheckpoints = checkpointList.filter((c) => c.area_id === area.area_id);
              return (
                <div
                  key={area.area_id}
                  onClick={() => onNavigate("map")}
                  style={{
                    border: "1px solid #e6e8eb", borderRadius: 10, padding: 14, minWidth: 190, cursor: "pointer", background: "#fbfbfc",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                    <div style={{ fontWeight: 600, fontSize: 13, color: "#161a1f" }}>{area.name}</div>
                    <Dot color={status.color} />
                  </div>
                  <div style={{ fontSize: 12, color: "#5a6270" }}>{emps.length} funcionário(s) - {trks.length} tracker(s)</div>
                  <div style={{ fontSize: 12, color: "#5a6270" }}>{areaCheckpoints.length} checkpoint(s)</div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: status.color === "red" ? "#c0281f" : status.color === "green" ? "#0f7938" : "#8a919c", marginTop: 6 }}>
                    {status.label.toUpperCase()}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
}
