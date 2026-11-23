# Diagnóstico — Fase 1 (auditoria) do Mapa Operacional

Data: 23/11/2026. Escopo: leitura do repositório do grupo (`diegovitor90/visao-do-porto`, **somente leitura, nada foi alterado**) e dos serviços do EPI Vision (este repositório). Nenhum código foi modificado nesta fase.

## 1. Resumo
O front do grupo é bem organizado e acessível, mas **tudo o que ele mostra é simulado** e ele não consome nenhum serviço de monitoramento. Os serviços do EPI Vision já produzem a maior parte dos dados que o mapa precisa, mas **expõem só consulta periódica (REST)**, **não têm WebSocket**, **não guardam evidência (imagem)** e **perdem os dados ao reiniciar** (exceto o cadastro de câmeras).

## 2. Front-end do grupo (Visão do Porto)
- Stack: React 19, TypeScript, Vite, lucide-react, CSS próprio (~665 linhas), sem biblioteca de UI. 5 páginas: Visão geral, Analisar imagem, Alertas, Zonas, Histórico. Rotas por hash.
- **Dados:** alertas e zonas (Z01–Z04 do laboratório da UNDB, câmera LAB-01) são constantes em `model.ts`. A revisão do operador é gravada no `localStorage`.
- **Único uso real de backend:** upload de imagem para a FastAPI (via proxy do Vite), que devolve só `person`.
- Pontos fortes: acessibilidade (skip link, foco, `aria-live`), textos honestos sobre o que é simulado, teste em navegador.
- Lacunas: sem tempo real, sem mapa geográfico, sem estados de carregando/erro além do básico, sem login, histórico só no navegador.

## 3. Backend do grupo
- **Spring Boot 4.1.2:** trabalhadores (`nome`, `matricula`, `empresa`, `ativo`) e capacitações com validade. H2 em memória; sem autenticação; sem editar/desativar trabalhador; entidade JPA devolvida direto na API; sem `setor`/`cargo`.
- **FastAPI v0.3.0:** `POST /api/v1/vision/analyze` (imagem única, YOLO11n, só `person`). Sem vídeo, rastreamento, EPI, regras ou incidentes. Porta documentada: 8000 (**conflita com o `epi_ppe`**).

## 4. Serviços do EPI Vision — o que existe
| Serviço | Porta | O que oferece hoje |
|---|---|---|
| epi_ppe | 8000 | `/detect`, `/pipeline/process-frame`, `/events`, `/classes` |
| epi_identity | 8001 | cadastro de funcionários, reconhecimento (provedor MOCK), cadastro biométrico com consentimento, revisão |
| epi_fusion | 8002 | observações por câmera/funcionário, `/fusion/state`, `/fusion/cameras/health`, perfil de visibilidade por câmera |
| epi_rules | 8003 | regras versionadas, avaliação de conformidade, violações |
| epi_incident | 8004 | incidentes `OPEN`/`RESOLVED`, severidade, duração, `source_cameras`, métricas |
| epi_alerts | 8005 | alertas (`OPEN`/`ACKNOWLEDGED`/`RESOLVED`), resumo, `ack`, `sync` por consulta |
| epi_tracker | 8010 | câmeras (CRUD, persistidas em arquivo), setores/áreas, rastreadores, checkpoints, `/events`, funcionários, histórico |

## 5. O que o mapa e as páginas novas precisam × situação

| Necessidade | Situação |
|---|---|
| Câmeras com setor, tipo e saúde | **Pronto** (Tracker + Fusion `/cameras/health`). Posição é X/Y em %, **falta latitude/longitude** (decidido: acrescentar) |
| Setores | **Pronto**: 6 códigos idênticos em Python, Tracker e front (testado). **Falta geometria** (polígonos) |
| Pessoas monitoradas / câmeras online | **Pronto** (Fusion/Tracker) |
| Estados `COMPLIANT`/`NON_COMPLIANT`/`INDETERMINATE`/`NOT_VISIBLE` | **Pronto** (Rules/Fusion) |
| Incidentes com EPI faltante, severidade, duração, horário | **Pronto** (`ppe_type`, `severity`, `opened_at`, `duration_seconds`) |
| Incidente ligado a câmera | **Parcial**: só `source_cameras` (lista). O setor se obtém cruzando com o cadastro de câmeras do Tracker (junção a fazer) |
| Estados `IN_REVIEW`/`DISMISSED` e revisão humana | **Falta** no Incident (só `OPEN`/`RESOLVED`). O Alerts tem `ACKNOWLEDGED`, sem justificativa nem autor |
| Evidência (imagem do incidente) | **Falta**: nenhum serviço guarda imagem; o log até bloqueia campos de imagem de propósito. Exige decisão de privacidade/retenção |
| Tempo real (WebSocket) | **Falta**: os serviços só respondem consulta; o barramento de eventos é interno e em memória. Hoje a tela usa consulta a cada 2 s |
| Vídeo ao vivo | **Falta**: a demo lê a webcam local (OpenCV); não há gateway RTSP/WebRTC |
| Histórico e indicadores por período/turno | **Falta persistência**: Incident, Alerts, Rules e Tracker (menos câmeras) guardam em memória |
| Login e perfis (quem revisou) | **Falta** nos dois lados (o epi_identity tem RBAC por permissão, mas o Spring e as telas não) |
| Identificação do trabalhador | Funciona por matrícula; reconhecimento **simulado** (MOCK). Provedor InsightFace escrito, não testado |
| Relação área (Regras) × setor (mapa) | **Falta junção**: as Regras usam `area_id` + operação; o mapa usa setor. Precisa de um mapeamento explícito |

## 6. Dependências externas (decisão adiada, na lista)
Polígonos dos setores, coordenadas reais das câmeras, fonte de imagem de satélite licenciada, autorização para usar o Itaqui FlowMap só como referência visual (não extrair tiles), possível contato com a EMAP/orientador.

## 7. Decisões já tomadas (Sophia)
- Manter os 6 setores do código. Manter `ENTRADA`/`INTERNA`.
- Acrescentar latitude e longitude ao cadastro de câmeras.
- Adicionar WebSocket e vídeo ao backend.
- Manter a decisão de reconhecimento facial com consentimento (piloto; precisa de aval do orientador e termo).

## 8. Ordem sugerida das próximas fases
1. **Latitude/longitude** no cadastro de câmeras (extensão da v20, retrocompatível).
2. **Camada de dados do mapa** (um serviço agregador ou rotas no Tracker): junta câmeras + setor + saúde + incidentes abertos.
3. **Mapa operacional** com MapLibre usando base livre/identificada e os dados do passo 2; setores sem geometria mostram estado "limites não disponibilizados".
4. **Incidentes:** estados de revisão, justificativa, autor; persistência em banco.
5. **WebSocket** (`camera.status_changed`, `incident.opened/updated/resolved`) sobre o barramento interno existente.
6. **Vídeo** sob demanda (gateway + player).
7. Visão geral, Alertas, Zonas e Histórico evoluídos sobre esses dados.

## 9. Riscos
- Mudar o front do grupo exige alinhamento com o Diego (usar fork + pull request, sem alterar o repositório deles).
- Evidência em imagem e reconhecimento facial envolvem LGPD: retenção, acesso por perfil e consentimento.
- Sem persistência, indicadores por turno só valem para a sessão.
