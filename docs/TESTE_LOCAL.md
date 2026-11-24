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
Rode o comando que o `start_demo.py` imprimiu no fim (já inclui a evidência). Antes: `set -a; . .local/segredos.env; set +a`.
`--source` aceita `0` (webcam), `video.mp4` ou `rtsp://usuario:senha@ip:554/stream`. No Mac, autorize a câmera para o Terminal em Ajustes do Sistema → Privacidade e Segurança → Câmera. `q` fecha a janela.
Fique sem capacete por mais de 3 segundos: o incidente abre e o recorte é enviado.

## 4. Ver na tela
Use o front do repositório `visao-do-porto-evolucao` (`cd frontend && npm install && npm run dev`, depois abra http://localhost:5173), entre com o usuário criado e abra o incidente na fila.

## 5. Parar
Ctrl+C no terminal do `start_demo.py`. As imagens de teste ficam em `.local/evidencias/` (apague quando quiser).

## Observações
- `./scripts/subir_local.sh` sobe só os serviços (sem funcionário nem regras de demonstração); serve para testar login e API.
- Se o log do Identity mostrar 401, o terminal da câmera não carregou `.local/segredos.env`.
