# IA Cartográfica no padrão IMAP — motor nativo (2026-07-08)

## Resumo

Evolução do motor cartográfico nativo (matplotlib, **sem ArcMap**) para uma IA que
**cria, edita, valida e exporta** mapas ambientais/fundiários no padrão IMAP. O layout
**não é fixo**: quem monta o mapa é a IA (DeepSeek) por meio de um `MapSpec` versionado —
cada elemento do mapa é ligável/desligável pela IA. Ex.: no chat, "remova o título preto"
faz a IA setar `elementos_layout.titulo_caixa=false` e o elemento some.

Validado ponta a ponta reproduzindo o mapa de referência **"Dinâmica ano 2000"** (Fazenda
Jacarandá) sobre a área real `ATP.shp`, com o Landsat-5/TM (224/071, 30/07/2000) de fundo —
**10/10 checagens de validação OK**.

## O que foi implementado

### 1. Raster de fundo local — `core/raster.py` (novo)
Leitor de **GeoTIFF sem GDAL/rasterio** (usa `tifffile` para a georreferência e `Pillow`
para os pixels — decodifica LZW nativamente). Lê `ModelPixelScale`/`ModelTiepoint`/
`ModelTransformation` + GeoKeys, recorta a janela da área, reamostra e devolve a imagem
pronta para `imshow` já no CRS do mapa. Reprojeta os cantos com `pyproj` (resolve o offset
de hemisfério, ex.: UTM 22N com northing negativo → UTM 22S do projeto). Esticamento de
contraste por canal (2–98%) para o falso-cor 543 (magenta/verde) ficar vívido. Falha nunca
derruba a geração — devolve aviso.

### 2. Motor de layout paramétrico — `core/nexomap_renderer.py`
- **Grade DMS** (graus/min/seg) nos 4 lados — padrão IMAP — com UTM como opção (`grade_tipo`).
- **Raster de fundo local** (`raster_fundo`) com fallback para tiles e depois fundo neutro.
- **Hachuras** na simbologia (estilo `hachura`: `////`, `----`, …) + swatches na legenda.
- **Caixa de título preta** (canto sup. dir.) + **rosa-dos-ventos** (estrela de 8 pontas).
- **Inset "Tipologia vegetal"** (canto sup. esq.) com mini-legenda Floresta/Cerrado.
- **Tabela** multinível flutuando sobre o mapa (cabeçalho azul, zebra).
- **Faixa inferior**: [localização] · [METADADOS IMAGEM] · [Legenda] · [logo IMAP].
- **Layout flexível**: dois arranjos — *flagship* full-bleed (padrão IMAP) e *painel* lateral —
  e **cada peça respeita `elementos_layout`** (a IA controla o que aparece).

### 3. MapSpec estendido — `core/mapspec.py`
Novos campos opcionais (retrocompatíveis): `subtitulo`, `grade_tipo`, `raster_fundo`,
`metadados_imagem`, `tabela`, `marca` (logo/texto), `versao`, `parent_job_id`.
Parser tolerante às variações da IA (`saidas` como objetos/aliases `png`→`png_validacao`).
`apply_rule_based_edit()`: editor determinístico de fallback (sem IA).

### 4. Validação visual avançada — `core/nexomap_validation.py`
Além de abrir/título/página-não-vazia, agora checa: **`mapa_tem_imagem`** (variância de cor
no quadro do mapa → não está em branco), **`sem_sobreposicao_elementos`** e
**`sem_texto_cortado`** (bordas). O renderer computa o relatório de layout antes de salvar.

### 5. DeepSeek V4 Pro como cérebro — `core/nexomap_ai.py`
- Modelo padrão `deepseek-v4-pro` (configurável). Chave em `secrets.local.json` (**nunca**
  no código). `v4-pro` é modelo de raciocínio: adicionados `max_tokens` e controle de
  `thinking` (padrão desligado para JSON estruturado confiável).
- Prompt do sistema descreve os campos e as chaves de `elementos_layout` para a IA
  ligar/desligar elementos.
- **Edição versionada**: `spec_edit_from_prompt()` parte sempre do MapSpec atual (fonte de
  verdade — nunca do PDF/PNG), aplica a instrução e preserva o resto.

### 6. Edição versionada no pipeline — `core/nexomap_generator.py`
`edit_map(project, parent_job_id, prompt)` carrega o `mapspec.json` do job pai, edita via IA
(ou fallback), gera **nova versão** com linhagem (`parent_job_id`, `versao`) e registra em
`versoes.jsonl`. Pipeline extraído em `_run_pipeline()` (compartilhado por gerar e editar).

### 7. Catálogo ampliado — `catalogo/camadas.json`
Adicionadas camadas **INCRA** (acervo fundiário i3geo): SIGEF particular/público MT, SNCI
particular MT, Assentamentos. Endpoints reais (o SIGEF particular vem do script de referência).

### 8. Marca IMAP — `templates/marca/`
Logos oficiais (`imap_logo_claro.png`, `imap_logo_escuro.png` — tom claro/escuro, 8334²) +
versões enxutas 900px (`imap_logo.png` p/ faixa branca, `imap_logo_claro_trim.png`).
No MapSpec: `marca.logo` = caminho do PNG.

## Formatos de entrada
Já suportados em `core/geo.py`: `.zip`, `.shp`, `.geojson`/`.json`, `.kml`, `.kmz`.
**Novo:** GeoTIFF (`.tif`/`.tiff`) como **raster de fundo** via `core/raster.py`.
**PDF** = mapa-modelo para a IA analisar/reproduzir o padrão (referência de estilo, decisão
do usuário) — não é importado como geometria.

## Como testar

```powershell
$py = "C:\Users\Usuario\AppData\Local\Programs\Python\Python311\python.exe"
$env:PYTHONPATH = "C:\GIS\NexoGeo-Ambiental"
& $py -m pytest tests -q          # 25 passed
```

Geração com IA (chave em `secrets.local.json` da análise):
```json
{ "nexomap_ai_provider": "deepseek", "deepseek_api_key": "...", "nexomap_deepseek_model": "deepseek-v4-pro" }
```

## Critérios de aceite atendidos
- Mapa real de teste com **PDF, preview PNG, PNG de validação, GeoJSON e `resultado.json`** ✓
  (via `generate()` — job em `Resultados/Mapas_IA/<job_id>/`).
- Validação: não-branco, sem sobreposição de elementos, sem texto cortado, imagem/camadas ✓.
- Prancha de comparação referência × gerado produzida ✓.
- `pytest` (25 passed) ✓.
- Loop DeepSeek real: gerar MapSpec + editar "remova o título preto" (`titulo_caixa=false`) ✓.

## Pendências / próximos passos
- Wire dos novos campos no `schema/mapspec.schema.json`, `exemplos/` e na UI (`ui/src/App.jsx`),
  incluindo endpoint de edição versionada e `npm run build`.
- Fetch de camadas i3geo/INCRA (SIGEF) hoje espera WFS-JSON; pode precisar de caminho GML.
- Inset de localização em vetor (MT + município) em vez de tiles.
- Arquétipo "AIR × SIGEF" (painel analítico) como segundo template pronto.
