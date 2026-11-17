import React from "react";
import { translateStatus } from "../utils/labels.js";

const STATUS_COLORS = {
  ONLINE: "green",
  ACTIVE: "green",
  OFFLINE: "red",
  LOW_BATTERY: "amber",
  CURRENT: "green",
  LAST_KNOWN: "amber",
  EXPIRED: "gray",
  COMPLIANT: "green",
  NON_COMPLIANT: "red",
  INDETERMINATE: "amber",
  NOT_EVALUATED: "gray",
  UNKNOWN: "gray",
  CONFLICTING: "orange",
  DETECTED: "green",
  NOT_DETECTED: "gray",
  ASSIGNED: "blue",
  REGISTERED: "gray",
  ATTENTION: "amber",
  CRITICAL: "red",
  WARNING: "amber",
  INFO: "blue",
  OPEN: "orange",
  ACKNOWLEDGED: "gray",
  RESOLVED: "green",
};

const COLOR_STYLES = {
  green: { bg: "#eefaf1", fg: "#0f7938", border: "#bfe8cd" },
  red: { bg: "#fdeeed", fg: "#c0281f", border: "#f2c2bd" },
  amber: { bg: "#fff8e8", fg: "#93650a", border: "#f1dfaf" },
  gray: { bg: "#f3f4f6", fg: "#5a6270", border: "#dde1e6" },
  orange: { bg: "#fff2e8", fg: "#a8480f", border: "#f2cba9" },
  blue: { bg: "#eaf1fd", fg: "#1c50a8", border: "#bcd3f5" },
};

export function Dot({ color }) {
  const style = COLOR_STYLES[color] || COLOR_STYLES.gray;
  return <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: style.fg }} />;
}

export function StatusBadge({ status, label }) {
  const color = STATUS_COLORS[status] || "gray";
  const style = COLOR_STYLES[color];
  const text = label || translateStatus(status);
  return (
    <span
      style={{
        display: "inline-flex", alignItems: "center", gap: 6, padding: "3px 10px", borderRadius: 999,
        fontSize: 12, fontWeight: 600, background: style.bg, color: style.fg, border: "1px solid " + style.border,
        whiteSpace: "nowrap",
      }}
    >
      <Dot color={color} />
      {text}
    </span>
  );
}

export function HealthBadge({ online }) {
  return <StatusBadge status={online ? "ONLINE" : "OFFLINE"} label={online ? "Sistema online" : "API indisponível"} />;
}

export function ComplianceBadge({ status }) {
  if (!status) return <StatusBadge status="NOT_EVALUATED" label="Sem verificação" />;
  return <StatusBadge status={status} />;
}

export function BatteryIndicator({ level }) {
  if (level === null || level === undefined) {
    return <span style={{ color: "#9aa1ac", fontSize: 12 }}>Não informado</span>;
  }
  const pct = Math.round(level * 100);
  const color = pct < 15 ? "#c0281f" : pct < 35 ? "#93650a" : "#0f7938";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 12 }}>
      <span style={{ width: 46, height: 8, borderRadius: 4, background: "#e7e9ec", overflow: "hidden", display: "inline-block" }}>
        <span style={{ display: "block", width: pct + "%", height: "100%", background: color }} />
      </span>
      <span style={{ color: "#3d4148", fontVariantNumeric: "tabular-nums" }}>{pct}%</span>
    </span>
  );
}

export function SignalIndicator({ strength }) {
  if (strength === null || strength === undefined) {
    return <span style={{ color: "#9aa1ac", fontSize: 12 }}>Não informado</span>;
  }
  let label = "Sinal fraco";
  let color = "#93650a";
  if (strength >= 0.7) {
    label = "Sinal forte";
    color = "#0f7938";
  } else if (strength >= 0.4) {
    label = "Sinal médio";
    color = "#3d6fd6";
  }
  return <span style={{ fontSize: 12, color }}>{label}</span>;
}

export function TechnicalValue({ label, code }) {
  return (
    <div>
      <div style={{ fontSize: 13 }}>{label}</div>
      {code && <div style={{ fontSize: 11, color: "#9aa1ac", fontFamily: "ui-monospace, monospace" }}>{code}</div>}
    </div>
  );
}
