# Demo com webcam + YOLO treinado

Modelo: `best.pt` (YOLOv8n, dataset Construction-Site-Safety v27; mAP50 0,713;
capacete 0,80 · colete 0,79). Detecta capacete e colete. NÃO detecta botas nem
luvas — por isso a demo usa a regra geral do pátio (capacete + colete) e marca
pés/mãos como "não observáveis" (nunca como "ausentes").

## 1. Ambiente (uma vez)
Use o venv do YOLO (Python 3.12, já tem torch/ultralytics) e acrescente o resto:

```
cd ~/Downloads/projetoEPI_YOLO/epi_vision_projeto_completo
source .venv/bin/activate
pip install fastapi "uvicorn[standard]" pydantic pydantic-settings httpx pyjwt \
            sqlalchemy aiosqlite greenlet cryptography numpy
pip install opencv-python        # versão com janela (se já tiver a headless, desinstale-a antes)
```

## 2. Terminal 1 — subir tudo (com o venv acima ativo)
```
cd ~/Downloads/v7/epi_vision_projeto_completo/epi_integration
python scripts/start_demo.py --model ~/Downloads/projetoEPI_YOLO/epi_vision_projeto_completo/runs/detect/train/weights/best.pt
```
Espere "Tudo pronto". Ele imprime o comando da câmera. Ctrl+C encerra TODOS os serviços.
Sem YOLO (só testar o fluxo): `--mock`.

## 3. Terminal 2 — câmera (mesmo venv)
Copie o comando que o Terminal 1 imprimiu. É assim:
```
cd ~/Downloads/v7/epi_vision_projeto_completo/epi_integration
EPI_PIPELINE_DEMO_EMPLOYEE_SEED=FUNC-000001 EPI_PIPELINE_OPERATION=GERAL \
EPI_PIPELINE_BLIND_REGIONS=feet,hands \
EPI_PIPELINE_TRACKER_URL=http://127.0.0.1:8010/api/v1 EPI_PIPELINE_TRACKER_AREA_ID=PATIO-02 \
python scripts/run_camera_demo.py --source 0 --camera-id CAM-ENTRY-02
```
Na primeira vez o macOS pede permissão de câmera para o Terminal: aceite e rode de novo.

## 4. Terminal 3 — interface
```
cd ~/Downloads/v7/epi_vision_projeto_completo/epi_tracker/frontend
python3 -m http.server 8020
```
Abra http://127.0.0.1:8020/index.html

## Roteiro da apresentação
1. Com capacete e colete visíveis: COMPLIANT, sem incidente.
2. Tire o capacete (ou use `EPI_PIPELINE_DEMO_SCENARIO=missing_helmet`): NON_COMPLIANT + incidente. Ponha de volta: o incidente se resolve.
3. Na interface, em Simulação, mova o rastreador do capacete (TRACKER-DEMO-01) para ARMAZÉM:
   aparece em Alertas "possível inconsistência" (câmera vê o capacete no Pátio 02, rastreador diz Armazém).
   Não é violação — é uma divergência a investigar.

## Limites a dizer com honestidade
- Identidade é MOCK (funcionário de demonstração), não reconhecimento facial real.
- Modelo pequeno treinado em CPU: pode errar com pouca luz, ângulo ou oclusão.
- Botas e luvas não são avaliadas por este modelo.
- Classes "NO-Hardhat"/"NO-Safety Vest" do dataset são ignoradas: a ausência é decidida por não detectar.

## Persistência dos incidentes (v11)
Para não abrir/fechar incidente a cada piscada da detecção, o lançador cria uma
nova versão das regras do pátio com tempos de confirmação:
- `--violation-seconds 3` (padrão): o EPI precisa faltar por 3 s CONTÍNUOS para abrir o incidente.
- `--recovery-seconds 3` (padrão): o EPI precisa estar visível por 3 s CONTÍNUOS para resolver.
- `--person-threshold 0.65` (padrão): confiança mínima para aceitar uma pessoa.
Use `--violation-seconds 0 --recovery-seconds 0` para o comportamento antigo (instantâneo).
Na tela da câmera, "NON_COMPLIANT" aparece na hora, mas o incidente só nasce após os 3 s.

## Uma identidade por quadro na demonstração (v12)
Com `EPI_PIPELINE_DEMO_EMPLOYEE_SEED`, o funcionário de demonstração vale para
UMA pessoa por quadro: a de maior confiança (ela só cede o lugar se outra tiver
confiança 0,15 maior). As demais ficam "não identificadas" e não geram
incidente — como numa câmera real, onde só quem é reconhecido é avaliado.
Antes, o seu corpo aparecendo atrás do celular recebia o mesmo funcionário e
mantinha os alertas abertos.

## Cabeça ou pés cortados pelo quadro (v13)
Se a caixa da pessoa encosta na borda de CIMA da imagem, a cabeça pode estar
fora do quadro: capacete/proteção auricular que não aparecem viram "não
observável" (indeterminado), nunca "ausente". Borda de BAIXO: idem para botas.
Se o EPI for detectado mesmo assim, continua DETECTED. Quando a cabeça está
inteira no quadro, a ausência do capacete continua gerando MISSING.

## v14 — confiança mínima ajustável (`--min-confidence`)

As regras de exemplo exigem confiança ≥ 0,85 para aceitar um EPI como presente. Para o yolov8n
treinado isso é alto: capacete real com 0,70 virava `INDETERMINATE`. O `start_demo.py` agora cria
a nova versão das regras com `--min-confidence 0.60` (padrão da demo). Abaixo desse valor continua
indeterminado (nunca violação nem conformidade); ausência continua `MISSING`. Para voltar ao rígido:
`--min-confidence 0.85`.

## v15 — tela "Câmeras" (mapa esquemático por setor do Itaqui)

Na interface (http://127.0.0.1:8020/index.html), menu **Monitoramento → Câmeras** (`#cameras`).
- Desenho ESQUEMÁTICO dos 6 setores (não é planta nem escala). Cada câmera é um ponto colorido pela saúde
  operacional do Fusion (Boa ≥ 75, Atenção ≥ 50, Baixa < 50, cinza = sem dados). Quadrado "E" = câmera de
  entrada do setor (checkpoint); círculo "I" = câmera interna.
- Clique na câmera: saúde, observações, taxa de identificação, % não observável e as pessoas vistas, com o
  estado de cada EPI (só o que a câmera enxergou; a conformidade continua sendo das Regras). Pessoa sem
  identidade aparece como "Não identificado"; a tela mostra o código do funcionário, sem imagens nem biometria.
- Cadastro de câmeras e setores: `epi_tracker/frontend/src/config/itaqui.js`. Câmera que manda dados ao
  Fusion mas não está no cadastro aparece em "Câmeras sem setor definido" (nada é escondido). Depois de
  editar o arquivo, gere o bundle de novo (`npm run build` em `epi_tracker/frontend`) ou peça o pacote novo.
- A câmera da demo (`CAM-ENTRY-02`) está cadastrada, só como exemplo, em "Carga Geral e Celulose".
- O Fusion ganhou CORS (a interface, em outra porta, lê as câmeras direto dele; somente leitura). Em
  produção, restrinja `allow_origins` ao endereço real da interface.
- Se o Fusion estiver fora do ar, a tela avisa "Fusion indisponível" (e isso não significa que não há pessoas).

## v17 — Tela Câmeras: clique no setor
- Clique em um setor (no mapa ou na lista) para ver as câmeras dele: **entrada (checkpoint)** e **internas (movimentação)**, cada uma com saúde e nº de pessoas.
- Clique numa câmera (no mapa ou na lista) para ver o detalhe: saúde, identificação, "não observável" e EPIs de cada pessoa vista. Botões "←" voltam um nível.
- "Vistos neste setor nos últimos 60s" junta todas as câmeras do setor. É o que a câmera enxergou, **não** registro oficial de presença e **não** decide conformidade.
- As 5 câmeras `CAM-EX-*` são **exemplos** (selo "exemplo") para mostrar entrada x interna. Para uma ganhar dados na demo, rode a câmera com `--camera-id CAM-EX-GS-ENT` (ou `CAM-EX-GS-INT1` etc.).
- Cadastrar as câmeras reais: edite `epi_tracker/frontend/src/config/itaqui.js` (apague as de exemplo).

## v18 — Setor no cadastro + tela Câmeras mais ágil
- A tela **Câmeras** atualiza a cada 2 s (antes 4 s). O Fusion em si atualiza na hora a cada observação; o atraso visto antes era do polling da página e da amostragem da câmera (1 quadro a cada 5).
- A ponte Spring→Identity aceita `setor` (um dos 6 códigos) e `cargo` opcionais. Ver `docs/integracao_spring_boot.md`. Setor desconhecido é reportado e ignorado.

## v19 — Demo de luvas e botas (usar DEPOIS do retreino 2, com `best_cores_gb.pt`)
A regra `RULE-PATIO-CARGA-001` (operação `MOVIMENTACAO_CARGA`) exige capacete, colete, **luvas e botas**. O Terminal 1 já aplica o tempo de persistência (3 s) e a confiança mínima nela.
No Terminal 1 troque o modelo: `--model ~/Downloads/modelo_cores/best_cores_gb.pt`.

**Testar LUVAS** (webcam vê as mãos; os pés ficam "não observáveis"): no Terminal 3 use
`EPI_PIPELINE_OPERATION=MOVIMENTACAO_CARGA` e `EPI_PIPELINE_BLIND_REGIONS=feet`.
- Mão com luva → `Luvas: Detectado`. Mão nua à mostra → `Luvas: Ausente`. Mão fora de quadro → `Luvas: Sem observação` (nunca violação).

**Testar BOTAS** (precisa enquadrar os pés; afaste-se da câmera): use `BLIND_REGIONS=hands`.
- Pés cortados pela borda do quadro → `Botas: Sem observação` automaticamente.
- Tênis comum NÃO deve virar `Botas: Detectado` com confiança alta; se virar, anote e me mande.

Resultado esperado: sem luvas ou botas visíveis o status é NON_COMPLIANT só depois de 3 s contínuos; EPI não observável deixa o status INDETERMINATE, sem incidente.
Testes automatizados: luva ausente com mão visível = MISSING; mão fora de quadro = nunca violação.

## v20 — Cadastro de câmeras pela tela (sem mexer no código)
- Na tela **Câmeras**, o painel **Gerenciar câmeras** (no fim da página) cadastra, edita e exclui câmeras: ID, nome, setor, tipo (entrada/interna) e posição no mapa (X e Y em %).
- O **ID** precisa ser igual ao `--camera-id` que a câmera envia. Câmera que envia dados sem cadastro aparece com o botão "cadastrar <ID>".
- O cadastro fica gravado em `~/.epi_vision/cameras.json` e **sobrevive a reiniciar e a trocar de versão** (o resto do sistema continua em memória). Na primeira vez o arquivo nasce com a câmera da demo e as 5 de exemplo (selo "exemplo"); depois disso ele só muda pelo que você fizer na tela.
- Para voltar às câmeras de exemplo: feche o Terminal 1, apague o arquivo (`rm ~/.epi_vision/cameras.json`) e suba de novo. Outro arquivo: `--cameras-file /caminho/cameras.json`.
- API (Tracker :8010): `GET/POST /api/v1/cameras`, `GET/PUT/DELETE /api/v1/cameras/{id}`. Setor desconhecido ou posição fora de 0-100 é recusado (422).
- **Decisão adiada:** se o cadastro oficial das câmeras ficará no Spring (Diego) ou no Tracker. Por enquanto o Tracker guarda; migrar depois não muda a tela, só a origem dos dados.
