# FASE 3.1 — Arquitetura e decisões

## Posição no sistema

```
Câmera → Detecção → Tracking → PPE → Associação → Identidade(Módulo 1)
        → Observation → CameraObservationOrchestrator → FusionService
        → EmployeeSafetyState → (Módulo 3 / Regras / Incidentes)
```

O FusionService fica **entre a identificação e a consolidação**. Ele **não decide
conformidade** — apenas consolida evidência ("capacete DETECTADO"), deixando a
decisão "está correto segundo a política" para o Módulo 3 + regras.

## Decisões arquiteturais

1. **Consistência com os módulos 1–3**: FastAPI síncrono, estado em memória com
   repositórios por trás de interfaces, providers/abstrações plugáveis. Nada de
   arquitetura paralela. Persistência em banco pode ser adicionada trocando os
   repositórios in-memory por implementações reais, sem tocar no FusionService.

2. **employee_id como única chave de junção**; `person_track_id` é sempre local
   por câmera. O agrupamento entre câmeras acontece **só** por `employee_id`.

3. **Conservadorismo (segurança)**: só `MATCHED` + confiança suficiente +
   funcionário válido/ativo vira chave. Qualquer outra coisa → observação
   ANÔNIMA, nunca atribuída por proximidade. Preferimos "não identificado" a
   "identificado errado".

4. **NOT_VISIBLE ≠ MISSING ≠ NOT_OBSERVED**: o silêncio de uma câmera é
   reinterpretado pelo **perfil de visibilidade**. Câmera que não vê os pés →
   `NOT_VISIBLE`; `MISSING` só vem de câmera que **vê** a região e reporta
   ausência.

5. **Consolidação por evidência, não média**: confiança combinada por
   *noisy-OR* ponderado (câmeras concordantes elevam a confiança); presença
   (quem vê) prevalece sobre ausência de quem não vê.

6. **Conflitos explícitos**: PROPER×IMPROPER ou presença×MISSING são resolvidos
   por visibilidade → confiança → recência; se a diferença for menor que a
   margem configurável, vira `UNKNOWN` e o conflito é **registrado**.

7. **Tempo**: janela de fusão (observações antigas não influenciam o presente),
   *last known state* (mantém a identidade por um TTL quando o rosto some, se o
   track é o mesmo) e expiração do estado consolidado.

8. **IdentityResolver como ponto de extensão da FASE 3.2**: hoje só
   `EmployeeIdIdentityResolver`. Amanhã, `SpatialIdentityResolver` /
   `ReIdentificationResolver` produzirão um `IdentityResolution` e entrarão no
   mesmo fluxo, sem reescrever o FusionService.

## O que NÃO foi implementado (pertence à FASE 3.2)

Re-ID, calibração espacial, homografia, matching visual entre câmeras,
identificação por aparência/roupa e qualquer inferência probabilística de
identidade. Observações sem `employee_id` confiável ficam **anônimas e
separadas**, prontas para a 3.2 tentar resolver depois.

## Entidades (materializáveis em banco)

`camera_observations`, `employee_safety_states`, `fusion_events`,
`fusion_conflicts`, `anonymous_observations`, `camera_visibility_profiles`.
Nesta fase são repositórios em memória; as observações originais são mantidas
conforme a janela e o estado consolidado é cacheado.
