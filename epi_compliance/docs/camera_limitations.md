# Limitações por tipo de câmera

Este módulo **nunca conclui além do que a câmera permite**. A qualidade da
verificação depende diretamente do enquadramento, resolução, ângulo e
iluminação. Abaixo, o impacto por tipo de instalação.

## Câmera de visão geral (grande angular, longe)
- **Vantagem**: cobre muitas pessoas e a cena inteira.
- **Limitação**: EPIs pequenos (óculos, luvas, protetor auricular) aparecem com
  poucos pixels → detecção fraca e posicionamento impreciso.
- **Comportamento esperado**: óculos/luvas tendem a `UNKNOWN` ou `NOT_VISIBLE`;
  capacete e colete (grandes) ainda são avaliáveis.

## Câmera de torso / cintura para cima (portaria, esteira)
- **Vantagem**: ótima para capacete, colete e óculos.
- **Limitação**: **pés fora de quadro** → botas não verificáveis.
- **Comportamento esperado**: `BOOTS = NOT_VISIBLE` (a pessoa é detectada
  cortada na borda inferior; a regra de visibilidade marca pés/pernas como não
  visíveis). O sistema **não** diz "sem botas".

## Câmera de solo / baixo ângulo
- **Vantagem**: boa para botas e pernas.
- **Limitação**: cabeça pode sair de quadro ou ficar em ângulo ruim → capacete
  incerto.
- **Comportamento esperado**: se a cabeça é cortada no topo, `HELMET = NOT_VISIBLE`.

## Câmera lateral (perfil)
- **Limitação**: uma das mãos costuma ficar ocluída pelo corpo.
- **Comportamento esperado**: a mão ocluída deve ir para `NOT_VISIBLE` (ideal com
  pose real); o resumo de luvas passa a `1/1` ou `not_verifiable`, nunca
  penalizando o que não dá para ver.

## Iluminação e clima (porto: sol forte, neblina, chuva, noite)
- Reduzem a confiança da detecção → mais frames caem em `UNKNOWN`.
- A **análise temporal** ajuda: exige consistência ao longo de vários frames
  antes de concluir, reduzindo falsos positivos causados por um frame ruim.

## Distância
- Quanto mais longe, menor o EPI em pixels. Recomenda-se posicionar câmeras de
  forma que uma pessoa ocupe altura suficiente do frame para os EPIs relevantes
  aparecerem com nitidez.

## Recomendação de projeto
Nenhuma câmera única cobre tudo bem. O ideal é **combinar enquadramentos**
(ex.: uma de torso para capacete/colete + uma de solo para botas) e deixar o
motor de conformidade consolidar por `person_track_id` (via Módulo 1/2),
mantendo `NOT_VISIBLE` onde cada câmera não alcança.
