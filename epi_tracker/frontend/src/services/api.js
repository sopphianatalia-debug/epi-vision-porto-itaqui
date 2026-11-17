const ALERTS_URL = (window.__EPI_ALERTS_API__ || "http://127.0.0.1:8005") + "/api/v1";
const FUSION_URL = (window.__EPI_FUSION_API__ || "http://127.0.0.1:8002") + "/api/v1";
const BASE_URL = (window.__EPI_TRACKER_API__ || "http://127.0.0.1:8010") + "/api/v1";

async function request(path, options = {}) {
  const resp = await fetch(BASE_URL + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail || detail;
    } catch (e) {
      /* corpo não era JSON — mantém statusText */
    }
    const error = new Error(detail);
    error.status = resp.status;
    throw error;
  }
  if (resp.status === 204) return null;
  return resp.json();
}

export const api = {
  health: () => request("/health"),

  listTrackers: () => request("/trackers"),
  getTracker: (id) => request(`/trackers/${id}`),
  registerTracker: (body) => request("/trackers", { method: "POST", body: JSON.stringify(body) }),
  getTrackerLocation: (id) => request(`/trackers/${id}/location`),
  getTrackerHistory: (id) => request(`/trackers/${id}/history`),
  getFusionObservation: (id) => request(`/trackers/${id}/fusion-observation`),

  listPPE: () => request("/ppe"),
  getPPE: (id) => request(`/ppe/${id}`),
  registerPPE: (body) => request("/ppe", { method: "POST", body: JSON.stringify(body) }),
  assignPPE: (id, employeeId) =>
    request(`/ppe/${id}/assign`, { method: "POST", body: JSON.stringify({ employee_id: employeeId }) }),

  listCameras: () => request("/cameras"),
  createCamera: (body) => request("/cameras", { method: "POST", body: JSON.stringify(body) }),
  updateCamera: (id, body) => request(`/cameras/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteCamera: (id) => request(`/cameras/${encodeURIComponent(id)}`, { method: "DELETE" }),

  listAreas: () => request("/areas"),
  getArea: (id) => request(`/areas/${id}`),
  getAreaTrackers: (id) => request(`/areas/${id}/trackers`),

  listCheckpoints: () => request("/checkpoints"),

  listEmployees: () => request("/employees"),
  getEmployeeSummary: (id) => request(`/employees/${id}/summary`),

  listInconsistencies: () => request("/inconsistencies"),
  listEvents: (limit = 100) => request(`/events?limit=${limit}`),
  getMetrics: () => request("/metrics"),

  recordSafetyCheck: (body) => request("/checks", { method: "POST", body: JSON.stringify(body) }),

  // Simulação (provider mock)
  simulateLocation: (trackerId, areaId) =>
    request("/demo/location", {
      method: "POST",
      body: JSON.stringify({ tracker_id: trackerId, area_id: areaId }),
    }),
  simulateBattery: (trackerId, level) =>
    request("/demo/battery", { method: "POST", body: JSON.stringify({ tracker_id: trackerId, level }) }),
  simulateOffline: (trackerId) =>
    request("/demo/offline", { method: "POST", body: JSON.stringify({ tracker_id: trackerId }) }),
  simulateOnline: (trackerId) =>
    request("/demo/online", { method: "POST", body: JSON.stringify({ tracker_id: trackerId }) }),
  pollTracker: (trackerId) => request(`/trackers/${trackerId}/poll`, { method: "POST" }),
  checkInconsistency: (employeeId, expectedAreaId, ppeId) =>
    request("/inconsistency-check", {
      method: "POST",
      body: JSON.stringify({ employee_id: employeeId, expected_area_id: expectedAreaId, ppe_id: ppeId }),
    }),
};

// Serviço de alertas (epi_alerts) — separado do tracker: se estiver fora do ar,
// o restante da interface continua funcionando.
export const alertsApi = {
  async summary() {
    const resp = await fetch(ALERTS_URL + "/alerts/summary");
    if (!resp.ok) throw new Error(resp.statusText);
    return resp.json();
  },
  async list(includeResolved) {
    const resp = await fetch(ALERTS_URL + "/alerts" + (includeResolved ? "?include_resolved=true" : ""));
    if (!resp.ok) throw new Error(resp.statusText);
    return resp.json();
  },
  async acknowledge(id) {
    const resp = await fetch(ALERTS_URL + `/alerts/${id}/ack`, { method: "POST" });
    if (!resp.ok) throw new Error(resp.statusText);
    return resp.json();
  },
};

// Serviço Fusion (epi_fusion) — somente leitura aqui. Se estiver fora do ar, só a tela de câmeras
// mostra "indisponível".
async function fusionGet(path) {
  const resp = await fetch(FUSION_URL + path);
  if (!resp.ok) throw new Error(resp.statusText || "Fusion indisponível");
  return resp.json();
}

export const fusionApi = {
  camerasHealth: () => fusionGet("/fusion/cameras/health"),
  cameraObservations: (cameraId) => fusionGet(`/fusion/cameras/${encodeURIComponent(cameraId)}/observations`),
  anonymous: (limit = 50) => fusionGet(`/fusion/anonymous?limit=${limit}`),
  employeeState: (employeeId) => fusionGet(`/fusion/employees/${encodeURIComponent(employeeId)}`),
  allStates: () => fusionGet("/fusion/state"),
};
