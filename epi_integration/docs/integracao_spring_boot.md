# Integração com o Spring Boot do grupo (Visão do Porto)

Divisão de responsabilidades (alinhada ao Plano do MVP do grupo):

| Lado | Responsabilidade |
| --- | --- |
| **Spring Boot (Java)** | Cadastro administrativo: trabalhadores, treinamentos, histórico, auditoria. **Fonte do cadastro.** |
| **Python (este projeto)** | Motor de visão e regras: detecção, EPIs, fusão de evidências, conformidade, incidentes, alertas, rastreador. |
| **Ponte (este módulo)** | API pequena entre os dois. Só leitura do lado Python. |

Princípio comum: **trajetória visual não é identidade**. Ter cadastro no Spring
não faz a câmera reconhecer ninguém; o rosto só entra com consentimento, num
passo separado.

## 1. Contrato usado hoje (Spring -> Python)

`GET {spring}/api/trabalhadores` ->
`[{ "id": "<uuid>", "nome": "...", "matricula": "...", "empresa": "...", "ativo": true,
   "setor": "GRANEIS_SOLIDOS", "cargo": "Operador de correia" }]`

`setor` e `cargo` são **opcionais** (o Spring pode começar sem eles). Valores válidos de `setor`
(os mesmos da tela Câmeras): `GRANEIS_SOLIDOS`, `GRANEIS_LIQUIDOS`, `CARGA_GERAL_CELULOSE`,
`PIER_BORDO`, `MANUTENCAO_ENGENHARIA`, `GUARDA_PORTUARIA`.

Mapeamento para o Identity:

| Spring | Identity | Observação |
| --- | --- | --- |
| `matricula` | `registration` | **Elo entre os dois.** Única nos dois lados. |
| `nome` | `name` | Atualizado se mudar no Spring. |
| `ativo` | `status` (`ACTIVE`/`INACTIVE`) | `ativo=false` vira INACTIVE. |
| `empresa` | — | Identity não tem o campo; fica só no Spring. |
| `setor` | `sector` | Um dos 6 códigos acima (aceita minúsculas/espaços). **Ausente** => na criação usa o padrão `PATIO_CARGA`; em trabalhador já existente **não altera**. **Código desconhecido** => reportado (`unknown_sector`) e ignorado: não adivinhamos. |
| `cargo` | `role_title` | Texto livre. Ausente => padrão `OPERADOR` na criação; não altera o existente. |
| `id` (UUID) | — | O Identity gera o próprio código (`FUNC-000001`). O elo é a matrícula, não o UUID. |

Regras da sincronização (`app/worker_sync.py`): idempotente; nunca apaga
(quem sumiu do Spring é só reportado); nunca mexe em biometria; se o Spring
cair, nada é alterado e o erro é reportado.

## 2. Como rodar

Com os serviços da demo no ar (`start_demo.py`) e o Spring em :8080:

```
python scripts/sync_trabalhadores.py --spring-url http://127.0.0.1:8080
```

Sai um resumo (criados, atualizados, sem mudança, só no Identity, erros).
Código de saída 0 = sucesso; 1 = Spring fora do ar ou houve erros.

## 3. Formato de detecções (FastAPI do grupo <-> nosso)

`app/vision_adapter.py` traduz:

```
Grupo: {"class_name":"person","confidence":0.91,"bbox":{"x1":..,"y1":..,"x2":..,"y2":..}}
Nosso: {"type":"person","confidence":0.91,"bbox":[x1,y1,x2,y2]}
```

Classes que não conhecemos são descartadas, não adivinhadas. Também há duas
colisões a resolver: ambos os FastAPI usam a porta 8000 (mude uma) e os
modelos são diferentes (o do grupo, `yolo11n.pt`, só acha pessoas; o nosso
`best.pt` acha capacete e colete).

## 4. Próximos passos sugeridos (a combinar com o grupo)

1. **Spring: adicionar os campos `setor` e `cargo`** ao trabalhador (o lado Python já aceita). **Decisão adiada:** onde as câmeras (e o setor de cada uma) ficam cadastradas oficialmente. Hoje o Tracker guarda (`/api/v1/cameras`, arquivo `~/.epi_vision/cameras.json`); se o Spring assumir, a tela passa a ler de lá (um sincronizador como o de trabalhadores) sem mudar de aparência.
2. Spring chamar o Python para consultar conformidade/incidentes de um
   trabalhador (hoje só o sentido Spring -> Python existe).
3. Contrato de eventos (`event_id`, `camera_id`, `zone_id`, `track_id`...) do
   Plano do MVP: mapear para os eventos que o nosso Incident já produz.
4. Autenticação entre os serviços (hoje o Identity usa JWT; o Spring ainda
   não tem segurança configurada).

## 5. O que foi e o que NÃO foi testado

- Testado: 11 testes novos com o **Identity real** e um Spring **simulado**
  que segue o contrato acima (suíte de integração: 83 passando).
- NÃO testado: contra o Spring Boot de verdade (o ambiente onde isto foi
  escrito não consegue baixar as dependências Maven). O primeiro teste real
  é rodar o script acima na máquina da Sophia com o Spring do Diego no ar.
