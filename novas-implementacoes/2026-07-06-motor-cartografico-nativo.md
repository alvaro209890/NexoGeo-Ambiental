# Motor Cartográfico Nativo — NexoMap AI (2026-07-06)

## Resumo

Migração completa do pipeline de mapas: o NexoMap AI agora usa um motor
cartográfico 100% nativo (matplotlib), eliminando a dependência do ArcGIS/ArcMap.
Tudo roda em qualquer máquina com Python — Windows, Linux e macOS.

---

## O que mudou

### 1. ArcGIS/ArcMap REMOVIDO
- **Deletado** `core/arcgis_bridge.py` (109 linhas) — ponte MXD/Python
- **Deletado** `templates/mxd/MANIFEST.json` — manifesto de templates .mxd
- **Deletado** `templates/mxd/scripts/export_mxd.py` — script de exportação ArcMap
- **Deprecated** `strict_mxd` na API — campo aceito e ignorado por compatibilidade
- **Remapeamento** `"mxd"` → `"geojson"` nas saídas do MapSpec (legado transparente)

### 2. Motor Nativo de Mapas (novo)
`core/nexomap_renderer.py` — reescrito de 224 para 612 linhas (+388):

- **Escala verdadeira** no papel (1:N honesto, calculado pelo bbox UTM)
- **Basemap de tiles** (satélite Esri World Imagery ou OSM) montado e reamostrado
- **Camadas WFS reais** do catálogo desenhadas com estilo do MapSpec
- **Suporte a ArcGIS REST** (ex.: PAMGIA/IBAMA) para camadas que não falam WFS
- **Grade UTM** com coordenadas marginais formatadas
- **Barra de escala segmentada** com comprimentos "redondos" (1-2-5)
- **Seta de norte** estilizada com stroke branco
- **Legenda** automática com patches coloridos
- **Minimapa de localização** (Brasil com bounding box do projeto)
- **Bloco de metadados** (data, CRS, escala, fonte das camadas)
- **Rótulos** em feições com stroke para legibilidade

### 3. Basemap por Tiles (novo)
`core/basemap.py` (125 linhas):

- Baixa tiles XYZ públicos (Esri World Imagery ou OpenStreetMap)
- Monta mosaico para o extent UTM do mapa
- Reamostra (vizinho mais próximo) para encaixar perfeitamente sob as camadas
- Sem internet → fundo neutro (nunca falha)

### 4. Camadas do Catálogo (novo)
`core/nexomap_layers.py` (174 linhas):

- Busca WFS 2.0.0 com fallback automático para WFS 1.0.0 (servidores antigos)
- Suporte a ArcGIS REST `/query` com GeoJSON (ex.: IBAMA/PAMGIA)
- Todas as camadas reprojetadas para UTM do projeto
- Exportação GeoJSON (EPSG:4674) em `camadas/<id>.geojson` — abre direto no QGIS
- Falha de rede vira aviso, não derruba a geração

### 5. Templates de Layout Nativo
`templates/layouts/MANIFEST.json` — novo manifesto com 3 layouts:

| ID | Formato | Orientação | Dimensão (mm) |
|---|---|---|---|
| `tematico_a3_retrato` | A3 | retrato | 297×420 |
| `dinamica_a3_paisagem` | A3 | paisagem | 420×297 |
| `tematico_a4_paisagem` | A4 | paisagem | 297×210 |

Projetos antigos com `templates_mxd` caem automaticamente no manifesto nativo.

### 6. Suporte a GeoJSON, KML e KMZ
`core/geo.py` (+210 linhas):

- `_geojson_features()` — lê .geojson/.json com CRS legado
- `_kml_features()` — lê Placemarks (Polygon, LineString, Point, MultiGeometry)
- `_kml_coords()` — parser de coordenadas KML
- `abrir_geometria()` — dispatch unificado para .zip/.shp/.geojson/.kml/.kmz
- `importar_shape_extraido()` refatorado com `_montar_importado()` interno
- `.close()` no shapefile.Reader (vazamento de recurso corrigido)
- Tratamento defensivo de área inválida no MapBiomas Alerta

### 7. API (`api/app.py`)
- Removeu `import tkinter` (quebrava em headless Linux)
- `abrir` cross-platform: `os.startfile` (Windows), `open` (macOS), `xdg-open` (Linux)
- `nexomap_area_base`: aceita .zip, .shp, .geojson, .kml, .kmz
- `nexomap_doctor`: usa `nexomap_doctor_mod.run()` (motor nativo)
- `nexomap_generate`: removeu `strict_mxd`, adiciona camadas WFS reais e GeoJSON

### 8. UI (`ui/src/App.jsx`)
- Campo de geometria: "Shapefile compactado (.zip)" → "Geometria da area (.zip, .shp, .geojson, .kml, .kmz)"
- Pré-análise: exibe fazendas intersectadas (CAR) e avisos (warnings)
- Resultados: `mxd` → `camadas` (GeoJSON) nos botões de ação
- Doctor: mostra motor nativo + dependências em vez de ArcGIS
- Manual: atualizado para descrever o pipeline sem ArcMap

### 9. Outros ajustes
- `nexomap_generator.py`: busca camadas WFS reais, exporta GeoJSON, sem `strict_mxd`
- `nexomap_project.py`: `templates_mxd` → `templates_layouts`, compatível com `geometria`
- `mapspec.py`: `mxd` → `geojson` nas saídas, fallback transparente
- `nexomap_doctor.py`: checa matplotlib/numpy/PIL/shapely/pyproj/shapefile/fitz
- `automations/pre_analise.py`: aceita .geojson/.kml/.kmz, área defensiva
- `catalogo/camadas.json`: embargos_ibama migrou de WMS para ArcGIS REST (PAMGIA)
- `requirements.txt`: adicionados `numpy` e `pillow`
- `schema`: adicionado `templates_layouts`, `geometria`, deprecated `templates_mxd`
- `exemplos/`: template atualizado com `templates_layouts`

### 10. Testes novos
- `tests/test_geo_formats.py` — teste dos formatos de geometria (.shp, .geojson, .kml)
- `tests/test_renderer.py` — smoke test do motor cartográfico nativo
- `tests/test_nexomap.py` — adicionados testes de legado (mxd→geojson) e fallback de templates

---

## Compatibilidade

- Projetos `.nexomap/projeto.nexomap.json` antigos com `templates_mxd` continuam
  funcionando — o sistema detecta e redireciona para o manifesto nativo.
- MapSpec com `"mxd"` nas saídas é automaticamente convertido para `"geojson"`.
- `area_base.tipo = "shapefile_zip"` segue suportado; novo tipo `"geometria"`
  aceita qualquer formato (.zip/.shp/.geojson/.kml/.kmz).

---

## Arquivos novos (não rastreados anteriormente)

| Arquivo | Descrição |
|---|---|
| `core/basemap.py` | Download e mosaico de tiles XYZ |
| `core/nexomap_layers.py` | Busca WFS/ArcGIS REST + export GeoJSON |
| `templates/layouts/MANIFEST.json` | Manifesto de layouts nativos |
| `tests/test_geo_formats.py` | Testes de formatos de geometria |
| `tests/test_renderer.py` | Smoke test do renderer nativo |

---

## Arquivos deletados

| Arquivo | Motivo |
|---|---|
| `core/arcgis_bridge.py` | ArcMap removido |
| `templates/mxd/MANIFEST.json` | Substituído por layouts nativos |
| `templates/mxd/scripts/export_mxd.py` | ArcMap removido |
