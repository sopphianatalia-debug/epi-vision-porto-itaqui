// Mapeamento de tipos de area -> zona visual da planta portuaria.
//
// IMPORTANTE: isso NÃO é dado inventado no frontend - é só a
// CLASSIFICAÇÃO VISUAL de um campo que já existe de verdade no backend
// (Area.type, livre, definido em POST /areas). O script de seed
// (scripts/seed_demo_data.py) cadastra áreas reais via API usando estes
// mesmos códigos de tipo; qualquer área com um tipo fora desta lista cai
// automaticamente na zona generica "Outras áreas", sem quebrar nada.
export const PORT_ZONE_TYPES = {
  CAIS: { label: "Cais / Berço de Atracação", icon: "ANC", zone: "water", order: 1 },
  NAVIOS: { label: "Área de Operação de Navios", icon: "NAV", zone: "operational", order: 1 },
  PATIO_ARMAZENAGEM: { label: "Pátio de Armazenagem", icon: "PAT", zone: "operational", order: 2 },
  PATIO_CAMINHOES: { label: "Pátio de Caminhões", icon: "CAM", zone: "logistics", order: 1 },
  CARGA_DESCARGA: { label: "Área de Carga e Descarga", icon: "C/D", zone: "operational", order: 3 },
  ARMAZEM: { label: "Armazém / Galpão Operacional", icon: "ARM", zone: "logistics", order: 2 },
  OFICINA: { label: "Oficina de Manutenção", icon: "OFI", zone: "support", order: 1 },
  ABASTECIMENTO: { label: "Área de Abastecimento", icon: "ABS", zone: "support", order: 2 },
  PORTARIA: { label: "Portaria / Controle de Acesso", icon: "PRT", zone: "access", order: 1 },
  ADMINISTRATIVA: { label: "Área Administrativa", icon: "ADM", zone: "support", order: 3 },
  OBRAS: { label: "Área de Obras / Manutenção", icon: "OBR", zone: "support", order: 4 },
  RESTRITA: { label: "Área de Acesso Restrito", icon: "RES", zone: "restricted", order: 1 },
};

export function zoneInfoForArea(area) {
  const known = PORT_ZONE_TYPES[(area.type || "").toUpperCase()];
  if (known) return known;
  return { label: area.type || "Área", icon: "ARE", zone: "other", order: 99 };
}

export const ZONE_GROUPS = [
  { key: "water", title: "Cais e área de água" },
  { key: "operational", title: "Área operacional" },
  { key: "logistics", title: "Pátios e armazéns" },
  { key: "access", title: "Acesso" },
  { key: "support", title: "Apoio e administracao" },
  { key: "restricted", title: "Acesso restrito" },
  { key: "other", title: "Outras áreas" },
];
