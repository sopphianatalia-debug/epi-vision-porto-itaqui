// Setores do Porto do Itaqui (códigos, nomes e desenho esquemático).
//
// ATENÇÃO: o desenho é ESQUEMÁTICO (não é planta nem escala). As posições (x, y, w, h, em %)
// só organizam a tela. Os berços e as descrições vieram de pesquisa (manual do Porto do Itaqui
// e Transpetro) e os EPIs por setor AINDA NÃO foram validados com especialista operacional.
//
// As CÂMERAS não ficam mais aqui: são cadastradas na própria tela (Câmeras > Gerenciar câmeras)
// e guardadas no Tracker (API /api/v1/cameras). Câmeras que enviam dados ao Fusion mas não estão
// cadastradas aparecem em "Câmeras sem setor definido" (nada é escondido).
// Os 6 códigos abaixo são os mesmos do Tracker e da ponte com o Spring (testes impedem divergência).

export const SECTORS = [
  { code: "GRANEIS_SOLIDOS", name: "Granéis Sólidos",
    description: "Vegetais e minerais: soja, milho, fertilizantes, manganês, clínquer", berths: ["99", "100", "101", "102", "105"],
    box: { x: 2, y: 4, w: 31, h: 40 } },
  { code: "GRANEIS_LIQUIDOS", name: "Granéis Líquidos",
    description: "Combustíveis e químicos: diesel, gasolina, GLP, querosene de aviação; áreas Transpetro/Taiselis", berths: ["102", "104", "106", "108"],
    box: { x: 35, y: 4, w: 31, h: 40 } },
  { code: "CARGA_GERAL_CELULOSE", name: "Carga Geral e Celulose",
    description: "Celulose (berço 99) e cargas diversas e pesadas", berths: ["99"],
    box: { x: 68, y: 4, w: 30, h: 40 } },
  { code: "PIER_BORDO", name: "Operações de Píer e Bordo",
    description: "Estiva e operadores portuários: navios, amarração, guindastes, empilhadeiras, caminhões", berths: [],
    box: { x: 2, y: 52, w: 31, h: 42 } },
  { code: "MANUTENCAO_ENGENHARIA", name: "Manutenção e Engenharia",
    description: "Equipamentos industriais, trilhos, redes elétricas, estruturas civis", berths: [],
    box: { x: 35, y: 52, w: 31, h: 42 } },
  { code: "GUARDA_PORTUARIA", name: "Guarda Portuária e Fiscalização Operacional",
    description: "Patrulha e controle de acesso", berths: [],
    box: { x: 68, y: 52, w: 30, h: 42 } },
];

// kind: "ENTRADA" (checkpoint na entrada do setor) ou "INTERNA" (acompanha a movimentação dentro do setor)
// pos: posição da câmera DENTRO do retângulo do setor, em % (0–100).
export function sectorByCode(code) {
  return SECTORS.find((s) => s.code === code) || null;
}

// Cor pela saúde operacional (health_score do Fusion: escala 0–100). Sem dado = cinza (NÃO significa "problema").
export function healthLevel(h) {
  if (!h || h.observations === 0 || h.health_score == null) return { key: "nodata", label: "Sem dados", color: "#8b949e" };
  if (h.health_score >= 75) return { key: "ok", label: "Boa", color: "#1a7f37" };
  if (h.health_score >= 50) return { key: "attention", label: "Atenção", color: "#bf8700" };
  return { key: "bad", label: "Baixa", color: "#cf222e" };
}
