import React from "react";

export function Card({ title, value, hint, accent }) {
  return (
    <div
      style={{
        background: "#fff", border: "1px solid #e2e5e9", borderRadius: 8, padding: "16px 18px",
        borderTop: accent ? `3px solid ${accent}` : undefined, minWidth: 150,
      }}
    >
      <div style={{ fontSize: 12, color: "#57606a", marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 26, fontWeight: 700, color: "#1b1f24" }}>{value}</div>
      {hint && <div style={{ fontSize: 11, color: "#8a8f98", marginTop: 4 }}>{hint}</div>}
    </div>
  );
}

export function Panel({ title, actions, children }) {
  return (
    <div style={{ background: "#fff", border: "1px solid #e2e5e9", borderRadius: 8, marginBottom: 20 }}>
      <div
        style={{
          padding: "12px 18px", borderBottom: "1px solid #eef0f2", display: "flex",
          justifyContent: "space-between", alignItems: "center",
        }}
      >
        <h2 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "#1b1f24" }}>{title}</h2>
        <div>{actions}</div>
      </div>
      <div style={{ padding: 18 }}>{children}</div>
    </div>
  );
}

export function Table({ columns, rows, onRowClick, emptyMessage }) {
  if (!rows || rows.length === 0) {
    return <EmptyState message={emptyMessage || "Sem dados"} />;
  }
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
      <thead>
        <tr>
          {columns.map((col) => (
            <th
              key={col.key}
              style={{ textAlign: "left", padding: "8px 10px", borderBottom: "2px solid #eef0f2", color: "#57606a", fontWeight: 600 }}
            >
              {col.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr
            key={row.__key || i}
            onClick={onRowClick ? () => onRowClick(row) : undefined}
            style={{ cursor: onRowClick ? "pointer" : "default", borderBottom: "1px solid #f1f2f4" }}
          >
            {columns.map((col) => (
              <td key={col.key} style={{ padding: "8px 10px" }}>
                {col.render ? col.render(row) : row[col.key]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function EmptyState({ message }) {
  return <div style={{ padding: 30, textAlign: "center", color: "#8a8f98", fontSize: 13 }}>{message}</div>;
}

export function LoadingState() {
  return (
    <div style={{ padding: 30, textAlign: "center", color: "#8a8f98", fontSize: 13 }}>
      <div
        style={{
          display: "inline-block", width: 18, height: 18, border: "2px solid #d0d7de",
          borderTopColor: "#4c8dff", borderRadius: "50%", animation: "spin 0.8s linear infinite", marginBottom: 8,
        }}
      />
      <div>Carregando...</div>
      <style>{"@keyframes spin { to { transform: rotate(360deg); } }"}</style>
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <div style={{ padding: 20, background: "#fdecea", border: "1px solid #f3b4b0", borderRadius: 8, color: "#c92a2a", fontSize: 13 }}>
      Não foi possível consultar a API{error && error.message ? `: ${error.message}` : "."}
      {onRetry && (
        <button
          onClick={onRetry}
          style={{ marginLeft: 12, padding: "4px 10px", fontSize: 12, border: "1px solid #f3b4b0", borderRadius: 6, background: "#fff", cursor: "pointer" }}
        >
          Tentar novamente
        </button>
      )}
    </div>
  );
}

export function Toast({ message, kind, onClose }) {
  const isError = kind === "error";
  const colors = isError ? { bg: "#fdecea", fg: "#c92a2a", bd: "#f3b4b0" } : { bg: "#e6f4ea", fg: "#1a7f37", bd: "#a6d8b8" };
  return (
    <div
      style={{
        position: "fixed", bottom: 20, right: 20, padding: "10px 16px", background: colors.bg, color: colors.fg,
        border: `1px solid ${colors.bd}`, borderRadius: 8, fontSize: 13, zIndex: 1000, boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
      }}
    >
      {message}
      <button onClick={onClose} style={{ marginLeft: 12, background: "none", border: "none", cursor: "pointer", color: colors.fg }}>
        ×
      </button>
    </div>
  );
}

export function Modal({ title, onClose, children }) {
  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)", display: "flex",
        alignItems: "center", justifyContent: "center", zIndex: 900,
      }}
      onClick={onClose}
    >
      <div
        style={{ background: "#fff", borderRadius: 10, width: 520, maxWidth: "90vw", maxHeight: "85vh", overflow: "auto" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ padding: "14px 20px", borderBottom: "1px solid #eef0f2", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0, fontSize: 15 }}>{title}</h3>
          <button onClick={onClose} style={{ border: "none", background: "none", fontSize: 18, cursor: "pointer", color: "#57606a" }}>
            ×
          </button>
        </div>
        <div style={{ padding: 20 }}>{children}</div>
      </div>
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder }) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder || "Pesquisar..."}
      style={{ padding: "6px 10px", border: "1px solid #d0d7de", borderRadius: 6, fontSize: 13, width: 220 }}
    />
  );
}
