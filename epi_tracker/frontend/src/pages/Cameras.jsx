import React, { useState } from "react";
import { Card, Panel, EmptyState, LoadingState } from "../components/Common.jsx";
import { api, fusionApi } from "../services/api.js";
import { usePolling } from "../hooks/usePolling.js";
import { SECTORS, sectorByCode, healthLevel } from "../config/itaqui.js";

const PPE_LABELS = { helmet: "Capacete", vest: "Colete", gloves: "Luvas", boots: "Botas", glasses: "Óculos", mask: "Máscara" };
const STATUS_LABELS = {
  DETECTED: ["Detectado", "#1a7f37"], MISSING: ["Ausente", "#cf222e"], NOT_VISIBLE: ["Não observável", "#8b949e"],
  NOT_OBSERVED: ["Sem observação", "#8b949e"], LOW_CONFIDENCE: ["Baixa confiança", "#bf8700"],
  CONFLICTING: ["Evidências conflitantes", "#bf8700"], IMPROPER: ["Uso incorreto", "#cf222e"], UNKNOWN: ["Desconhecido", "#8b949e"],
};
const FRESH_SECONDS = 60; // "visto recentemente" = últimos 60 s

// Cadastro de câmeras (Tracker) e leitura de visão (Fusion) são independentes: uma falha não esconde a outra.
const toUi = (c) => ({ id: c.camera_id, name: c.name, sector: c.sector, kind: c.kind, pos: c.pos, example: !!c.example, active: c.active !== false, latitude: c.latitude ?? null, longitude: c.longitude ?? null });

async function fetchCameras() {
  let registered = [], registryError = null;
  try {
    registered = (await api.listCameras()).map(toUi);
  } catch (e) {
    registryError = e.message || "falha ao ler o cadastro de câmeras";
  }
  try {
    const [health, states, anonymous] = await Promise.all([
      fusionApi.camerasHealth(), fusionApi.allStates(), fusionApi.anonymous(200),
    ]);
    return { offline: false, registered, registryError, health: health.cameras || [], states: states || [], anonymous: anonymous || [] };
  } catch (e) {
    return { offline: true, registered, registryError, health: [], states: [], anonymous: [] };
  }
}

function ago(iso) {
  if (!iso) return "—";
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `há ${s}s`;
  if (s < 3600) return `há ${Math.round(s / 60)} min`;
  return `há ${Math.round(s / 3600)} h`;
}
const isFresh = (iso) => iso && Date.now() - new Date(iso).getTime() <= FRESH_SECONDS * 1000;

// Pessoas vistas por uma câmera: identificadas (do estado consolidado) + não identificadas.
function peopleAt(cameraId, states, anonymous) {
  const identified = [];
  states.forEach((st) => {
    const obs = (st.observations || {})[cameraId];
    if (obs) identified.push({ code: st.employee_id, track: obs.track_id, lastSeen: obs.last_seen, ppe: st.ppe || {}, visible: obs.visible || [] });
  });
  // Não identificados: o Fusion guarda uma linha por leitura. Aqui contamos UMA pessoa por track (a mais recente).
  const latestByTrack = {};
  anonymous.filter((a) => a.camera_id === cameraId).forEach((a) => {
    const prev = latestByTrack[a.person_track_id];
    if (!prev || new Date(a.timestamp) > new Date(prev.timestamp)) latestByTrack[a.person_track_id] = a;
  });
  const anon = Object.values(latestByTrack)
    .map((a) => ({ code: null, track: a.person_track_id, lastSeen: a.timestamp, ppe: a.ppe || {}, visible: [] }));
  return [...identified, ...anon].sort((a, b) => new Date(b.lastSeen) - new Date(a.lastSeen));
}

function PpeChips({ ppe }) {
  const keys = Object.keys(ppe);
  if (keys.length === 0) return <span style={{ color: "#8a8f98", fontSize: 12 }}>sem leitura de EPI</span>;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {keys.map((k) => {
        const st = ppe[k].status; const [label, color] = STATUS_LABELS[st] || [st, "#8b949e"];
        // Só estados com leitura de fato mostram confiança; "sem observação"/"não observável" não têm número útil.
        const showConf = ["DETECTED", "MISSING", "IMPROPER", "LOW_CONFIDENCE"].includes(st) && ppe[k].confidence != null;
        const conf = showConf ? ` ${Math.round(ppe[k].confidence * 100)}%` : "";
        return (
          <span key={k} style={{ fontSize: 11, padding: "2px 8px", borderRadius: 999, border: `1px solid ${color}`, color }}>
            {PPE_LABELS[k] || k}: {label}{conf}
          </span>
        );
      })}
    </div>
  );
}

function CameraDot({ cam, health, selected, onClick }) {
  const lvl = healthLevel(health);
  const size = 26;
  return (
    <button
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      title={`${cam.name} (${cam.id}) — saúde: ${lvl.label}`}
      aria-label={`${cam.name}, saúde ${lvl.label}`}
      style={{
        position: "absolute", left: `${cam.pos.x}%`, top: `${cam.pos.y}%`, transform: "translate(-50%, -50%)",
        width: size, height: size, cursor: "pointer", background: lvl.color, color: "#fff", fontSize: 11, fontWeight: 700,
        border: selected ? "3px solid #4c8dff" : "2px solid #fff", boxShadow: "0 1px 4px rgba(0,0,0,.35)",
        borderRadius: cam.kind === "ENTRADA" ? 4 : "50%", padding: 0,
      }}
    >
      {cam.kind === "ENTRADA" ? "E" : "I"}
    </button>
  );
}

function SchematicMap({ cameras, healthById, selectedId, onSelect, countsBySector, selectedSector, onSelectSector }) {
  return (
    <div style={{ position: "relative", width: "100%", aspectRatio: "14 / 9", minHeight: 360, background: "#eef3f8", borderRadius: 8, border: "1px solid #d0d7de" }}>
      <div style={{ position: "absolute", inset: 0 }}>
        {SECTORS.map((s) => {
          const c = countsBySector[s.code] || { cameras: 0, people: 0 };
          return (
            <div key={s.code} role="button" tabIndex={0} aria-label={`Setor ${s.name}`}
              onClick={() => onSelectSector(s.code)} onKeyDown={(e) => { if (e.key === "Enter") onSelectSector(s.code); }}
              style={{
              position: "absolute", left: `${s.box.x}%`, top: `${s.box.y}%`, width: `${s.box.w}%`, height: `${s.box.h}%`,
              background: selectedSector === s.code ? "#eaf1fd" : "#fff", cursor: "pointer", boxSizing: "border-box", borderRadius: 6,
              border: selectedSector === s.code ? "2px solid #4c8dff" : "1px solid #b6c2d0",
            }}>
              <div style={{ padding: "6px 8px 2px", fontSize: 12, fontWeight: 700, color: "#1b1f24", lineHeight: 1.2 }}>{s.name}</div>
              {s.berths.length > 0 && <div style={{ padding: "0 8px", fontSize: 10, color: "#57606a" }}>Berços {s.berths.join(", ")}</div>}
              <div style={{ padding: "0 8px", fontSize: 10, color: "#57606a" }}>{c.cameras} câm. · {c.people} pessoa(s)</div>
              {cameras.filter((cam) => cam.sector === s.code).map((cam) => (
                <CameraDot key={cam.id} cam={cam} health={healthById[cam.id]} selected={selectedId === cam.id} onClick={() => onSelect(cam.id)} />
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Legend() {
  const items = [["Boa", "#1a7f37"], ["Atenção", "#bf8700"], ["Baixa", "#cf222e"], ["Sem dados", "#8b949e"]];
  return (
    <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12, color: "#57606a", marginTop: 10 }}>
      <span>Saúde da câmera:</span>
      {items.map(([l, c]) => (
        <span key={l}><span style={{ display: "inline-block", width: 10, height: 10, background: c, borderRadius: "50%", marginRight: 4 }} />{l}</span>
      ))}
      <span>■ E = entrada do setor (checkpoint) · ● I = interna</span>
    </div>
  );
}

function CameraDetail({ cam, health, people }) {
  const lvl = healthLevel(health);
  const sector = sectorByCode(cam.sector);
  const fmtRate = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
  return (
    <div>
      <div style={{ fontSize: 16, fontWeight: 700 }}>{cam.name}</div>
      <div style={{ fontSize: 12, color: "#57606a", marginBottom: 10 }}>
        {cam.id} · {sector ? sector.name : "sem setor definido"} · {cam.kind === "ENTRADA" ? "entrada do setor" : cam.kind === "INTERNA" ? "interna" : "tipo não informado"}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10, marginBottom: 14 }}>
        <Card title="Saúde operacional" value={lvl.label} hint={health?.health_score != null ? `índice ${Math.round(health.health_score)} de 100` : "sem dados"} accent={lvl.color} />
        <Card title="Observações" value={health ? health.observations : 0} hint="recebidas pelo Fusion" />
        <Card title="Identificação" value={fmtRate(health?.identity_match_rate)} hint={`${health ? health.anonymous : 0} sem identidade`} />
        <Card title="Não observável" value={fmtRate(health?.not_visible_rate)} hint="EPI fora de vista" />
      </div>
      <div style={{ fontSize: 12, color: "#57606a", marginBottom: 6 }}>Pessoas vistas por esta câmera</div>
      {people.length === 0 ? <EmptyState message="Nenhuma pessoa vista por esta câmera ainda." /> : people.map((p, i) => (
        <div key={`${p.track}-${i}`} style={{ border: "1px solid #e2e5e9", borderRadius: 8, padding: 10, marginBottom: 8, opacity: isFresh(p.lastSeen) ? 1 : 0.65 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 6 }}>
            <strong>{p.code ? p.code : "Não identificado"}</strong>
            <span style={{ color: "#8a8f98", fontSize: 12 }}>{p.track} · {ago(p.lastSeen)}{isFresh(p.lastSeen) ? "" : " (não recente)"}</span>
          </div>
          <PpeChips ppe={p.ppe} />
        </div>
      ))}
      <div style={{ fontSize: 11, color: "#8a8f98", marginTop: 8 }}>
        Mostra o que a câmera enxergou. A conformidade é decidida pelas Regras (ver Alertas). Sem imagens ou dados biométricos.
      </div>
    </div>
  );
}

const KIND_LABEL = { ENTRADA: "Entrada do setor (checkpoint)", INTERNA: "Interna (movimentação no setor)" };

function ExampleBadge() {
  return <span style={{ fontSize: 10, marginLeft: 6, padding: "1px 6px", borderRadius: 999, background: "#eef0f2", color: "#57606a" }}>exemplo</span>;
}

function CameraRow({ cam, health, freshCount, onClick }) {
  const lvl = healthLevel(health);
  return (
    <button onClick={onClick} style={{
      display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", textAlign: "left", padding: "8px 10px",
      cursor: "pointer", background: "#fff", border: "1px solid #e2e5e9", borderRadius: 6, marginBottom: 6, fontSize: 13,
    }}>
      <span>{cam.name}{cam.example && <ExampleBadge />} <span style={{ color: "#8a8f98" }}>({cam.id})</span></span>
      <span style={{ whiteSpace: "nowrap" }}>
        <span style={{ color: "#57606a", marginRight: 10 }}>{freshCount} pessoa(s)</span>
        <span style={{ color: lvl.color, fontWeight: 600 }}>{lvl.label}</span>
      </span>
    </button>
  );
}

function SectorDetail({ sector, cams, healthById, peopleOf, onSelectCamera }) {
  const entradas = cams.filter((c) => c.kind === "ENTRADA");
  const internas = cams.filter((c) => c.kind !== "ENTRADA");
  // Funcionários vistos por alguma câmera deste setor (a leitura mais recente de cada um) + não identificados
  const seen = {}; let anonCount = 0;
  cams.forEach((c) => peopleOf(c.id).filter((p) => isFresh(p.lastSeen)).forEach((p) => {
    if (!p.code) { anonCount += 1; return; }
    if (!seen[p.code] || new Date(p.lastSeen) > new Date(seen[p.code].lastSeen)) seen[p.code] = { ...p, camera: c };
  }));
  const seenList = Object.values(seen).sort((a, b) => new Date(b.lastSeen) - new Date(a.lastSeen));
  const group = (title, list, empty) => (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 12, color: "#57606a", marginBottom: 6, fontWeight: 600 }}>{title} ({list.length})</div>
      {list.length === 0 ? <div style={{ fontSize: 12, color: "#8a8f98", marginBottom: 4 }}>{empty}</div> : list.map((c) => (
        <CameraRow key={c.id} cam={c} health={healthById[c.id]} freshCount={peopleOf(c.id).filter((p) => isFresh(p.lastSeen)).length} onClick={() => onSelectCamera(c.id)} />
      ))}
    </div>
  );
  return (
    <div>
      <div style={{ fontSize: 16, fontWeight: 700 }}>{sector.name}</div>
      <div style={{ fontSize: 12, color: "#57606a", marginBottom: 12 }}>
        {sector.description}{sector.berths.length ? ` · Berços ${sector.berths.join(", ")}` : ""}
      </div>
      {group("Câmeras de entrada (checkpoint)", entradas, "Nenhuma câmera de entrada cadastrada neste setor.")}
      {group("Câmeras internas (movimentação)", internas, "Nenhuma câmera interna cadastrada neste setor.")}
      <div style={{ fontSize: 12, color: "#57606a", marginBottom: 6, fontWeight: 600 }}>Vistos neste setor nos últimos {FRESH_SECONDS}s</div>
      {seenList.length === 0 && anonCount === 0 ? <div style={{ fontSize: 12, color: "#8a8f98" }}>Ninguém visto agora.</div> : (
        <div style={{ fontSize: 13 }}>
          {seenList.map((p) => (
            <div key={p.code} style={{ padding: "4px 0", display: "flex", justifyContent: "space-between" }}>
              <strong>{p.code}</strong>
              <span style={{ color: "#57606a" }}>{p.camera.name} · {ago(p.lastSeen)}</span>
            </div>
          ))}
          {anonCount > 0 && <div style={{ padding: "4px 0", color: "#57606a" }}>{anonCount} pessoa(s) não identificada(s)</div>}
        </div>
      )}
      <div style={{ fontSize: 11, color: "#8a8f98", marginTop: 8 }}>
        "Visto" significa que uma câmera do setor enxergou a pessoa; não é registro oficial de presença nem decide conformidade.
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Gerenciar câmeras: cadastrar, editar e excluir sem mexer no código.
// ---------------------------------------------------------------------------
const EMPTY_FORM = { camera_id: "", name: "", sector: "", kind: "INTERNA", x: 50, y: 50, latitude: "", longitude: "", example: false, active: true };
const inputStyle = { padding: "6px 8px", border: "1px solid #cfd4da", borderRadius: 6, fontSize: 13, width: "100%", boxSizing: "border-box" };

function CameraAdmin({ cameras, orphanIds, onChanged }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [editing, setEditing] = useState(null);       // camera_id em edição (null = criando)
  const [msg, setMsg] = useState(null);               // { kind: "ok" | "err", text }
  const [confirmDel, setConfirmDel] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const startEdit = (c) => {
    setEditing(c.id); setMsg(null); setConfirmDel(null);
    setForm({ camera_id: c.id, name: c.name, sector: c.sector || "", kind: c.kind || "INTERNA",
      x: c.pos?.x ?? 50, y: c.pos?.y ?? 50, latitude: c.latitude ?? "", longitude: c.longitude ?? "", example: !!c.example, active: c.active !== false });
  };
  const startCreate = (id = "") => { setEditing(null); setMsg(null); setForm({ ...EMPTY_FORM, camera_id: id }); };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setMsg(null);
    const body = { camera_id: form.camera_id.trim(), name: form.name, sector: form.sector || null, kind: form.kind,
      pos: { x: Number(form.x), y: Number(form.y) }, active: form.active, example: form.example,
      latitude: form.latitude === "" ? null : Number(form.latitude), longitude: form.longitude === "" ? null : Number(form.longitude) };
    try {
      if (editing) await api.updateCamera(editing, body); else await api.createCamera(body);
      const text = editing ? "Câmera atualizada." : "Câmera cadastrada.";
      startCreate(); setMsg({ kind: "ok", text }); onChanged();   // limpa o formulário e DEPOIS mostra a mensagem
    } catch (err) {
      const d = err.message || "erro";
      setMsg({ kind: "err", text: typeof d === "string" ? d : JSON.stringify(d) });
    } finally { setBusy(false); }
  };

  const remove = async (id) => {
    setBusy(true); setMsg(null);
    try { await api.deleteCamera(id); setConfirmDel(null); if (editing === id) startCreate(); setMsg({ kind: "ok", text: "Câmera excluída." }); onChanged(); }
    catch (err) { setMsg({ kind: "err", text: err.message || "erro ao excluir" }); }
    finally { setBusy(false); }
  };

  const field = (label, node) => (
    <label style={{ display: "block", fontSize: 12, color: "#57606a" }}>{label}<div style={{ marginTop: 3 }}>{node}</div></label>
  );
  return (
    <Panel title="Gerenciar câmeras">
      <div style={{ fontSize: 12, color: "#57606a", marginBottom: 12 }}>
        O ID precisa ser o mesmo que a câmera envia (<code>--camera-id</code>). Setor, tipo, posição e coordenadas só descrevem a câmera no mapa; não decidem conformidade. Latitude e longitude (graus decimais) devem ser informadas juntas.
        {orphanIds.length > 0 && <> Câmeras enviando dados sem cadastro: {orphanIds.map((id) => (
          <button key={id} type="button" onClick={() => startCreate(id)} style={{ marginLeft: 6, fontSize: 12, cursor: "pointer" }}>cadastrar {id}</button>
        ))}</>}
      </div>
      <form onSubmit={submit} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 10, marginBottom: 12 }}>
        {field("ID da câmera", <input style={inputStyle} value={form.camera_id} disabled={!!editing} required onChange={(e) => set("camera_id", e.target.value)} />)}
        {field("Nome", <input style={inputStyle} value={form.name} required onChange={(e) => set("name", e.target.value)} />)}
        {field("Setor", (
          <select style={inputStyle} value={form.sector} onChange={(e) => set("sector", e.target.value)}>
            <option value="">(sem setor)</option>
            {SECTORS.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>))}
        {field("Tipo", (
          <select style={inputStyle} value={form.kind} onChange={(e) => set("kind", e.target.value)}>
            <option value="ENTRADA">Entrada (checkpoint)</option>
            <option value="INTERNA">Interna (movimentação)</option>
          </select>))}
        {field("Posição X (%)", <input style={inputStyle} type="number" min="0" max="100" step="1" value={form.x} onChange={(e) => set("x", e.target.value)} />)}
        {field("Posição Y (%)", <input style={inputStyle} type="number" min="0" max="100" step="1" value={form.y} onChange={(e) => set("y", e.target.value)} />)}
        {field("Latitude (opcional)", <input style={inputStyle} type="number" min="-90" max="90" step="any" placeholder="-2.5700" value={form.latitude} onChange={(e) => set("latitude", e.target.value)} />)}
        {field("Longitude (opcional)", <input style={inputStyle} type="number" min="-180" max="180" step="any" placeholder="-44.3600" value={form.longitude} onChange={(e) => set("longitude", e.target.value)} />)}
        <div style={{ display: "flex", alignItems: "flex-end", gap: 8 }}>
          <button type="submit" disabled={busy} style={{ padding: "7px 12px", cursor: "pointer" }}>{editing ? "Salvar alterações" : "Cadastrar câmera"}</button>
          {editing && <button type="button" onClick={() => startCreate()} style={{ padding: "7px 12px", cursor: "pointer" }}>Cancelar</button>}
        </div>
      </form>
      {editing && (
        <label style={{ fontSize: 12, color: "#57606a", display: "block", marginBottom: 8 }}>
          <input type="checkbox" checked={form.active} onChange={(e) => set("active", e.target.checked)} /> câmera ativa (inativa some do mapa e das contagens)
        </label>
      )}
      {msg && <div style={{ fontSize: 13, marginBottom: 10, color: msg.kind === "ok" ? "#1a7f37" : "#cf222e" }}>{msg.text}</div>}
      {cameras.length === 0 ? <div style={{ fontSize: 13, color: "#8a8f98" }}>Nenhuma câmera cadastrada.</div> : (
        <div>
          {cameras.map((c) => (
            <div key={c.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0", borderTop: "1px solid #eef0f2", fontSize: 13, gap: 8, flexWrap: "wrap" }}>
              <span>
                <strong>{c.name}</strong>{c.example && <ExampleBadge />}{!c.active && <span style={{ marginLeft: 6, color: "#8a8f98" }}>(inativa)</span>}
                <span style={{ color: "#8a8f98" }}> ({c.id}) · {sectorByCode(c.sector)?.name || "sem setor"} · {c.kind === "ENTRADA" ? "entrada" : "interna"}{c.latitude != null && c.longitude != null ? ` · ${Number(c.latitude).toFixed(5)}, ${Number(c.longitude).toFixed(5)}` : ""}</span>
              </span>
              <span style={{ whiteSpace: "nowrap" }}>
                <button type="button" onClick={() => startEdit(c)} style={{ marginRight: 6, cursor: "pointer" }}>Editar</button>
                {confirmDel === c.id ? (
                  <>
                    <button type="button" disabled={busy} onClick={() => remove(c.id)} style={{ marginRight: 6, cursor: "pointer", color: "#cf222e" }}>Confirmar exclusão</button>
                    <button type="button" onClick={() => setConfirmDel(null)} style={{ cursor: "pointer" }}>Não</button>
                  </>
                ) : <button type="button" onClick={() => setConfirmDel(c.id)} style={{ cursor: "pointer" }}>Excluir</button>}
              </span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

export function Cameras() {
  const { data, loading, refresh } = usePolling(fetchCameras, 2000, []);
  const [selectedSector, setSelectedSector] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  if (loading && !data) return <LoadingState />;
  const { offline, health, states, anonymous, registered: allRegistered, registryError } =
    data || { offline: true, health: [], states: [], anonymous: [], registered: [], registryError: null };
  const CAMERAS = allRegistered.filter((c) => c.active);   // só câmeras ativas entram no mapa e nas contagens

  const healthById = {}; health.forEach((h) => { healthById[h.camera_id] = h; });
  const registered = new Set(allRegistered.map((c) => c.id));
  // Câmeras que mandam dados ao Fusion mas não estão cadastradas: aparecem, nunca são escondidas.
  const orphans = health.filter((h) => !registered.has(h.camera_id))
    .map((h) => ({ id: h.camera_id, name: h.camera_id, sector: null, kind: null, pos: { x: 50, y: 50 } }));
  const allCams = [...CAMERAS, ...orphans];
  const peopleOf = (id) => peopleAt(id, states, anonymous);

  const countsBySector = {};
  CAMERAS.forEach((c) => {
    const e = (countsBySector[c.sector] = countsBySector[c.sector] || { cameras: 0, people: 0 });
    e.cameras += 1;
    e.people += peopleOf(c.id).filter((p) => isFresh(p.lastSeen)).length;
  });

  const selected = allCams.find((c) => c.id === selectedId) || null;
  const sector = sectorByCode(selectedSector);
  const pickSector = (code) => { setSelectedSector(code); setSelectedId(null); };
  const pickCamera = (id) => { setSelectedId(id); const c = allCams.find((x) => x.id === id); if (c && c.sector) setSelectedSector(c.sector); };

  let panelTitle = "Setores", panel;
  if (selected) {
    panelTitle = "Câmera selecionada";
    panel = (
      <div>
        <button onClick={() => setSelectedId(null)} style={{ marginBottom: 10, fontSize: 12, cursor: "pointer" }}>
          ← {sector ? `voltar ao setor ${sector.name}` : "voltar"}
        </button>
        <CameraDetail cam={selected} health={healthById[selected.id]} people={peopleOf(selected.id)} />
      </div>
    );
  } else if (sector) {
    panelTitle = "Setor selecionado";
    panel = (
      <div>
        <button onClick={() => pickSector(null)} style={{ marginBottom: 10, fontSize: 12, cursor: "pointer" }}>← todos os setores</button>
        <SectorDetail sector={sector} cams={CAMERAS.filter((c) => c.sector === sector.code)} healthById={healthById}
          peopleOf={peopleOf} onSelectCamera={pickCamera} />
      </div>
    );
  } else {
    panel = (
      <div>
        <div style={{ fontSize: 12, color: "#57606a", marginBottom: 8 }}>Clique em um setor (no mapa ou aqui) para ver as câmeras dele.</div>
        {SECTORS.map((s) => {
          const c = countsBySector[s.code] || { cameras: 0, people: 0 };
          const ent = CAMERAS.filter((x) => x.sector === s.code && x.kind === "ENTRADA").length;
          return (
            <button key={s.code} onClick={() => pickSector(s.code)} style={{
              display: "flex", justifyContent: "space-between", width: "100%", textAlign: "left", padding: "8px 10px", cursor: "pointer",
              background: "#fff", border: "1px solid #e2e5e9", borderRadius: 6, marginBottom: 6, fontSize: 13,
            }}>
              <span>{s.name}</span>
              <span style={{ color: "#57606a" }}>{ent} entrada · {c.cameras - ent} interna(s) · {c.people} pessoa(s)</span>
            </button>
          );
        })}
        {orphans.length > 0 && orphans.map((o) => (
          <CameraRow key={o.id} cam={{ ...o, name: `${o.id} (sem setor)` }} health={healthById[o.id]} freshCount={peopleOf(o.id).filter((p) => isFresh(p.lastSeen)).length} onClick={() => pickCamera(o.id)} />
        ))}
      </div>
    );
  }

  return (
    <div>
      <h1 style={{ fontSize: 20, margin: "0 0 4px" }}>Câmeras por setor</h1>
      <div style={{ fontSize: 12, color: "#8a8f98", marginBottom: 16 }}>
        Desenho esquemático (não é planta nem escala). Berços e descrições vêm de pesquisa; EPIs por setor ainda não validados com especialista.
      </div>
      {registryError && (
        <div style={{ background: "#fff8c5", border: "1px solid #d4a72c", padding: 10, borderRadius: 6, fontSize: 13, marginBottom: 14 }}>
          Não foi possível ler o cadastro de câmeras ({registryError}). O mapa pode estar incompleto; isso não afeta as detecções.
        </div>
      )}
      {offline && (
        <div style={{ background: "#fff8c5", border: "1px solid #d4a72c", padding: 10, borderRadius: 6, fontSize: 13, marginBottom: 14 }}>
          Fusion indisponível: não foi possível ler as câmeras agora. Isso não significa que não há pessoas ou violações.
        </div>
      )}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
        <Card title="Câmeras cadastradas" value={CAMERAS.filter((c) => !c.example).length}
          hint={`${CAMERAS.filter((c) => c.example).length} de exemplo · ${orphans.length} sem setor definido`} />
        <Card title="Câmeras enviando dados" value={health.length} hint="ao Fusion" />
        <Card title="Pessoas vistas agora" value={Object.values(countsBySector).reduce((a, c) => a + c.people, 0)} hint={`últimos ${FRESH_SECONDS}s, câmeras cadastradas`} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(440px, 1fr))", gap: 20 }}>
        <Panel title="Mapa esquemático do Porto do Itaqui">
          <SchematicMap cameras={CAMERAS} healthById={healthById} selectedId={selectedId} onSelect={pickCamera}
            countsBySector={countsBySector} selectedSector={selectedSector} onSelectSector={pickSector} />
          <Legend />
        </Panel>
        <Panel title={panelTitle}>{panel}</Panel>
      </div>
      <CameraAdmin cameras={allRegistered} orphanIds={orphans.map((o) => o.id)} onChanged={refresh} />
      {orphans.length > 0 && (
        <Panel title="Câmeras sem setor definido">
          <div style={{ fontSize: 13, color: "#57606a" }}>
            Estas câmeras enviam dados ao Fusion mas não estão cadastradas (use "Gerenciar câmeras" abaixo): {orphans.map((o) => o.id).join(", ")}.
          </div>
        </Panel>
      )}
    </div>
  );
}
