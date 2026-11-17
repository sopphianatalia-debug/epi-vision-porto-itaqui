# O modelo de visão (a parte que não está no repositório)

O arquivo do modelo (`best.pt` / `best_cores.pt`) **não está no Git**: tem dezenas de MB, é
gerado por treinamento e muda a cada rodada. Aqui está o que ele é e como foi feito.

## O que é
- Modelo **YOLOv8n** (Ultralytics), versão pequena, ajustada (fine-tuning) para detectar EPIs.
- Classes base (10): Hardhat, Mask, NO-Hardhat, NO-Mask, NO-Safety Vest, Person, Safety Cone,
  Safety Vest, machinery, vehicle. O serviço `epi_ppe` converte esses nomes em tipos de EPI
  (capacete, colete etc.) e ignora as classes "NO-*": ausência é decidida pelas Regras, não pelo modelo.

## Como foi treinado
- **Rodada 1 (cores):** treino no Google Colab (GPU T4) para incluir coletes de outras cores
  (inclusive azul). Resultado na validação: capacete mAP50 0,889; colete 0,918; pessoa 0,883;
  média geral 0,725.
- **Rodada 2 (luvas e botas):** notebook `retreino2_luvas_botas.ipynb` usa o dataset
  Ultralytics Construction-PPE (CC BY 4.0) para adicionar luvas e botas. **Ainda não foi
  executado**: depende de GPU (a cota gratuita do Colab acabou). As regras de luvas e botas
  já existem e estão testadas; falta apenas o modelo reconhecê-las.

## Limitações conhecidas (honestas)
- O modelo é pequeno (yolov8n) e a confiança do capacete/colete oscila; por isso a demo usa
  confiança mínima 0,60 e, abaixo disso, o resultado é "indeterminado", nunca violação.
- Coletes com cores incomuns e pessoas muito próximas da câmera (cabeça cortada pelo quadro)
  geram "sem observação" em vez de decisão.
- Parte do dataset de luvas/botas tem imagens geradas por IA e enquadramento de perto.

## Como obter ou treinar o seu
1. Instale `ultralytics` e treine com seu dataset em formato YOLO, ou use o notebook do Colab.
2. Salve o `best.pt` fora do Git (ex.: `~/modelos/`).
3. Rode a demo apontando para ele: `python scripts/start_demo.py --model ~/modelos/best.pt`.
Sem modelo, use `--mock` para ver o fluxo completo com detecções simuladas.

## Créditos dos dados
- Ultralytics Construction-PPE (CC BY 4.0)
- Dataset de coletes (autor "college", CC BY 4.0)
