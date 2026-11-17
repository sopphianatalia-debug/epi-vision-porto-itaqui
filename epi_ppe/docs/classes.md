# Classes de detecção

As classes são **configuráveis** (seção 5 do spec). O conjunto padrão:

| Classe | Descrição | É EPI? | Região corporal esperada (fração vertical na pessoa) |
|---|---|:---:|---|
| `PERSON` | Pessoa | não | — |
| `HELMET` | Capacete | sim | 0.00–0.30 (cabeça) |
| `SAFETY_VEST` | Colete refletivo | sim | 0.20–0.70 (torso) |
| `GLOVES` | Luvas | sim | 0.30–0.95 (mãos) |
| `SAFETY_BOOTS` | Botas de segurança | sim | 0.75–1.00 (pés) |
| `SAFETY_GLASSES` | Óculos de proteção | sim | 0.00–0.28 (olhos) |
| `EAR_PROTECTION` | Protetor auricular | sim | 0.00–0.32 (orelhas) |

## Como adicionar uma classe

1. Acrescente o valor em `app/enums.py::DetectionClass`. Ele entra automaticamente
   em `PPE_CLASSES` (tudo que não é `PERSON`).
2. Adicione a região corporal esperada em
   `app/association/associator.py::EXPECTED_REGION` (opcional, melhora a associação).
3. Adicione um threshold próprio em `app/config.py` e no mapa de
   `ObjectDetectionService.threshold_for` (senão usa o `default`).
4. Se usar o provider YOLO, mapeie o nome da classe do modelo em
   `app/detection/providers/yolo_provider.py::DEFAULT_NAME_MAP`.

Nenhuma parte do pipeline (tracking, associação, avaliação) precisa mudar.
