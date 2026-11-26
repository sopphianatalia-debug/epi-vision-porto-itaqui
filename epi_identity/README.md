# EPI Vision — Módulo 1: Identificação Biométrica de Funcionários

Componente de **identificação biométrica** para um sistema de monitoramento de
segurança ocupacional (EPIs) em áreas portuárias. Este repositório implementa
**apenas o Módulo 1** (identificação do funcionário), já preparado para
integração futura com os módulos de detecção de pessoas, EPIs, regras, alertas
e dashboard.

> Princípio central: a IA **não é autoridade absoluta**. Toda identificação de
> baixa confiança ou ambígua vai para **revisão humana**, e dados biométricos
> são tratados como dado pessoal sensível (LGPD) desde o primeiro commit.

---

## Sumário
- [Arquitetura](#arquitetura)
- [Fluxo de dados](#fluxo-de-dados)
- [Como rodar](#como-rodar)
- [Estratégia de reconhecimento](#estratégia-de-reconhecimento)
- [Estratégia de tracking e reidentificação](#estratégia-de-tracking-e-reidentificação)
- [Segurança e privacidade (LGPD)](#segurança-e-privacidade-lgpd)
- [API](#api)
- [Contrato para o Módulo de EPI](#contrato-para-o-módulo-de-epi)
- [Testes](#testes)
- [Trocar o modelo de reconhecimento](#trocar-o-modelo-de-reconhecimento)
- [Riscos e limitações](#riscos-e-limitações)

---

## Arquitetura

Monólito modular com fronteiras hexagonais. O **domínio** (reconhecimento,
tracking, matching) não conhece banco nem HTTP; a **aplicação** orquestra
domínio + persistência + auditoria; a **API** só traduz HTTP.

```
app/
├── config.py            # Settings (thresholds, provider, chaves) via env
├── database.py          # SQLAlchemy 2.0 async + Base (UUID + timestamps)
├── enums.py             # Estados de domínio
├── models/              # Tabelas: employees, biometrics, events, tracks, reviews, audit
├── schemas/             # DTOs Pydantic (I/O da API)
├── security/
│   ├── crypto.py        # Criptografia de embeddings (Fernet; KMS em prod)
│   ├── auth.py          # JWT
│   └── rbac.py          # Papéis x permissões (segregação de funções)
├── recognition/
│   ├── base.py          # FaceRecognitionProvider (ABC) — troca de modelo
│   ├── quality.py       # QualityGate (FacialQualityScore)
│   ├── matching.py      # cosseno + threshold + ambiguidade
│   ├── service.py       # FaceRecognitionService (orquestra o pipeline)
│   ├── factory.py       # Seleciona o provider por config
│   └── providers/       # mock (dev/testes) | insightface (produção)
├── tracking/
│   ├── tracker.py       # IoUTracker → person_track_id temporário
│   └── identity_manager.py  # associa/expira identidade (reidentificação/TTL)
├── services/            # employee, enrollment, recognition, review, audit
├── api/                 # routers REST + deps (auth/RBAC)
└── observability/       # logs estruturados + métricas
```

## Fluxo de dados

```
Câmera → Frame → Detecção de pessoa → Tracking (person_track_id)
   → Melhor rosto → Gate de qualidade → (se ok) Embedding
   → Matching contra galeria autorizada → similarity/confidence/status
   → IdentificationResult → IdentityManager (TTL/reid)
   → Persistência (evento) + Auditoria → Contrato p/ Módulo de EPI
```

Se a qualidade for insuficiente, o pipeline retorna `UNAVAILABLE` — **nunca**
produz uma identificação de baixa qualidade.

## Como rodar

```bash
# 1. Dependências (dev)
pip install -e ".[dev]"

# 2. Variáveis de ambiente
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# cole o valor em EPI_BIOMETRIC_ENCRYPTION_KEY

# 3. Subir a API (cria as tabelas automaticamente fora de produção)
uvicorn app.main:app --reload
# Docs interativas: http://localhost:8000/docs

# Ou via Docker (PostgreSQL):
docker compose up --build
```

## Estratégia de reconhecimento

Reconhecimento **não roda em todo frame**. O fluxo eficiente é:
detectar pessoa → criar `person_track_id` temporário → rastrear →
executar reconhecimento facial **apenas quando há qualidade suficiente** →
associar a identidade ao track → manter durante o tracking → revalidar quando
necessário.

O matching usa **similaridade por cosseno** contra a galeria de embeddings
autorizados, com dois limiares configuráveis (similaridade e confiança) e uma
**margem de ambiguidade**. Estados possíveis:

| Status | Significado |
|---|---|
| `MATCHED` | Confiança ≥ threshold, sem ambiguidade |
| `LOW_CONFIDENCE` | Acima do limiar de similaridade, mas confiança baixa → revisão |
| `AMBIGUOUS` | 2º colocado dentro da margem → não escolhe, vai para revisão |
| `UNKNOWN` | Nenhum candidato acima do limiar |
| `UNAVAILABLE` | Qualidade insuficiente / sem rosto |

> A calibração similaridade→confiança é uma referência. Em produção, calibre
> estatisticamente (ex.: Platt scaling) sobre dados reais do site.

## Estratégia de tracking e reidentificação

`IoUTracker` gera IDs **temporários** (`CAM07_PERSON_00127`) — que **não são** a
identidade real. O `IdentityManager` guarda a associação
`person_track → employee_code` com **TTL**: se o rosto some por pouco tempo, a
identidade é mantida (reidentificação); passado o TTL, a identidade expira; sem
detecções por tempo suficiente, o track é encerrado.

## Segurança e privacidade (LGPD)

- Biometria é **dado pessoal sensível**: enrollment exige **consentimento
  explícito** do titular (HTTP 412 se ausente).
- Embeddings são **sempre criptografados** em repouso (Fernet/AES). A busca é
  feita em memória após descriptografia controlada e **auditada** — embeddings
  não trafegam nem ficam em claro em tabelas de acesso amplo.
- **RBAC** com segregação de funções:

| Papel | Lê func. | Escreve func. | Enroll | Roda match | Revisa | Auditoria |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| ADMIN | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| SECURITY_MANAGER | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| OPERATOR | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| AUDITOR | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| VIEWER | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

- **Auditoria append-only**: quem cadastrou/acessou/alterou/removeu, tentativas
  de identificação, ambiguidades e decisões de revisão.
- Imagens faciais brutas **não são persistidas** por padrão; retenção
  configurável.

## API

Base: `/api/v1`. Autenticação: `Authorization: Bearer <JWT>`.

```
POST   /employees
GET    /employees
GET    /employees/{id}
PUT    /employees/{id}
DELETE /employees/{id}                      (soft delete)

POST   /employees/{id}/biometric-enrollment
GET    /employees/{id}/biometric-status
DELETE /employees/{id}/biometric            (apaga o template, revoga o consentimento; 204, idempotente)

POST   /recognition/match
GET    /recognition/events
GET    /recognition/events/{id}
POST   /recognition/review
GET    /recognition/metrics
```

### Imagem real de rosto (provider `insightface`)

`frame` aceita `{"image_base64": "<JPEG|PNG>"}` (até 2 MB, 1920 px, 4 MP; mínimo 32 px). O tamanho, a assinatura e as
dimensões são validados antes de decodificar. A imagem fica só em memória: nada vai a disco nem a log; o que persiste
é o template numérico criptografado. Imagem inválida: 422 no cadastro, `UNAVAILABLE` na identificação. A galeria usa
apenas templates da versão do modelo atual (cadastro do mock não se mistura com o modelo real). Ligar com
`EPI_FACE_PROVIDER=insightface` (padrão: `mock`).

**Licença:** os modelos pré-treinados do InsightFace (ex.: buffalo_l) são para pesquisa / uso não comercial. Uso
comercial exige outro modelo ou licença própria. **Limiares:** os padrões (similaridade 0,55; confiança 0,80) foram
pensados para o mock. Em testes locais com o modelo real (3 pessoas, poucas amostras) a mesma pessoa deu 0,76–0,88 e
uma pessoa diferente 0,11; a confiança de 0,80 não é atingível. Valores a validar pelo grupo com mais voluntários
(proposta: confiança 0,40, via `EPI_CONFIDENCE_THRESHOLD`; o Fusion tem outro limiar equivalente, `FUS_IDENTITY_CONFIDENCE_THRESHOLD`, que também precisa ser calibrado). **Consentimento:** o termo do script de cadastro é de
teste e precisa de revisão jurídica/ética do grupo antes de qualquer uso real.

## Contrato para o Módulo de EPI

O resultado é entregue no formato que o Módulo de EPI consumirá (seção 17):

```json
{
  "camera_id": "CAM-07",
  "person_track_id": "CAM07_PERSON_00127",
  "employee_id": "FUNC-000234",
  "identity_status": "MATCHED",
  "confidence": 0.96,
  "timestamp": "2026-08-12T12:04:31"
}
```

## Testes

```bash
pytest -q
```

Cobrem: CRUD e geração de `employee_code` (nunca o nome como PK), enrollment com
consentimento e gate de qualidade, matching (match/unknown/low-confidence),
ambiguidade, pipeline `UNAVAILABLE`, tracking IoU, reidentificação por TTL,
revisão humana sobrepondo a IA e RBAC (403 para papéis sem permissão).

## Trocar o modelo de reconhecimento

Implemente `FaceRecognitionProvider` (métodos `detect_faces`,
`assess_quality`, `generate_embedding`), registre no `factory.py` e selecione via
`EPI_FACE_PROVIDER`. O provider `insightface` (ArcFace) já vem como referência
de produção, com import protegido:

```bash
pip install -e ".[recognition]"   # insightface + onnxruntime + opencv
export EPI_FACE_PROVIDER=insightface
```

Nenhuma outra parte do sistema muda — matching, regras e persistência são
agnósticos ao modelo.

## Riscos e limitações

- **Viés e erro do modelo**: por isso a revisão humana é obrigatória em casos
  duvidosos; a IA nunca é autoridade final.
- **Calibração de confiança**: a fórmula atual é heurística; recalibre com dados
  reais.
- **Geração de `employee_code`** por contagem tem condição de corrida — use uma
  *sequence* do banco em produção.
- **Escala do matching em memória**: adequado para milhares de funcionários por
  site; acima disso, considere um índice vetorial dedicado (ex.: pgvector/FAISS)
  em ambiente isolado e cifrado.
- **Base legal**: implante com Relatório de Impacto (RIPD/DPIA), política de
  retenção e canal de exclusão do titular.

---

**Escopo**: este módulo entrega identificação. Detecção de EPIs, verificação de
uso correto, regras, alertas e dashboard são módulos subsequentes e **não** estão
implementados aqui, conforme especificado.
