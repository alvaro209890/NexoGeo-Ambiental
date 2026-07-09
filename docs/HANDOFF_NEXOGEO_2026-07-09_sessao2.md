# HANDOFF — NexoGeo-Ambiental (2026-07-09, sessão 2)

Continuação do [HANDOFF_NEXOGEO_2026-07-09](HANDOFF_NEXOGEO_2026-07-09.md). Foco desta
sessão: fazer a **geração de mapas bater com o padrão IMAP real do cliente** (PDFs de
referência da análise do Lauri), ensinar a **IA** a usar os dados do imóvel, corrigir o
**logo**, revisar o **cruzamento de dados**, e **automatizar a série de mapas pelo número
do CAR**. Todas as mudanças estão nos módulos `core/` + `api/`; **117 testes offline
passam** (9 skip de rede).

---

## 1. Camadas de SHAPEFILE LOCAL no MapSpec (`fonte: "arquivo:<path>"`)

Antes o motor só desenhava camadas WFS do catálogo. Os mapas IMAP de referência são feitos
com os **shapefiles do imóvel** (lotes, AVN, AC, AUAS, tipologia). Adicionado:

- `core/nexomap_layers.py::_read_local_layer` — lê `.shp/.zip/.geojson/.kml` local, reprojeta
  pelo `.prj` (via `core.geo.ler_geometria`). `fetch_layers(..., project=project)` resolve
  paths relativos à raiz de dados/repo.
- `core/mapspec.py::validate_mapspec` aceita o prefixo `arquivo:`.
- **Rótulo estático por camada**: `estilo.rotulo_texto` (+ `rotulo_cor`) → desenhado no
  centroide, branco com contorno (`nexomap_renderer._label_layer_static`). Ex.: nome do lote
  + matrícula.

### Fixes de renderer para bater com o IMAP
- `estilo.largura` passou a ser respeitado nas camadas (antes fixo em 1.1).
- `preenchimento: "none"` = contorno-só (lotes vazados sobre o satélite).
- `_draw_perimeter` pula quando `largura <= 0` (perímetro invisível — usado quando os lotes
  vêm como camadas separadas vermelho/azul; o area_base só define o extent).
- Camadas com `rotulo_texto` (lotes/perímetros) desenham em **zorder 9** (sempre acima das
  sub-áreas AVN/AC/AUAS, independentemente da ordem de adição).
- Perímetro transparente/invisível **não entra na legenda** (evitava o crash
  `'transparente' is not a valid color` no `Line2D`).
- Inset "Tipologia vegetal": reposicionado o mini-mapa interno (rótulos não truncam mais).

---

## 2. Logo IMAP automático

O logo não aparecia porque o mapa só o desenhava se `marca.logo` apontasse para um arquivo
existente. Corrigido:

- Logo oficial empacotado em **`assets/logo_imap.png`** (recorte do "LOGOTIPO SEM FUNDO / TOM
  ESCURO", margens transparentes removidas).
- `nexomap_renderer._default_logo_path` — usado quando o MapSpec não traz `marca.logo`, então
  **todo mapa flagship sai com o logo** no rodapé-direito.
- `aplicar_modelo` (fluxo CAR) também injeta `marca` com o logo.

---

## 3. A IA sabe montar os mapas com os dados do imóvel

- `projeto.json` pode declarar **`camadas_locais`**: `[{id, arquivo, nome, tema, estilo{...}}]`
  → `NexoMapProject.camadas_locais_index()` → `ToolContext.camadas_locais`.
- Tools novas/estendidas em `core/nexomap_tools.py`:
  - `listar_camadas_locais` — lista os shapefiles do imóvel com estilo/rótulo sugeridos.
  - `adicionar_camada` aceita `fonte='local.<id>'` (resolve para `arquivo:<path>`, herda
    estilo/rótulo) e `arquivo:<path>` avulso.
- System prompt (`core/nexomap_agent.py`) manda preferir as camadas locais, usar grade DMS e
  desligar `inset_tipologia` fora de mapas de Tipologia. O logo é automático.
- **Validado ao vivo** (DeepSeek): pedido "Dinâmica 2026" → a IA chamou `listar_camadas_locais`
  + 5× `adicionar_camada(local.*)` e produziu o mapa fiel à referência, com logo.

> Nota: a API pública da DeepSeek exige `nexomap_deepseek_model = "deepseek-chat"`; o default
> do repo `deepseek-v4-pro` volta com `content` vazio.

---

## 4. Cruzamento de dados (overlay/quantitativos) — revisado e corrigido

`core/nexomap_quantitativos.py`:

- **Dedup por união**: `calcular_area_utm` agora faz `unary_union` das feições antes de medir
  — polígonos sobrepostos dentro de uma classe (comum no recorte SIMCAR) não contam 2×.
- **Tabela-matriz** `quantitativos_matriz(propriedades, classes, drawn_layers)` — cruza cada
  PROPRIEDADE (lote) × cada CLASSE (AVN/AC/AUAS), recortando por interseção (com dedup).
  Produz a tabela `Propriedade × [Área total, classes…] + TOTAL` igual à do IMAP. Ligada via
  `tabela.fonte = "quantitativos_matriz"`, config
  `{propriedades:[{rotulo,camada}], classes:[…], area_total_col, linha_total}`.
- Validado vs. referência do Lauri: **Lote 65 exato** (AVN 55,3378 / AC 217,9836 / AUAS
  6,5682 ha). Lote 66-A ~0,2 ha de diferença (slivers na divisa — recorto por lote, que é
  geodesicamente mais correto que atribuir a feição inteira).
- Testes: `tests/test_quantitativos.py` (dedup + matriz + resolver_tabela_matriz).

---

## 5. Automação da SÉRIE de mapas pelo NÚMERO DO CAR (100% WFS)

`core/nexomap_generator.py`:

- `gerar_serie_por_car(numero_car, modelos=None)` — busca a **ATP UMA vez** na SEMA
  (`nexomap_car.buscar_car`), reusa como area_base e gera a série
  `SERIE_CAR_PADRAO = [car, uso_consolidado, tipologia, dinamica, areas_protegidas, embargos,
  alertas]`. Um modelo que falha não derruba a série.
- `gerar_serie_por_car_stream` (SSE, um evento por mapa) + endpoint
  **`POST /api/nexomap/car-serie`** (`api/app.py`).
- Runner CLI: `projetos/car_web/rodar_serie_car.py "MT313839/2025"`.
- `aplicar_modelo` agora usa grade **DMS** (padrão IMAP) + logo.

### Requisitos de credenciais (o que falta para rodar ao vivo)
- **`sema_authkey`** (em `secrets.local.json`, na raiz ou em `projetos/car_web/`) — o ponto de
  entrada (buscar ATP pelo CAR) e as camadas SIMCAR/tipologia/uso/embargos-SEMA ficam
  **ocultos sem a chave** (a SEMA responde `400 InvalidParameterValue`).
- Camadas **públicas** (não precisam de chave) — testadas e funcionando nesta máquina:
  FUNAI (terras indígenas), MapBiomas, IBAMA (ArcGIS REST).
- **`planet_api_key`** (opcional) — basemap PLANET idêntico à referência; sem ele cai no Esri
  World Imagery.

---

## Bugs conhecidos / próximos passos

- **`prodes_inpe`** no `catalogo/camadas.json` aponta para um endpoint **WMS** mas é consultado
  como WFS-JSON → `JSONDecodeError`. Corrigir o `tipo`/`endpoint` (usar `wms_raster` ou o WFS
  correto do TerraBrasilis). MapBiomas cobre os alertas enquanto isso.
- **Embargos/Alertas/Autos/TI/UC não estão no recorte local** — são WFS externos; dependem das
  chaves acima para o fluxo por CAR.
- Título do flagship: quando reposicionado, ainda emite o aviso `ponto fora do quadro;
  ajustado` (cosmético — o clamp resolve).
- Faltam fixtures/testes visuais da série por CAR (precisam de `sema_authkey`).

---

## Como rodar (Windows, sem ArcMap)

```powershell
# venv com a stack geo (matplotlib, shapely, pyproj, pyshp, pymupdf, numpy, pillow)
.venv\Scripts\python.exe -m pytest tests -q          # 117 passam, 9 skip

# série de mapas por CAR (precisa sema_authkey em secrets.local.json)
.venv\Scripts\python.exe projetos\car_web\rodar_serie_car.py "MT313839/2025"
```
