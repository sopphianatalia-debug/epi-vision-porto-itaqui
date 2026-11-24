# Teste local com webcam, vídeo ou RTSP (macOS/Linux)

Tudo roda no seu computador. Segredos e dados ficam em `.local/` (fora do Git).

## 1. Uma vez só
```
git clone https://github.com/sopphianatalia-debug/epi-vision-porto-itaqui.git
cd epi-vision-porto-itaqui
python3 -m venv .venv && source .venv/bin/activate
pip install -e epi_ppe -e epi_identity -e epi_fusion -e epi_rules -e epi_incident -e epi_auth -e epi_integration
pip install ultralytics opencv-python pyjwt httpx
```
(Se algum `pip install -e` reclamar de uma pasta, instale as dependências listadas no `pyproject.toml` dela.)
Coloque o modelo treinado (`.pt`) em um lugar seu, por exemplo `~/modelos/epi.pt`.

## 2. Subir os serviços
```
export PPE_DETECTOR_PROVIDER=yolo
export PPE_DETECTOR_MODEL_PATH=~/modelos/epi.pt
./scripts/subir_local.sh start
./scripts/subir_local.sh status      # tudo OK?
```
Criar o seu usuário (pede a senha sem mostrar):
```
cd epi_auth && AUTH_DB_PATH=../.local/auth.db python -m app.cli create-user --username sophia --name "Sophia" --role SUPERVISOR && cd ..
```

## 3. Câmera
```
set -a; . .local/segredos.env; set +a
export EPI_PIPELINE_SEND_EVIDENCE=true EPI_PIPELINE_INCIDENT_SERVICE_KEY=$INC_SERVICE_KEY
python epi_integration/scripts/run_camera_demo.py --source 0 --camera-id CAM-01
```
`--source` aceita `0` (webcam), `video.mp4` ou `rtsp://usuario:senha@ip:554/stream`. No Mac, autorize a câmera para o Terminal em Ajustes do Sistema → Privacidade e Segurança → Câmera. `q` fecha a janela.
Fique sem capacete por mais de 3 segundos: o incidente abre e o recorte é enviado.

## 4. Ver na tela
Use o front do repositório `visao-do-porto-evolucao` (`cd frontend && npm install && npm run dev`, depois abra http://localhost:5173), entre com o usuário criado e abra o incidente na fila.

## 5. Parar
```
./scripts/subir_local.sh stop
```
Logs: `.local/logs/<serviço>.log`. Para apagar as imagens de teste: apague `.local/evidencias/`.

## Observações
- Sem `PPE_DETECTOR_PROVIDER=yolo` o serviço usa o detector de teste (mock), que não lê imagem de câmera.
- Este caminho com câmera real ainda não foi exercitado de ponta a ponta; se algo falhar, mande o conteúdo de `.local/logs/`.
