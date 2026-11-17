# Dataset — estrutura e documentação

Estrutura de diretórios recomendada (formato YOLO):

```
dataset/
├── data.yaml                # nomes de classes + caminhos
├── train/
│   ├── images/
│   └── labels/              # um .txt por imagem (formato YOLO)
├── validation/
│   ├── images/
│   └── labels/
└── test/
    ├── images/
    └── labels/
```

## Formato das anotações (YOLO)

Cada linha de um `.txt`: `class_id cx cy w h` — coordenadas **normalizadas**
(0–1) do centro e do tamanho da caixa. `class_id` segue a ordem de `data.yaml`.

Exemplo (`data.yaml`):

```yaml
names:
  0: PERSON
  1: HELMET
  2: SAFETY_VEST
  3: GLOVES
  4: SAFETY_BOOTS
  5: SAFETY_GLASSES
  6: EAR_PROTECTION
train: train/images
val: validation/images
test: test/images
```

## Metadados a documentar por imagem (recomendado, em CSV/JSON à parte)

- **origem**: qual câmera / local do porto;
- **resolução** e proporção;
- **condições ambientais**: sol forte, chuva, neblina, noite;
- **horário**: manhã/tarde/noite (afeta iluminação);
- **distância** da pessoa à câmera (perto/médio/longe);
- **oclusões**: parcial (equipamentos, outras pessoas, contêineres);
- **tipos de EPI** presentes na cena.

## Diretrizes de coleta

Priorizar imagens **representativas do ambiente portuário**: contêineres, guindastes,
coletes de várias cores, capacetes de diferentes modelos, trabalhadores a distâncias
e ângulos variados, e cenas negativas (pessoas sem EPI) para reduzir falsos positivos.
Balancear as classes: EPIs pequenos (óculos, protetor auricular, luvas) costumam ser
sub-representados e exigem coleta dirigida.

## Divisão

Split sugerido: **70% train / 15% validation / 15% test**, garantindo que imagens
da **mesma sequência de vídeo/câmera** não vazem entre os splits (evita otimismo na
avaliação). A avaliação (`app/evaluation`) calcula Precision/Recall/F1/AP por classe
e mAP sobre o conjunto de teste.
