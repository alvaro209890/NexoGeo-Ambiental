# 03 — Camadas WMS/WFS (SEMA e demais bases)

## Objetivo

Fazer a IA **saber usar todas as bases disponíveis** — WMS/WFS da SEMA-MT e das demais fontes já
inventariadas — para desenhar camadas reais no mapa (embargos, CAR, UC, autos, desmatamento, terras
indígenas, SIGEF/INCRA etc.), com **estilo controlado pela IA** e **degradação graciosa**.

## Estado atual

- `core/nexomap_layers.py` busca camadas `catalogo.<id>` por **WFS-JSON** (2.0.0 c/ fallback 1.0.0)
  e **ArcGIS REST** (GeoJSON), reprojeta p/ UTM e exporta GeoJSON. Falha → aviso.
- `catalogo/camadas.json` expõe: `car_sema`, `embargos_sema`, `embargos_ibama`(REST),
  `terras_indigenas_funai`, `unidades_conservacao`, `alertas_mapbiomas`, `prodes_inpe`,
  `tipologia_sema`, `sigef_particular_mt`, `sigef_publico_mt`, `snci_particular_mt`,
  `assentamentos_incra`.
- **Inventário real completo** em `catalogo/servicos_geo.json` (fonte de verdade dos endpoints).

### Lacunas
- SEMA tem camadas ainda **não expostas** no catálogo: `embargos_siga_poligono`,
  `desembargos_sema`, `autos_siga_poligono` (e a `tipologia`).
- **INCRA acervo** devolve **GML (EPSG:4326)**, não JSON — o fetch atual (JSON) provavelmente falha.
- **IBAMA SISCOM** e alguns serviços só oferecem **WMS (raster GetMap)**, sem WFS.
- Sem **cache** de respostas; cada geração rebaixa a rede.

## Escopo

**Inclui**
- Completar `catalogo/camadas.json` com as camadas SEMA faltantes (endpoints reais do inventário).
- **Parser GML** para o acervo INCRA (SIGEF/SNCI) — reaproveitar o parser já existente em
  `automations`/scripts de referência (Lauri) que lê `gml:featureMember`.
- **WMS GetMap** para camadas raster-only (IBAMA SISCOM): baixar imagem por bbox e sobrepor.
- Cache local opcional das respostas por bbox (evitar rebaixar a rede em re-render).
- Tool `adicionar_camada`/`editar_camada`/`listar_camadas` (plano 00).

**Não inclui**
- Inventar endpoints novos. **Somente** os de `catalogo/servicos_geo.json` ou confirmados.
- Autenticação Planet (fica no plano 08, como basemap).

## Design / contrato

### Catálogo — completar (endpoints reais do inventário)

| id (novo) | fonte | endpoint/base | tipo |
|-----------|-------|---------------|------|
| `embargos_siga` | SEMA | `geo.sema.mt.gov.br/geoserver/ows` · `Geoportal:AREA_EMBARGADA_SIGA_POLIGONO` | wfs (auth) |
| `desembargos_sema` | SEMA | idem · `Geoportal:AREAS_DESEMBARGADAS_SEMA` | wfs (auth) |
| `autos_siga` | SEMA | idem · `Geoportal:AUTOS_DE_INFRACAO_SIGA_POLIGONO` | wfs (auth) |
| `embargos_ibama_siscom` | IBAMA | `siscom.ibama.gov.br/geoserver/publica/wms` · `publica:vw_brasil_adm_embargo_a` | **wms** |
| `alertas_mapbiomas_simpl` | MapBiomas | `production.alerta.mapbiomas.org/geoserver/ows` · `mapbiomas-alertas:crew_simplified-alerts` | wfs |

> Nota: `snci` no acervo INCRA usa o tema `imoveiscertificados_privado_mt` (ver
> `servicos_geo.json`), diferente do que está hoje no `camadas.json` — revisar.

### Tipos de fetch (por `tipo`)

- `wms_wfs` → WFS GetFeature JSON (atual).
- `arcgis_rest` → REST `/query` GeoJSON (atual).
- `wfs_gml` (**novo**) → GetFeature GML → parser `gml:Polygon/coordinates` → shapely (INCRA).
- `wms_raster` (**novo**) → WMS GetMap PNG por bbox → sobrepor como imagem com opacidade.

### Estilo controlado pela IA

Cada camada no MapSpec: `estilo{linha, preenchimento, opacidade, largura, hachura}` + `rotulo`.
Para `wms_raster`, `estilo.opacidade` controla a transparência do overlay.

### Auth

`auth` = nome do segredo (ex.: `sema_authkey`) lido de `secrets.local.json`. Sem segredo → a camada
vira **aviso** e sai do mapa (nunca quebra). Isso já existe; manter.

## Checklist de implementação

- [ ] Acrescentar as camadas SEMA faltantes ao `catalogo/camadas.json` (endpoints do inventário).
- [ ] Corrigir o tema SNCI (`imoveiscertificados_privado_mt`) conforme `servicos_geo.json`.
- [ ] Implementar `tipo: wfs_gml` em `nexomap_layers.py` (parser GML → shapely, EPSG:4326→UTM).
- [ ] Implementar `tipo: wms_raster` (GetMap por bbox, PNG, overlay com opacidade).
- [ ] Cache opcional por `(id,bbox,zoom)` em `<job>/.cache/` para re-render sem rede.
- [ ] Tool `listar_camadas` (read) e `adicionar_camada`/`editar_camada`/`remover_camada`.
- [ ] Enriquecer o contexto do prompt com **descrição de cada camada** (para a IA escolher certo).
- [ ] Rótulos de feição por atributo configurável (ex.: `NOME_IMOVEL`, `parcela_codigo`).

## Plano de testes

**Unit (`tests/test_layers.py`, com fixtures/offline)**
- [ ] Parser GML lê `gml:featureMember` de um XML fixo e produz shapely válido.
- [ ] `wms_raster` monta a URL GetMap correta (bbox, CRS, size, layers, format).
- [ ] Camada sem `auth` disponível vira aviso (não exceção).

**Integração (rede, marcado como opcional/slow)**
- [ ] SEMA embargos com `sema_authkey` retorna feições no bbox de uma área conhecida.
- [ ] INCRA SIGEF (GML) retorna parcelas que intersectam a área.
- [ ] IBAMA SISCOM WMS retorna PNG não vazio no bbox.

**Ao vivo (chave real quando disponível)**
- [ ] "Mapa com CAR e embargos da SEMA" → 2 camadas desenhadas + legenda + GeoJSON exportado.

## Critérios de aceite

- IA adiciona/edita camadas das bases SEMA/INCRA/IBAMA/FUNAI/MapBiomas/INPE por instrução.
- INCRA (GML) e IBAMA SISCOM (WMS raster) passam a funcionar, não só WFS-JSON.
- Sem credencial/rede, a geração degrada com aviso e o mapa ainda sai.
- Todas as camadas WFS/GML exportadas em GeoJSON (abrem no QGIS).

## Riscos e decisões abertas

- **Estabilidade dos servidores públicos** (INCRA/IBAMA caem com frequência) → cache + timeouts.
- **Limite de feições** (`MAX_FEATURES=500`) pode cortar áreas grandes → paginação futura.
- **Projeção do INCRA** (4326 lon/lat) já tratada pela reprojeção por shape.

## Dependências

- `catalogo/servicos_geo.json` (fonte dos endpoints — **não inventar**).
- Plano 02 (legenda) para itens vinculados a camadas.
- Plano 04 (tabelas) consome as feições para quantitativos.
