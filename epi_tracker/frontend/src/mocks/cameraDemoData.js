// ATENCAO: este arquivo contem dados SIMULADOS -- separados de proposito
// dos dados reais do backend (secao 21 do pedido de melhoria).
//
// O QUE E REAL: o ID e a area de cada camera vem do campo `camera_id` que
// ja existe de verdade em SafetyCheckpoint (backend) -- nada inventado ali.
//
// O QUE E MOCK: o backend ainda NAO tem um endpoint de cameras (status
// online/offline, historico de eventos por camera). Ate essa integracao
// existir de verdade, este arquivo simula essas duas coisas -- e SO essas
// duas -- de forma deterministica (mesma camera sempre da o mesmo status
// simulado, para nao mudar aleatoriamente a cada re-render).
//
// Quando o backend tiver um endpoint real de cameras, e so trocar as duas
// funcoes abaixo por chamadas a app/services/api.js -- o resto do frontend
// (CameraDetail, filtros, etc.) ja consome atraves desta mesma interface.

function hashCode(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

const STATUSES = ["ONLINE", "ONLINE", "ONLINE", "ATTENTION", "OFFLINE"];

export function getMockCameraStatus(cameraId) {
  const idx = hashCode(cameraId) % STATUSES.length;
  return STATUSES[idx];
}

const MOCK_EVENT_TYPES = [
  "EMPLOYEE_ENTERED_AREA",
  "SAFETY_CHECK_COMPLETED",
  "TRACKER_DETECTED",
];

export function getMockCameraHistory(cameraId, employeeId) {
  const seed = hashCode(cameraId);
  const count = 3 + (seed % 4);
  const history = [];
  for (let i = 0; i < count; i++) {
    const daysAgo = i % 3;
    const date = new Date(2026, 7, 27 - daysAgo, 8 + i, (seed + i * 7) % 60);
    history.push({
      event: MOCK_EVENT_TYPES[(seed + i) % MOCK_EVENT_TYPES.length],
      timestamp: date.toISOString(),
      employee_id: employeeId || null,
    });
  }
  return history.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
}
