import React, { useState } from "react";
import { Panel, LoadingState, ErrorState } from "../components/Common.jsx";
import { api } from "../services/api.js";

export function Simulation(props) {
  const { trackers, areas, loading, error, onRetry, onActionDone, notify } = props;
  const [selectedTracker, setSelectedTracker] = useState("");
  const [selectedArea, setSelectedArea] = useState("");
  const [busy, setBusy] = useState(false);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;

  const trackerOptions = trackers || [];
  const areaOptions = areas || [];

  async function run(fn, successMessage) {
    if (!selectedTracker) {
      notify("Selecione um tracker primeiro.", "error");
      return;
    }
    setBusy(true);
    try {
      await fn();
      notify(successMessage, "success");
      onActionDone();
    } catch (e) {
      notify("Falha na simulação: " + e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <Panel title="Seleção">
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
          <label style={{ fontSize: 12 }}>
            <div style={{ marginBottom: 4, color: "#57606a" }}>Tracker</div>
            <select value={selectedTracker} onChange={(e) => setSelectedTracker(e.target.value)} style={{ padding: 6, fontSize: 13, minWidth: 180 }}>
              <option value="">Selecione...</option>
              {trackerOptions.map((t) => (
                <option key={t.tracker_id} value={t.tracker_id}>{t.tracker_id} ({t.status})</option>
              ))}
            </select>
          </label>
        </div>
      </Panel>

      <Panel title="Movimentação">
        <div style={{ display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
          <label style={{ fontSize: 12 }}>
            <div style={{ marginBottom: 4, color: "#57606a" }}>Mover para</div>
            <select value={selectedArea} onChange={(e) => setSelectedArea(e.target.value)} style={{ padding: 6, fontSize: 13, minWidth: 180 }}>
              <option value="">Selecione uma área...</option>
              {areaOptions.map((a) => (
                <option key={a.area_id} value={a.area_id}>{a.name}</option>
              ))}
            </select>
          </label>
          <ActionButton
            disabled={busy || !selectedArea}
            onClick={() =>
              run(async () => {
                await api.simulateLocation(selectedTracker, selectedArea);
                await api.pollTracker(selectedTracker);
              }, `Feito: ${selectedTracker} movido para ${selectedArea}.`)
            }
          >
            Mover tracker
          </ActionButton>
        </div>
      </Panel>

      <Panel title="Simular problemas">
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <ActionButton
            disabled={busy}
            onClick={() => run(async () => { await api.simulateBattery(selectedTracker, 0.05); await api.pollTracker(selectedTracker); }, "Feito: bateria baixa simulada.")}
          >
            Simular bateria baixa
          </ActionButton>
          <ActionButton
            disabled={busy}
            onClick={() => run(async () => { await api.simulateBattery(selectedTracker, 0.9); await api.pollTracker(selectedTracker); }, "Feito: bateria normalizada.")}
          >
            Restaurar bateria
          </ActionButton>
          <ActionButton
            disabled={busy}
            onClick={() => run(async () => { await api.simulateOffline(selectedTracker); await api.pollTracker(selectedTracker); }, "Feito: tracker marcado como offline.")}
          >
            Simular offline
          </ActionButton>
          <ActionButton
            disabled={busy}
            onClick={() => run(async () => { await api.simulateOnline(selectedTracker); await api.pollTracker(selectedTracker); }, "Feito: tracker esta online novamente.")}
          >
            Restaurar online
          </ActionButton>
        </div>
      </Panel>

      <Panel title="Simular inconsistência">
        <InconsistencyForm trackers={trackerOptions} areas={areaOptions} busy={busy} setBusy={setBusy} notify={notify} onActionDone={onActionDone} />
      </Panel>
    </div>
  );
}

function ActionButton(props) {
  return (
    <button
      onClick={props.onClick}
      disabled={props.disabled}
      style={{
        padding: "8px 14px", fontSize: 13, borderRadius: 6, border: "1px solid #d0d7de",
        background: props.disabled ? "#f1f2f4" : "#1b1f24", color: props.disabled ? "#8a8f98" : "#fff",
        cursor: props.disabled ? "not-allowed" : "pointer",
      }}
    >
      {props.children}
    </button>
  );
}

function InconsistencyForm(props) {
  const { trackers, areas, busy, setBusy, notify, onActionDone } = props;
  const [employeeId, setEmployeeId] = useState("");
  const [ppeId, setPpeId] = useState("");
  const [expectedArea, setExpectedArea] = useState("");

  async function submit() {
    if (!employeeId || !ppeId || !expectedArea) {
      notify("Preencha funcionário, EPI e área esperada.", "error");
      return;
    }
    setBusy(true);
    try {
      const result = await api.checkInconsistency(employeeId, expectedArea, ppeId);
      notify(result.type ? "Feito: inconsistencia detectada e registrada." : "Nenhuma inconsistencia encontrada.", "success");
      onActionDone();
    } catch (e) {
      notify("Falha: " + e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
      <label style={{ fontSize: 12 }}>
        <div style={{ marginBottom: 4, color: "#57606a" }}>employee_id</div>
        <input value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} placeholder="FUNC-000234" style={{ padding: 6, fontSize: 13 }} />
      </label>
      <label style={{ fontSize: 12 }}>
        <div style={{ marginBottom: 4, color: "#57606a" }}>ppe_id</div>
        <input value={ppeId} onChange={(e) => setPpeId(e.target.value)} placeholder="PPE-000001" style={{ padding: 6, fontSize: 13 }} />
      </label>
      <label style={{ fontSize: 12 }}>
        <div style={{ marginBottom: 4, color: "#57606a" }}>Área esperada (câmera)</div>
        <select value={expectedArea} onChange={(e) => setExpectedArea(e.target.value)} style={{ padding: 6, fontSize: 13 }}>
          <option value="">Selecione...</option>
          {areas.map((a) => (
            <option key={a.area_id} value={a.area_id}>{a.name}</option>
          ))}
        </select>
      </label>
      <ActionButton disabled={busy} onClick={submit}>Verificar inconsistência</ActionButton>
    </div>
  );
}
