import React, { useState, useMemo } from "react";
import { Panel, EmptyState, LoadingState, ErrorState } from "../components/Common.jsx";
import { translateEvent, eventIcon, EVENT_CATEGORIES } from "../utils/labels.js";

const FILTERS = [
  { key: "todos", label: "Todos" },
  { key: "trackers", label: "Trackers" },
  { key: "localizacao", label: "Localização" },
  { key: "epis", label: "EPIs" },
  { key: "funcionarios", label: "Funcionários" },
  { key: "alertas", label: "Alertas" },
];

// Agrupa eventos IDENTICOS consecutivos (seção 12 do pedido de refinamento)
// para não poluir a tela com muitas linhas repetidas seguidas.
function groupConsecutive(events) {
  const groups = [];
  for (const ev of events) {
    const last = groups[groups.length - 1];
    if (last && last.event === ev.event && last.items.length < 500) {
      last.items.push(ev);
    } else {
      groups.push({ event: ev.event, items: [ev] });
    }
  }
  return groups;
}

export function History(props) {
  const { events, loading, error, onRetry } = props;
  const [filter, setFilter] = useState("todos");

  const filtered = useMemo(() => {
    const list = (events || []).slice().reverse(); // mais recente primeiro
    if (filter === "todos") return list;
    const allowed = EVENT_CATEGORIES[filter] || [];
    return list.filter((e) => allowed.includes(e.event));
  }, [events, filter]);

  const grouped = useMemo(() => groupConsecutive(filtered), [filtered]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;

  return (
    <Panel title="Histórico de eventos">
      <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" }}>
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            style={{
              padding: "5px 12px", fontSize: 12, borderRadius: 999, cursor: "pointer",
              border: "1px solid " + (filter === f.key ? "#1c50a8" : "#d7dbe0"),
              background: filter === f.key ? "#eaf1fd" : "#fff",
              color: filter === f.key ? "#1c50a8" : "#5a6270",
              fontWeight: filter === f.key ? 600 : 400,
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {grouped.length === 0 ? (
        <EmptyState message="Nenhum evento registrado ainda." />
      ) : (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {grouped.map((group, idx) => {
            const first = group.items[0];
            const count = group.items.length;
            return (
              <div key={idx} style={{ display: "flex", gap: 12, padding: "10px 4px", borderBottom: "1px solid #f1f2f4", alignItems: "flex-start" }}>
                <div style={{
                  width: 30, height: 30, borderRadius: 8, background: "#f1f2f4", display: "flex", alignItems: "center",
                  justifyContent: "center", fontSize: 10, fontWeight: 700, color: "#5a6270", flexShrink: 0,
                }}>
                  {eventIcon(first.event)}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#161a1f" }}>
                    {translateEvent(first.event)}
                    {count > 1 && <span style={{ fontWeight: 400, color: "#8a919c" }}> — {count} ocorrências</span>}
                  </div>
                  <div style={{ fontSize: 11, color: "#9aa1ac", fontFamily: "ui-monospace, monospace", marginTop: 2 }}>
                    {JSON.stringify(first.payload)}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Panel>
  );
}
