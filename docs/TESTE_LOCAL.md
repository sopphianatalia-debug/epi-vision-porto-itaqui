# Teste local com webcam, vídeo ou RTSP (macOS/Linux)

Tudo roda no seu computador. Segredos e dados ficam em `.local/` (fora do Git).

## 1. Uma vez só
```
git clone https://github.com/sopphianatalia-debug/epi-vision-porto-itaqui.git
cd epi-vision-porto-itaqui
python3 -m venv .venv && source .venv/bin/activate
pip install -e epi_ppe -e epi_identity -e epi_fusion -e epi_rules -e epi_incident -e epi_auth -e epi_integration
pip install ultralytics opencv-python pyjwt httpx greenlet aiosqlite
```
(Se algum `pip install -e` reclamar de uma pasta, instale as dependências listadas no `pyproject.toml` dela.)
Coloque o modelo treinado (`.pt`) em um lugar seu, por exemplo `~/modelos/epi.pt`.

## 2. Subir tudo para a demonstração (um terminal)
Use o `start_demo.py`: além dos serviços, ele cria o funcionário de demonstração, as regras com 3 s de persistência e os EPIs dele no tracker. Sem isso nenhuma pessoa é identificada e nenhum incidente abre.
```
set -a; . .local/segredos.env; set +a        # segredos locais (o ./scripts/subir_local.sh start cria o arquivo na primeira vez)
cd epi_integration
python scripts/start_demo.py --evidence --model /caminho/do/best.pt
```
Sem YOLO: `--mock`. Ctrl+C encerra tudo. Crie o seu usuário uma vez (antes de subir, com `.local/segredos.env` carregado):
```
cd epi_auth && AUTH_DB_PATH=../.local/auth.db python -m app.cli create-user --username sophia --name "Sophia" --role SUPERVISOR && cd ..
```

## 3. Câmera (outro terminal, mesmo venv)
Rode `./scripts/camera_local.sh` (carrega os segredos e todas as variáveis; aceita a fonte: `./scripts/camera_local.sh video.mp4`). Não cole o comando em várias linhas no Terminal: cada linha vira um comando separado.
`--source` aceita `0` (webcam), `video.mp4` ou `rtsp://usuario:senha@ip:554/stream`. No Mac, autorize a câmera para o Terminal em Ajustes do Sistema → Privacidade e Segurança → Câmera. `q` fecha a janela.
Fique sem capacete por mais de 3 segundos: o incidente abre e o recorte é enviado.

## 4. Ver na tela
Use o front do repositório `visao-do-porto-evolucao` (`cd frontend && npm install && npm run dev`, depois abra http://localhost:5173), entre com o usuário criado e abra o incidente na fila.

## 4b. Reconhecimento facial real (opcional, só voluntários com consentimento)

Desligado por padrão (a demonstração usa "DEMO IDENTITY"). Para testar com rosto real (InsightFace; 1º uso baixa o modelo):

0. Em TODO terminal novo: `cd ~/epi-vision-porto-itaqui && source .venv/bin/activate` (o prompt deve mostrar `(.venv)`).
1. Serviços (terminal 1): `./scripts/subir_local.sh stop`, depois, em uma linha:
   `FUS_IDENTITY_CONFIDENCE_THRESHOLD=0.40 EPI_CONFIDENCE_THRESHOLD=0.40 EPI_FACE_PROVIDER=insightface PPE_DETECTOR_PROVIDER=yolo PPE_DETECTOR_MODEL_PATH="<caminho do best.pt>" ./scripts/subir_local.sh start`
   (sem o detector `yolo` a câmera dá `VISION: ERROR`; se algum serviço sair de antes, o `stop` evita configuração antiga)
2. Funcionário (terminal 2, venv ativo): `python epi_integration/scripts/criar_funcionario_demo.py`
3. Cadastro: `python epi_integration/scripts/cadastrar_voluntario.py` (termo, digitar ACEITO, ESPAÇO captura; a foto não é guardada)
4. Teste: `python epi_integration/scripts/cadastrar_voluntario.py --testar`
5. Câmera com reconhecimento: `EPI_PIPELINE_FACE_RECOGNITION=true ./scripts/camera_local.sh` (o rótulo mostra "RECONHECIMENTO FACIAL"; sem rosto reconhecido, a pessoa fica "não identificada", nunca vira outra)
6. Apagar o rosto: `python epi_integration/scripts/cadastrar_voluntario.py --apagar` (outro voluntário: `--registration DEMO-0002`)

**Calibração (decisão do grupo):** a confiança do modelo real fica em ~0,45–0,75 para a mesma pessoa (similaridade 0,76–0,88),
e os padrões do código (0,80) foram feitos para o mock. Há DOIS limiares: `EPI_CONFIDENCE_THRESHOLD` (Identity, MATCHED) e
`FUS_IDENTITY_CONFIDENCE_THRESHOLD` (Fusion, atribuir o EPI à pessoa). Abaixo do limiar do Fusion o resultado é
`INDETERMINATE` e nenhum incidente abre (comportamento conservador). Os 0,40 acima são só para teste local; os valores finais
dependem de mais voluntários e condições (luz, distância, capacete/óculos). Validado em teste local com 2 voluntários: cadastro,
reconhecimento sem confusão, incidente aberto com nome (supervisor) e só código (operador).

Atenção: com o modo real, a biometria de demonstração é recusada (esperado) e o rosto precisa ser cadastrado no passo 3.

## 5. Parar
Ctrl+C no terminal do `start_demo.py`. As imagens de teste ficam em `.local/evidencias/` (apague quando quiser).

## Observações
- `./scripts/subir_local.sh` sobe só os serviços (sem funcionário nem regras de demonstração); serve para testar login e API.
- Se o log do Identity mostrar 401, o terminal da câmera não carregou `.local/segredos.env`.
