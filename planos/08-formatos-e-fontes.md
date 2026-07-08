# 08 — Formatos de entrada e fontes de fundo

## Objetivo

Consolidar e ampliar, de forma **extensível**, os formatos de geometria e as **fontes de fundo** do
mapa (raster local, tiles Planet/Google/Esri), além do papel do **PDF-modelo** (referência de estilo
para a IA). Sem inflar o escopo agora — apenas planejar os pontos de extensão.

## Estado atual

- Geometria (`core/geo.py`): `.zip`, `.shp`, `.geojson`/`.json`, `.kml`, `.kmz` ✓.
- Raster de fundo (`core/raster.py`): **GeoTIFF local** (tifffile+Pillow), reprojeção por cantos,
  esticamento de contraste ✓.
- Basemap por tiles (`core/basemap.py`): Esri World Imagery / OSM ✓.
- Inventário de fontes (`catalogo/servicos_geo.json`): **Planet Basemaps** (auth `api_key`, mosaicos
  mensais) e **Google Satellite** (xyz) — ainda **não** ligados ao motor.

## Escopo

**Inclui (planejar)**
- **Planet Basemaps** como fundo (auth `planet_api_key`, mosaico por data — casa com a "Data da
  imagem" do bloco metadados).
- **Google Satellite** como fundo tiles (xyz) — alternativa rápida.
- **PDF-modelo**: pipeline em que a IA recebe um PDF de referência (texto/preview) e **reproduz o
  padrão** (layout/simbologia) para os novos dados — decisão do usuário; **não** importa geometria.
- Ponto de extensão para **novos formatos** (ex.: File Geodatabase, GPKG) sem reescrever o dispatch.

**Não inclui**
- Importar geometria de PDF; DWG/CAD; serviços pagos além do Planet já inventariado.

## Design / contrato

### Fonte de fundo no MapSpec

```json
"raster_fundo": "C:/.../cena.tif"          // arquivo local (atual)
"basemap": "satellite" | "planet" | "google" | "osm" | "none"
"basemap_config": { "planet_mosaic": "global_monthly_2000_07_mosaic" }   // quando aplicável
```

- Ordem de resolução do fundo: `raster_fundo` (local) → `basemap`(tiles) → neutro.
- **Planet**: `core/basemap.py` ganha um provedor `planet` (URL de `servicos_geo.json`,
  `{mosaic}/{z}/{x}/{y}`, header/token do `planet_api_key`). Mosaico casa com a data da imagem.
- **Google**: provedor `google` (xyz `lyrs=s`). Uso conforme termos — expor como opção, não default.

### PDF-modelo (referência de estilo)

- `core/nexomap_modelo.py` (novo): recebe um PDF de referência, extrai texto/preview (PyMuPDF) e
  monta um **resumo de estilo** (título, presença de tabela/legenda/insets, paleta aproximada) que
  entra no **contexto do prompt** da IA para orientar o MapSpec dos novos dados.
- **Não** faz OCR de geometria; é guia visual/textual.

### Extensibilidade de formatos

- Manter o **dispatch por extensão** em `core/geo.py` (`abrir_geometria`) e o de raster em
  `core/raster.py`. Novos formatos = nova função + entrada no dispatch, sem tocar no resto.
- Documentar a interface `(-> features_utm, features_geo, bbox, area_ha, avisos)`.

## Checklist de implementação

- [ ] Provedor `planet` em `core/basemap.py` (auth `planet_api_key`, mosaico por data).
- [ ] Provedor `google` em `core/basemap.py` (xyz satellite) como opção.
- [ ] `basemap_config` no MapSpec + resolução de ordem de fundo documentada.
- [ ] `core/nexomap_modelo.py`: PDF-modelo → resumo de estilo → contexto do prompt.
- [ ] Documentar o ponto de extensão de formatos (geometria e raster).
- [ ] (Opcional) GPKG/GeoPackage como leitura de geometria (avaliar dependência).

## Plano de testes

**Unit**
- [ ] Ordem de resolução do fundo (`raster_fundo` > `basemap` > neutro).
- [ ] Montagem correta da URL Planet (mosaico/z/x/y) e Google (offline, só URL).
- [ ] `core/raster.py` com `raster_min.tif` (georreferência conhecida) → extent correto.

**Integração rede (opcional)**
- [ ] Planet com `planet_api_key` retorna tiles não vazios (skip sem chave).

**Ao vivo**
- [ ] PDF-modelo real → resumo de estilo coerente influencia o MapSpec.

## Critérios de aceite

- Fundo do mapa pode ser raster local, Planet, Google ou tiles — escolhido pela IA/usuário.
- PDF-modelo orienta o estilo sem virar fonte de geometria.
- Novos formatos entram por um único ponto de extensão, sem regressão.

## Riscos e decisões abertas

- **Planet**: exige `api_key` válido e cota; termos de uso. Confirmar antes de usar em produção.
- **Google tiles**: termos de uso — manter como opção explícita, não default.
- **Datum/CRS de rasters variados**: hoje assume zona UTM compatível; warp completo (reprojeção de
  pixel) fica como evolução se aparecer raster fora da zona.

## Dependências

- `catalogo/servicos_geo.json` (URLs Planet/Google — não inventar).
- Plano 03 (camadas) compartilha o cliente HTTP e o cache.
