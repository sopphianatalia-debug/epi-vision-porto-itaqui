// Traducoes e rotulos amigaveis - secao 3 do pedido de refinamento:
// nenhum valor tecnico em ingles aparece como texto PRINCIPAL da interface.
// O codigo tecnico continua disponivel como informacao secundaria.

export const STATUS_LABELS = {
  ACTIVE: "Ativo",
  OFFLINE: "Offline",
  LOW_BATTERY: "Bateria baixa",
  UNKNOWN: "Desconhecido",
  ONLINE: "Online",
  CURRENT: "Atual",
  LAST_KNOWN: "Última localização conhecida",
  EXPIRED: "Expirado",
  COMPLIANT: "Conforme",
  NON_COMPLIANT: "Não conforme",
  INDETERMINATE: "Indeterminado",
  NOT_EVALUATED: "Não avaliado",
  CONFLICTING: "Conflitante",
  DETECTED: "Detectado",
  NOT_DETECTED: "Não detectado",
  ASSIGNED: "Atribuído",
  REGISTERED: "Registrado",
  RETIRED: "Desativado",
  ATTENTION: "Atenção",
  CRITICAL: "Crítico",
  WARNING: "Atenção",
  INFO: "Informativo",
  OPEN: "Novo",
  ACKNOWLEDGED: "Visto",
  RESOLVED: "Resolvido",
};

export const PPE_TYPE_LABELS = {
  helmet: "Capacete",
  vest: "Colete",
  boots: "Botas",
  gloves: "Luvas",
  goggles: "Óculos de proteção",
  hearing_protection: "Proteção auricular",
  other: "Outro",
};

export const TECHNOLOGY_LABELS = {
  MOCK: "Simulado",
  BLE: "Bluetooth (BLE)",
  RFID: "RFID",
  UWB: "Ultra-wideband (UWB)",
  OTHER: "Outra tecnologia",
};

export const EVENT_LABELS = {
  EMPLOYEE_ENTERED_AREA: "Funcionário entrou na área",
  EMPLOYEE_EXITED_AREA: "Funcionário saiu da área",
  SAFETY_CHECK_STARTED: "Verificação de segurança iniciada",
  SAFETY_CHECK_COMPLETED: "Verificação de segurança concluída",
  TRACKER_DETECTED: "Tracker detectado",
  TRACKER_LOCATION_UPDATED: "Localização recebida",
  TRACKER_ENTERED_AREA: "Tracker entrou na área",
  TRACKER_EXITED_AREA: "Tracker saiu da área",
  TRACKER_OFFLINE: "Tracker ficou offline",
  TRACKER_LOW_BATTERY: "Bateria baixa detectada",
  TRACKER_LOCATION_EXPIRED: "Localização expirada",
  POSSIBLE_PPE_LOCATION_INCONSISTENCY: "Possível inconsistência de localização",
};

export const EVENT_ICONS = {
  EMPLOYEE_ENTERED_AREA: "IN",
  EMPLOYEE_EXITED_AREA: "OUT",
  SAFETY_CHECK_STARTED: "CHK",
  SAFETY_CHECK_COMPLETED: "OK",
  TRACKER_DETECTED: "DET",
  TRACKER_LOCATION_UPDATED: "LOC",
  TRACKER_ENTERED_AREA: "IN",
  TRACKER_EXITED_AREA: "OUT",
  TRACKER_OFFLINE: "!",
  TRACKER_LOW_BATTERY: "BAT",
  TRACKER_LOCATION_EXPIRED: "!",
  POSSIBLE_PPE_LOCATION_INCONSISTENCY: "!",
};

// Categorias para o filtro da tela de Historico (secao 12).
export const EVENT_CATEGORIES = {
  trackers: ["TRACKER_DETECTED", "TRACKER_OFFLINE", "TRACKER_LOW_BATTERY"],
  localizacao: ["TRACKER_LOCATION_UPDATED", "TRACKER_ENTERED_AREA", "TRACKER_EXITED_AREA", "TRACKER_LOCATION_EXPIRED"],
  epis: ["POSSIBLE_PPE_LOCATION_INCONSISTENCY"],
  funcionarios: ["EMPLOYEE_ENTERED_AREA", "EMPLOYEE_EXITED_AREA", "SAFETY_CHECK_STARTED", "SAFETY_CHECK_COMPLETED"],
  alertas: ["TRACKER_OFFLINE", "TRACKER_LOW_BATTERY", "TRACKER_LOCATION_EXPIRED", "POSSIBLE_PPE_LOCATION_INCONSISTENCY"],
};

export function translateStatus(status) {
  return STATUS_LABELS[status] || status || "Não informado";
}

export function translatePPEType(type) {
  if (!type) return "Não informado";
  return PPE_TYPE_LABELS[type.toLowerCase()] || type;
}

export function translateTechnology(tech) {
  return TECHNOLOGY_LABELS[tech] || tech || "Não informado";
}

export function translateEvent(eventName) {
  return EVENT_LABELS[eventName] || eventName;
}

export function eventIcon(eventName) {
  return EVENT_ICONS[eventName] || "-";
}

// "Não informado" em vez de traco/vazio - secao 10 e 19: nunca deixar a
// ausencia de dado parecer um erro visual silencioso.
export function orNotInformed(value, formatter) {
  if (value === null || value === undefined || value === "") return "Não informado";
  return formatter ? formatter(value) : value;
}
