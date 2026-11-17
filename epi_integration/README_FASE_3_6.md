# Fase 3.6 — Identity-to-Fusion Integration

## Objetivo

Substituir o `employee_id` artificial da Fase 3.5 pela saída real de
`POST /recognition/match` do `epi_identity` (provider **mock**, sem
biometria real), provando que os quatro módulos conversam:

```
epi_identity -> epi_fusion -> epi_rules -> epi_incident
```

## O que mudou desde a Fase 3.5

**Nenhum arquivo dos módulos existentes foi alterado** (auditoria: 0 arquivos
`.py` modificados em `epi_ppe`, `epi_identity`, `epi_fusion`, `epi_rules`,
`epi_incident`, `epi_compliance` desde a Fase 3.5). Diferente da Fase 3.5
(que precisou de 1 endpoint novo no `epi_incident`), aqui o `epi_identity` já
tinha tudo que a integração precisava — só foi consumido via HTTP.

Tudo que é novo mora em `epi_integration/`:

- `app/identity_client.py` — cliente HTTP do Identity (o único dos 4
  serviços que exige JWT + RBAC)
- `app/bridge.py` — nova função `identity_result_to_fusion_identity` (a
  ponte Identity → Fusion) e `identify_and_ingest` (atalho Observation →
  Identity → Fusion completo)
- `app/runner.py` — agora também sobe `epi_identity` (e uma segunda
  instância dele com threshold permissivo — ver `docs/contracts.md`)
- `tests/integration/test_identity_scenarios.py` — MATCHED, UNMATCHED,
  LOW_CONFIDENCE, AMBIGUOUS, propagação de `employee_id`, pipeline completo,
  NOT_VISIBLE, multi-câmera, identidades diferentes, idempotência
- `tests/integration/test_identity_errors.py` — auth, RBAC, payload
  inválido, qualidade insuficiente, observabilidade

## Fluxo novo

```
Observation (artificial) -> POST /recognition/match (epi_identity)
    -> IdentityResult -> [Identity-to-Fusion Adapter] -> employee_id + identity_status
    -> POST /fusion/observations (epi_fusion) -> ... (igual à Fase 3.5)
```

## Regra fundamental preservada

`employee_id` só é considerado confiável quando o Identity retorna
`MATCHED`. Em qualquer outro estado (`UNKNOWN`, `LOW_CONFIDENCE`,
`AMBIGUOUS`, `UNAVAILABLE`), a observação segue para o Fusion **sem**
`employee_id` — o Fusion já trata isso como anônimo por conta própria
(`JOINABLE_IDENTITY = {MATCHED}`, regra que já existia desde a Fase 3.1 e
não foi tocada).

## Como rodar

Precisa de mais uma dependência (`pyjwt`, para mintar tokens compatíveis com
o `epi_identity`) além do que a Fase 3.5 já instalava:

```bash
# a partir da raiz do projeto
pip install -e epi_fusion -e epi_rules -e epi_incident -e epi_identity
pip install -e "epi_integration[dev]"

# testes unitários de cada módulo (nenhum foi alterado, devem continuar passando)
pytest epi_fusion/tests epi_rules/tests epi_incident/tests epi_identity/tests

# testes de integração — Fase 3.5 (Fusion/Rules/Incident) + Fase 3.6 (Identity)
pytest epi_integration/tests/integration -v
```

O `epi_identity` precisa de `greenlet` (dependência transitiva do
SQLAlchemy async) — se faltar, `pip install greenlet` resolve (já visto na
validação manual do módulo antes desta fase).

Cada execução da suíte de integração cria bancos SQLite temporários próprios
para as instâncias de `epi_identity` (via `tempfile`), então rodar a suíte
várias vezes não acumula funcionários entre execuções.

## Decisões arquiteturais

1. **Nada foi reescrito no `epi_identity`.** O enum `RecognitionStatus` já
   cobria exatamente os 4 estados que o pedido da Fase 3.6 queria (mais um
   quinto, `UNAVAILABLE`, que o pedido não previu — tratado na ponte).
2. **Tradução de enum na ponte, não em nenhum dos serviços** — ver
   `docs/contracts.md`, seção 9.2. `UNAVAILABLE -> NOT_IDENTIFIED` é a única
   tradução não-trivial.
3. **Duas instâncias de `epi_identity` nos testes** (padrão e "permissiva")
   — necessário porque o provider mock só produz similaridade ~1.0 (mesma
   seed) ou ~0 (seed diferente), sem meio-termo controlável; ver
   `docs/contracts.md`, seção 9.3, para o raciocínio completo. Isso é uma
   decisão da camada de TESTE, não do sistema — em produção, com biometria
   real, similaridades intermediárias surgem naturalmente.
4. **AMBIGUOUS via colisão de seed** (dois funcionários cadastrados com a
   mesma seed) — funciona com os thresholds padrão, sem precisar de
   configuração especial.

## Testes — cobertura dos cenários do pedido original

| # | Cenário | Teste |
|---|---|---|
| 10 | MATCHED propaga employee_id | `test_matched_propagates_employee_id_to_fusion` |
| 11 | UNMATCHED não inventa employee_id | `test_unmatched_does_not_invent_employee_id` |
| 12 | LOW_CONFIDENCE não atribui automaticamente | `test_low_confidence_does_not_auto_assign` |
| 13 | AMBIGUOUS não escolhe arbitrariamente | `test_ambiguous_does_not_choose_arbitrarily` |
| 14 | Propagação employee_id ponta a ponta | dentro de `test_full_pipeline_matched_and_missing_ppe_*` |
| 15 | Pipeline completo, EPI correto | `test_full_pipeline_matched_and_compliant_no_incident` |
| 16 | Pipeline completo, EPI ausente | `test_full_pipeline_matched_and_missing_ppe_creates_incident_with_correct_employee` |
| 17 | Não identificado + EPI ausente -> nenhum incidente | `test_unmatched_with_missing_ppe_creates_no_incident` |
| 18 | NOT_VISIBLE via pipeline de identidade | `test_not_visible_via_identity_pipeline_is_indeterminate` |
| 19 | Multi-câmera, mesmo employee_id | `test_multi_camera_same_employee_consolidates_one_state` |
| 20 | Identidades diferentes não unificadas | `test_different_employees_between_cameras_not_merged` |
| 22 | Idempotência | `test_repeated_match_does_not_duplicate_incident` |
| 23 | Métricas | `test_identity_metrics_increment_on_match`, `test_fusion_metrics_unaffected_by_identity_errors` |
| 26 | Erros (payload, auth, RBAC, qualidade, 404, propagação de erro) | `test_identity_errors.py` (7 testes) |

**Cenário 21 (Event Bus) não tem teste HTTP dedicado nesta fase** — mesma
limitação já documentada na Fase 3.5: nenhum dos serviços expõe histórico
bruto de eventos via HTTP, só métricas agregadas (que são testadas).

## Status de execução

Este ambiente de geração de código não tem acesso à internet — não foi
possível instalar `fastapi`/`sqlalchemy`/`pyjwt`/etc. aqui para rodar a
suíte de fato. Toda a sintaxe foi verificada (`py_compile`, sem erros) e o
contrato de cada endpoint foi conferido linha a linha no código-fonte do
`epi_identity` (não presumido a partir do pedido). Os números reais de
passou/falhou vêm da sua execução local — mesmo fluxo que já usamos nas
fases anteriores.

## Limitações

- Reconhecimento facial continua sendo o provider mock — nenhuma biometria
  real, nenhum InsightFace, conforme pedido explícito desta fase.
- O adaptador Identity→Fusion (`bridge.py`) é uma função pura chamada pelo
  código de teste, não um serviço orquestrador rodando continuamente — mesma
  limitação já registrada na Fase 3.5 para o pipeline inteiro.
- `UNAVAILABLE` (qualidade insuficiente) é tratado como `NOT_IDENTIFIED` no
  Fusion; se no futuro for necessário distinguir "câmera não conseguiu nem
  tentar identificar" de "tentou e não achou", será preciso estender o
  `IdentityStatus` do próprio Fusion (fora do escopo desta fase, por ser uma
  mudança em módulo já estabilizado).

## Próximos passos

Alertas/Notificações e Dashboard Operacional, como já estava planejado —
agora com o pipeline completo (Identity → Fusion → Rules → Incident)
validado ponta a ponta, incluindo identificação real (ainda que mock).
