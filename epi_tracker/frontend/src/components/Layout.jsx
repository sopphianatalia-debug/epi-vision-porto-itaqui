import React from "react";
import { useSecondsAgo } from "../hooks/usePolling.js";

const NAV_SECTIONS = [
  {
    label: "Monitoramento",
    items: [
      { key: "dashboard", label: "Dashboard" },
      { key: "map", label: "Mapa operacional" },
      { key: "cameras", label: "Câmeras" },
      { key: "employees", label: "Funcionários" },
      { key: "ppe", label: "EPIs" },
      { key: "trackers", label: "Rastreadores" },
      { key: "alerts", label: "Alertas" },
      { key: "inconsistencies", label: "Inconsistências" },
      { key: "history", label: "Histórico" },
    ],
  },
  {
    label: "Administração",
    items: [
      { key: "areas", label: "Áreas" },
      { key: "checkpoints", label: "Checkpoints" },
      { key: "simulation", label: "Simulação" },
    ],
  },
];

export function Layout({ route, onNavigate, apiOnline, lastUpdated, alertCount, alertCritical, children }) {
  const secondsAgo = useSecondsAgo(lastUpdated);

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#f6f7f9", fontFamily: "system-ui, sans-serif" }}>
      <aside
        style={{
          width: 220, flexShrink: 0, background: "#12161c", color: "#c9ced6",
          display: "flex", flexDirection: "column", padding: "20px 0",
        }}
      >
        <div style={{ padding: "0 20px 20px", fontSize: 15, fontWeight: 700, color: "#fff", letterSpacing: 0.3 }}>
          EPI SAFETY
          <div style={{ fontSize: 11, fontWeight: 400, color: "#7d8590", marginTop: 2 }}>Tracker Service</div>
        </div>
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} style={{ marginBottom: 18 }}>
            <div style={{ padding: "0 20px 6px", fontSize: 10, textTransform: "uppercase", letterSpacing: 0.6, color: "#5c6472" }}>
              {section.label}
            </div>
            {section.items.map((item) => (
              <button
                key={item.key}
                onClick={() => onNavigate(item.key)}
                style={{
                  display: "block", width: "100%", textAlign: "left", padding: "8px 20px",
                  background: route === item.key ? "#1e2530" : "transparent",
                  borderTop: "none", borderRight: "none", borderBottom: "none",
                  borderLeft: route === item.key ? "3px solid #4c8dff" : "3px solid transparent",
                  color: route === item.key ? "#fff" : "#c9ced6",
                  cursor: "pointer", fontSize: 13,
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
        ))}
      </aside>

      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <header
          style={{
            height: 52, background: "#fff", borderBottom: "1px solid #e2e5e9",
            display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 24px",
          }}
        >
          <div style={{ fontSize: 13, color: "#57606a" }}>
            {secondsAgo !== null ? `Última atualização: há ${secondsAgo}s` : "Carregando..."}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 18, fontSize: 13, fontWeight: 600 }}>
            <button
              onClick={() => onNavigate("alerts")}
              title="Alertas abertos"
              style={{
                display: "inline-flex", alignItems: "center", gap: 6, background: "transparent", border: "none",
                cursor: "pointer", fontSize: 13, fontWeight: 600, color: "#3d4148", padding: 0,
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.7 21a2 2 0 0 1-3.4 0" />
              </svg>
              {alertCount > 0 && (
                <span style={{
                  minWidth: 18, padding: "1px 6px", borderRadius: 999, fontSize: 11, textAlign: "center",
                  color: "#fff", background: alertCritical > 0 ? "#c92a2a" : "#d48806",
                }}>{alertCount}</span>
              )}
            </button>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span
                style={{
                  width: 8, height: 8, borderRadius: "50%",
                  background: apiOnline ? "#1a7f37" : "#c92a2a",
                }}
              />
              {apiOnline ? "SISTEMA ONLINE" : "API INDISPONÍVEL"}
            </div>
          </div>
        </header>
        <main style={{ flex: 1, padding: 24, overflow: "auto" }}>{children}</main>
      </div>
    </div>
  );
}
