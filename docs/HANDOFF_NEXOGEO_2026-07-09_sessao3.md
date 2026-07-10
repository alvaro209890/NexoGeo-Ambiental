# HANDOFF — NexoGeo-Ambiental (2026-07-09, sessão 3)

Continuação do [HANDOFF sessão 2](HANDOFF_NEXOGEO_2026-07-09_sessao2.md). Foco desta
sessão: **os mapas gerados pela aba web "Mapas por CAR" divergiam dos PDFs-modelo IMAP**
versionados no último commit (`referencias/pdf_modelo_imap/`). Commit desta sessão:
**`f056b88`** (pushado no `main`). Suíte: **117 testes offline passando, 9 skip de rede**.

---

## Diagnóstico (por que divergia)

A calibração de paridade IMAP (commits `87a7e1c`/`987d5a8`) foi feita **nos scripts de
exemplo** (`projetos/lauri_teste/gerar_*.py`), que montam o MapSpec à mão. O fluxo real
da web (card + nº do CAR) monta o MapSpec por **outro caminho**:

```
ui (CarMapaView) → POST /api/nexomap/car-mapa
  → core/nexomap_generator.gerar_mapa_por_car[_stream]
    → core/nexomap_modelos.aplicar_modelo   ← ainda no padrão ANTIGO
      + catalogo/modelos_mapas.json          ← estilos web (Tailwind), ids crus
```

Resultado: A3 em vez de A4, `escala_grafica: true` forçado (o default flagship é off,
mas o spec explícito vence), cores web nas camadas, tabela com `simcar_avn` cru,
títulos sem acento — e dois bugs independentes (mojibake no rótulo e minimapa com
"Mato Grosso" placeholder).

## O que foi corrigido (arquivo a arquivo)

### `core/nexomap_modelos.py`
- `LAYOUT_PAISAGEM = "dinamica_a4_paisagem"` (era `dinamica_a3_paisagem`; A4 é o padrão
  do cliente — A3 abria demais o enquadramento).
- `elementos_layout` **não força mais `escala_grafica: True`** — vale o default flagship
  (off, como no modelo). Regra geral: só colocar chave em `elementos_layout` quando se
  quer FUGIR do default do renderer.
- Perímetro fallback: `#c00000` largura 2.8 (era `#ff2d00` 2.6).

### `catalogo/modelos_mapas.json` (todos os 7 cards)
- Estilos = paleta oficial IMAP (`docs/PADRAO_IMAP_RENDERER.md`):
  perímetro `#c00000` 2.8; AVN hachura `xxx` `#00b050` vazada 0.7; AC/uso consolidado
  contorno magenta `#ff00ff` vazado 1.6; AUAS `///` `#ffa500` vazada 0.7; ARL `\\`
  verde-escuro; APP `|||` azul; embargos/autos vazados com hachura.
- Títulos com acento ("CAR do Imóvel", "Dinâmica do Desmatamento", …).
- `tabela.config.classes` virou `[{rotulo, camada}]` → a tabela imprime
  "Vegetação Nativa (AVN)" em vez de `simcar_avn` (o resolver
  `core/nexomap_quantitativos.py` já aceitava dicts; bastou usar).

### `core/geo.py` — fim do mojibake ("FAZENDA ARUANÃ�")
- Causa: `_reader` tentava **latin-1 primeiro**, que decodifica qualquer byte (nunca
  falha) — o `.dbf` UTF-8 escrito pelo fluxo CAR virava `Ã` + caractere de controle.
  Além disso o try/except era inútil: **o pyshp só decodifica ao ler `records()`**,
  não no construtor.
- Fix: novo `_codec_cpg()` lê o sidecar `.cpg`; `_reader` tenta
  `.cpg → utf-8 → cp1252 → latin-1` **forçando `r.records()`** em cada tentativa.
- Os leitores legados (`ler_geometria`, `carregar_cars` com `encoding="latin-1"`)
  ficaram como estavam — são para shapefiles da era ArcMap.

### `core/nexomap_car.py`
- `escrever_area_zip` agora grava `area.cpg` = `UTF-8` no zip (pyshp escreve UTF-8).
- Novo `codigo_ibge_do_car(busca)`: código IBGE (7 dígitos) do município do imóvel —
  propriedades `MUNICIPIO_CODIGO`/`COD_IBGE`/… ou **extraído do CAR federal**
  (`MT-<ibge7>-<hash>`).
- Novo `municipio_por_codigo(cod)`: nome/UF pela API de localidades do IBGE, com cache
  em `~/.nexogeo/malhas/municipios_meta.json` (mesma pasta das malhas do minimapa).
  **GOTCHA: a API do IBGE devolve gzip mesmo sem `Accept-Encoding`** — detectar o magic
  `\x1f\x8b` e descomprimir, senão o `json.loads` falha silenciosamente.

### `core/nexomap_generator.py`
- `_preparar_area_por_car` preenche `project.municipio` (nome/uf/ibge) a partir do CAR
  antes do `project.save()` → o minimapa destaca e **rotula o município real**
  (validado: MT117775/2017 → Ribeirão Cascalheira). Antes ficava o placeholder do
  `projeto.json` ("Mato Grosso"), que só acertava o destaque por fallback de centroide
  e errava o rótulo.

### `core/nexomap_renderer.py`
- Título da tabela desenhado **depois** da tabela, colado no topo real dela (bbox);
  antes ficava em `y=1.03` do eixo e flutuava solto quando a tabela era menor que o
  eixo. Com `colunas_grupos`, sobe +0.10 para não colidir com os rótulos de grupo.
- Legenda do perímetro: swatch = **retângulo vazado** (`patches.Patch`, igual ArcMap),
  não linha; rótulo "Perímetro do imóvel" com acentos.

### `catalogo/camadas.json`
- 17 nomes de exibição acentuados ("Vegetação Nativa - SIMCAR digital (AVN)", "Terras
  Indígenas FUNAI", …). Só docstrings referenciavam os nomes antigos — nada quebra.

### `core/nexomap_ai.py`
- System prompt do agente recomenda `dinamica_a4_paisagem` (dizia A3).

## Verificação

- Série completa dos 7 cards regenerada ao vivo
  (`.venv/bin/python projetos/car_web/rodar_serie_car.py "MT117775/2017"`) — 7/7 ok.
- Comparação visual com o gabarito (`referencias/pdf_modelo_imap/README.md`, checklist
  de 7 itens): grade DMS sem linhas, caixa de título branca/borda preta, seta ArcMap,
  perímetro `#c00000` com rótulo branco/halo, tabela branca com Total em negrito e
  nomes amigáveis, faixa inferior completa (minimapa com município real, METADADOS
  IMAGEM, legenda com retângulos vazados, logo IMAP), sem escala e sem "Fontes:".
- `pytest tests -q` → 117 passed, 9 skipped.

## Pendências conhecidas (inalteradas, ver PADRAO_IMAP_RENDERER.md)

- Fundo PLANET real (hoje Esri World Imagery; com `planet_api_key` fica idêntico).
- Tipologia Vegetal com fundo WMS SEMA (Radam) em vez de satélite+hachura.
- "Data da imagem" sai "-" quando não informada no request.
- `projetos/car_web/projeto.json` é **estado runtime** (reescrito a cada busca de CAR:
  area_base, crs_utm e agora município) — não commitar essas mudanças.
