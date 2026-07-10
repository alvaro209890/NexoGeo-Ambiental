# HANDOFF — NexoGeo-Ambiental (2026-07-10, estilos do ArcMap)

Pedido da sessão: trazer os estilos salvos do ArcMap do usuário (linhas, hachuras,
ícones) para o motor nativo (`core/nexomap_renderer.py`). Resultado parcial — cores
reais entraram, ícones de ponto não (limitação técnica, ver abaixo).

## O que foi tentado e não funcionou

O estilo pessoal do ArcMap (`Usuario.style`, ArcMap 10.8, formato Access/Jet) tem
**77.200+ símbolos só na categoria Line Symbols** — claramente uma biblioteca de
referência acumulada por anos, não uma lista curada. Ler isso via ArcObjects/COM
(`esriFramework.StyleGallery`, Python 2.7 do ArcGIS Desktop) é viável em princípio
(cores/largura/traço/hachura são extraíveis via `ILineSymbol`/`IFillSymbol`/
`ISimpleLineSymbol` etc.), mas na prática:

- `IStyleGallery::LoadStyle` para as categorias **Fill Symbols** e **Marker Symbols**
  trava indefinidamente nesta máquina (testado 4× separadas, 10-25 min cada vez sem
  terminar). Line Symbols carrega rápido (milhares de itens/segundo).
- Descartado bloat do arquivo: compactar/reparar via `JRO.JetEngine` (226→214 MB) não
  mudou a lentidão.
- Suspeita de antivírus (Windows Defender, escaneamento em tempo real de acessos COM
  a um arquivo de 200+ MB) não pôde ser testada — exclusão bloqueada por Tamper
  Protection gerenciada pela organização do usuário.
- Causa raiz não identificada com certeza.

**Não tente reabrir esse caminho sem necessidade real.** Os scripts de sondagem ficaram
fora do repo (`scratchpad` da sessão), não foram versionados.

## O que funcionou: `Favorites.stylx`

O usuário tem `C:\Users\<user>\AppData\Roaming\ESRI\ArcGISPro\Favorites.stylx` —
formato ArcGIS Pro (SQLite, tabela `ITEMS` com coluna `CONTENT` em JSON/CIM). Só
**5 itens**, lidos direto com `sqlite3` da stdlib (sem ArcObjects, instantâneo):

| Nome | Cor (contorno) | Uso provável |
|---|---|---|
| AVN | `#ffff00` (amarelo) | Vegetação nativa |
| ARL | `#55ff00` (verde) | Reserva legal |
| AC | `#ff00c5` (magenta) | Área consolidada |
| Hidro | `#0070ff` (azul) | Hidrografia (sem camada correspondente em `camadas.json` ainda) |
| AIR | `#ff0000` (vermelho) | Não identificado — sem camada correspondente clara |

Todos são polígonos "vazados": contorno colorido largura 2, preenchimento
`alpha=0` (transparente) — o mesmo padrão que o renderer já usa para hachuras
(`_layer_color`: com hachura, preenchimento vira `"none"` e só o contorno/hachura
aparece na cor da camada).

## Mudanças em `core/nexomap_renderer.py`

1. **`LAYER_ID_COLORS`** (novo dict, logo após `THEME_COLORS`): cores reais por
   `layer.id`, prioridade **acima** de `THEME_COLORS` (por tema) e **abaixo** de
   qualquer `estilo.linha`/`estilo.preenchimento` explícito no MapSpec.
   - `car_avn` / `simcar_avn` → `#ffff00`
   - `car_arl` / `simcar_arl` → `#55ff00`
   - `area_consolidada_simcar` / `uso_consolidado` → `#ff00c5`
   - `AIR` e `Hidro` **não mapeados** — não há `id` de camada correspondente em
     `catalogo/camadas.json` (nenhuma camada de hidrografia existe ainda; `AIR` é
     ambíguo, não identificado).
   - `_layer_color(estilo, tema, layer_id)` ganhou o parâmetro `layer_id`.

   ⚠️ **Isso NÃO muda o fluxo "Mapas por CAR" nem os exemplos calibrados** — os 7
   cards de `catalogo/modelos_mapas.json` já definem `estilo.linha`/`hachura`
   explícitos por camada (calibrados contra os PDFs-modelo reais do cliente, ver
   [`PADRAO_IMAP_RENDERER.md`](PADRAO_IMAP_RENDERER.md): AVN hachura verde `#00b050`,
   AC magenta `#ff00ff`). Essas cores **são diferentes** das do `Favorites.stylx`
   pessoal do usuário. `LAYER_ID_COLORS` só entra em jogo quando **não** há estilo
   explícito nem override de tema — ex. caminhos rule-based/ad-hoc que referenciam
   essas camadas sem estilo próprio.

2. **Dash pattern por camada** (novo): `estilo.dash` (lista de segmentos on/off em
   pontos, ex. `[6, 3]`) é lido em `_layer_color` (retorna 5-tupla agora, era
   4-tupla) e aplicado via `dashes=` em `_draw_geoms` (linhas, contornos de
   polígono) e em `_legend_swatch`/`Line2D.set_dashes` na legenda. Antes só existia
   linha sólida.

3. **Marcador com ícone/imagem** (novo): `estilo.icone` (caminho de um PNG) desenha
   o ponto via `AnnotationBbox`/`OffsetImage` em vez do círculo padrão
   (`_draw_icon_markers`, com cache `_load_icon_image` via `functools.lru_cache`).
   Fallback automático pro círculo se o arquivo não existir/falhar ao ler. A
   legenda continua usando o círculo simples (`OffsetImage` não tem handler de
   legenda nativo no matplotlib — não implementado).

## Pendências

- **Ícones reais dos marcadores de ponto** (Camera, Árvores, Fogo, Vértices, fotos,
  Pontos) — não extraídos, ver limitação acima. O código de renderização
  (`estilo.icone`) já está pronto; falta só os arquivos PNG. Se o usuário
  conseguir exportá-los manualmente do ArcMap (Style Manager → botão direito no
  símbolo → não há "salvar como imagem" nativo fácil; alternativa: adicionar os
  6 símbolos ao Favorites do ArcGIS Pro, se/quando o Pro estiver instalado nesta
  máquina — o `Favorites.stylx` é trivial de ler via sqlite3, ao contrário do
  `.style` legado do ArcMap).
- **AIR e Hidro** sem camada correspondente em `catalogo/camadas.json` — perguntar
  ao usuário o que "AIR" representa e se vale a pena criar uma camada de
  hidrografia para usar a cor `#0070ff`.
- Arquivos temporários **fora do repo** que o usuário pode limpar (não afetam o
  app): `Usuario_compactado.style` e `Usuario.style.bak_*` em
  `AppData\Roaming\ESRI\Desktop10.8\ArcMap\` (~450 MB no total).
