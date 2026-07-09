# Diário de Desenvolvimento — Software de Análise de Área

Registro cronológico do desenvolvimento. Complementa [`PLANO_SOFTWARE.md`](PLANO_SOFTWARE.md)
(visão/roadmap) e [`README.md`](README.md) (como usar). Datas em AAAA-MM-DD.

---

## Princípios travados

1. **Software genérico, zero dado de imóvel embutido.** Nada de nome de fazenda, CAR, CRS ou
   campo de `.dbf` escrito no código. Tudo vem do `projeto.json` da análise.
2. **Projeto vive com os dados**, não dentro do `nexogeo/`. O `nexogeo/` só traz código,
   schema e exemplos.
3. **I/O único** em `<projeto>/Resultados`.
4. **Segredos fora do código e do Git** (`secrets.local.json` na pasta da análise).
5. **Tudo documentado** à medida que avança (este diário + docstrings + README).

---

## 2026-06-17 — Fase 0 (fundação) ✓

- Esqueleto do repositório `nexogeo/` criado.
- `core/config.py`: esquema do `projeto.json` (dataclasses, **stdlib puro**) + `load_projeto()`
  com validação (campos obrigatórios, ids de fazenda únicos, versão de schema) e derivados
  (`data_consulta_efetiva`, `raiz_abs`, `caminho`).
- `schema/projeto.schema.json`: JSON Schema (draft-07) documentando o formato.
- `catalogo/servicos_geo.json`: inventário dos 9 serviços WMS/WFS extraídos dos MXDs
  (SEMA-MT, INCRA, IBAMA SISCOM/PAMGIA, INPE PRODES, MapBiomas, FUNAI, Planet, Google).
- `exemplos/`: `projeto.template.json` (placeholders, sem dado real) + `secrets.example.json`.

**Verificação:** `python -m core.config ..\projeto.json` → schema válido, 4 pastas de dados
resolvidas `[ok]`, 5 shapefiles de CAR encontrados `[ok]`, matrículas somando corretamente.

> Correção de rumo aplicada: o `projeto.json` da Querência saiu de dentro do `nexogeo/`
> (era dado embutido) e foi para a **raiz da análise** (`../projeto.json`, com `raiz_dados="."`).

## 2026-06-17 — Fase 1 (núcleo) — em andamento

- `core/geo.py` ✓
  - `crs_do_prj()` lê o `.prj` de cada shape e devolve o `CRS`.
  - Reprojeção **automática por shape** para o `crs_utm` do projeto — não se assume mais
    qual camada está em graus e qual em UTM (era o ponto frágil dos scripts antigos).
  - `carregar_cars(projeto)`: polígono unido (em UTM) + atributos do CAR de cada fazenda;
    `Car.attr()` lê o `.dbf` por nome lógico via `mapa_campos`.
  - `atribuir(cars, shp, dst, limiar=0.5)`: atribui cada polígono ao CAR de maior
    sobreposição; área pelo atributo (`Area`/`AREA`) com fallback para a geometria.
- `core/io.py` ✓: `garantir_dir`, `caminho_resultado`, `caminho_consulta`.
- `core/xlsx_builder.py` ✓: cores institucionais, cabeçalho azul, total verde, zebra e larguras
  (estilo que estava copiado em 3–4 scripts).

**Verificação do `core.geo`:** quantitativos de área cultivável por fazenda reproduzidos a
partir do `Area_Cultivavel.shp`, sem nada hardcoded — total **2799,1316 ha**, 0 polígonos
não atribuídos. Áreas dos CARs batem com o `AREA_HA` do `.dbf` (ex.: Espírito Santo 1231,58 ha).

## 2026-06-17 — Fase 2 (automações) — em andamento

### Correção de modelo: matrícula ≠ CAR

A visão de **registro (matrícula)** não bate 1:1 com a visão **espacial (CAR)**: por exemplo,
"Gabriela V e VI" é 1 CAR mas 2 matrículas (6482/6483), e "Gabriela II e III" é 1 CAR mas 2
matrículas (7932/7933). Modelagem ajustada:
- `fazendas[]` = visão espacial (1 por CAR) — perdeu o campo `matriculas` (era inferência minha).
- novo bloco **`area_total.itens[]`** = visão de registro, fiel ao antigo `gerar_area_total.py`.
  É a fonte da automação de área total.
- `core/config.py` passou a expor `projeto.area_total`; `schema/` e `exemplos/` atualizados.

> Rótulo da matrícula **6350**: é a **Fazenda Gabriela II** (CAR 70), confirmado pelo usuário.
> (Houve um vaivém — chegou a ser registrada como "Gabriela I" e foi corrigida.)

### `automations/quantitativos.py` ✓

Primeira automação ponta-a-ponta. Reproduz as 3 abas do `gerar_quantitativos.py`
(Quantitativos, Detalhe da Área Cultivável, Detalhe CAR), 100% a partir do `projeto.json`,
usando `core.geo` + `core.xlsx_builder` + `core.io`.

**Verificação:** gerado para arquivo temporário (sem tocar no `Resultados/` existente),
reaberto e conferido — 3 abas, total cultivável **2799,1316 ha**, e a aba Detalhe CAR lendo
`car_federal` / módulos / proprietários do `.dbf` via `mapa_campos`.

### `core/normalize.py`, `core/docx_builder.py`, `automations/area_total.py` ✓

- `core/normalize.py` ✓: números/datas BR (`br`, `br_data`, `casas_decimais`). As funções de
  nome (Title Case + conectores) e máscara CNPJ/CPF entram com o contexto ambiental.
- `core/docx_builder.py` ✓: documento base Tahoma, numeração multinível (• / o / ▪), filete
  inferior — estilo que estava copiado em 3 scripts.
- `automations/area_total.py` ✓: gera o bloco "Área total" (certificação × matrícula) a partir
  do `area_total.itens`.

**Verificação:** gerado para arquivo temporário, reaberto com python-docx — 7 itens, números no
padrão BR (ex.: `1.230,7372 ha`), e a matrícula 6350 saindo como **Fazenda Gabriela II** (valida
a correção de modelo de ponta a ponta).

### Clientes web + 3 automações restantes ✓ — Fase 2 concluída

- `core/normalize.py` parte 2 ✓: `nome` (Title Case + conectores), `mascara_cnpj`, `proprietarios`.
- `core/recibo.py` ✓: parser do recibo PDF (PyMuPDF) — testado contra os 5 PDFs reais.
- `core/secrets.py` ✓: carrega `secrets.local.json` (ao lado do projeto.json / na raiz de dados).
- `core/clients/` ✓: `http` (sessão única, TLS/timeout), `sema` (situação do CAR via WFS),
  `incra` (SIGEF/SNCI via GML), `apf_rural` (raspagem ASP.NET do APF Rural).
- `automations/ctx_ambiental.py` ✓ — SEMA + recibo + APF; **degrada** sem rede/authkey.
- `automations/ctx_fundiario.py` ✓ — INCRA SIGEF/SNCI por interseção > 50%.
- `automations/apf.py` ✓ — consulta + planilha (+ download opcional dos PDFs REGULAR).

**Verificação AO VIVO** (authkey passada de forma transitória e removida depois):
- ctx_ambiental: situação real por fazenda (ex.: "Aguardando análise", "Validado"), proprietários
  formatados e APF REGULAR da planilha (ex.: nº 520/2023).
- ctx_fundiario: 7 certificações SIGEF/SNCI do INCRA, com código, data (BR) e averbação.
- apf: Espírito Santo retornou 2 (Federal) + 3 (Estadual) APFs; planilha montada ok.
- normalize/recibo/secrets verificados offline (recibo contra os 5 PDFs reais).

> **Marco:** as 5 automações do v1 rodam genéricas e verificadas. **Fase 2 concluída.**

## 2026-06-17 — Fase 4 (backend + interface) ✓

### Backend `api/` (FastAPI) ✓
- `api/registry.py` — registro das 5 automações (metadados + função `gerar`).
- `api/app.py` — endpoints: `/api/health`, `/api/projeto/validar`, `/api/automacoes`,
  `/api/run` (SSE: started/done/error/complete por automação, via `asyncio.to_thread`),
  `/api/resultados`, `/api/abrir` (`os.startfile`). Serve `ui/dist` na raiz quando existe.

**Verificação (TestClient, em processo, não-destrutiva):** health, listagem, validação do
projeto e `/api/run` com SSE rodando `area_total` num `Resultados/` temporário; depois `/`
servindo o index buildado e o bundle JS (200).

### Frontend `ui/` (React + Vite + Tailwind v4) ✓
- Vite + React 18 + Tailwind v4 (`@tailwindcss/vite`), cor de marca `#1F4E79`.
- `src/App.jsx` — carrega o projeto por caminho, cartões de automação selecionáveis,
  "Rodar selecionadas" com progresso ao vivo (lê o stream SSE), lista de resultados com
  "abrir". Responsivo (sidebar em telas md+, grade 1/2/3 colunas), tema claro/escuro.
- `npm install` (79 pacotes) + `npm run build` → `dist/` (CSS 14 KB, JS 152 KB / 49 KB gzip).

### Shell `app.py` (pywebview) ✓
- Sobe uvicorn (servindo API + UI) e abre a janela; sem pywebview, instrui a abrir no navegador.

> **Marco:** v1 funcional ponta a ponta — projeto → seleção → execução com progresso → resultados,
> backend + UI integrados e verificados.

### Próximo — Fase 7 (empacotamento) e v2

- Empacotar com PyInstaller (incluir `ui/dist` e `catalogo/`); instalar `pywebview`.
- v2: restrições/desmatamento (motor de overlay), mapa MapLibre, variantes de quantitativos
  (AUAS, com-estrada + PEF) e seleção de projeto por diálogo de arquivo na UI.

---

## 2026-07-02 - Mapas IA integrado como aba

- O NexoMap AI deixou de ser tratado como app separado e passou a ser a aba **Mapas IA**
  dentro do NexoGeo Ambiental.
- O projeto aberto pelo usuario continua sendo o `projeto.json` normal da analise; a aba cria
  automaticamente `<raiz da analise>/.nexomap/projeto.nexomap.json` por meio de
  `core.nexomap_project.ensure_project_from_analysis()`.
- Saidas de mapa ficam em `<Resultados>/Mapas_IA/<job_id>/` com `mapspec.json`, `mapa.pdf`,
  `png_validacao.png`, `validacao.json` e `resultado.json`; `mapa.mxd` depende de ArcMap e
  templates reais.
- Handoff para continuidade por outro agente: `docs/NEXOMAP_AGENT_HANDOFF.md`.

## 2026-07-08 — IA cartográfica no padrão IMAP (motor nativo)

Motor cartográfico nativo evoluído para uma IA que **cria, edita, valida e exporta** mapas no
padrão IMAP, com **layout dirigido pela IA** (nada fixo no código). Detalhes completos em
[`novas-implementacoes/2026-07-08-ia-cartografica-imap.md`](novas-implementacoes/2026-07-08-ia-cartografica-imap.md).

- **`core/raster.py` (novo):** GeoTIFF de fundo sem GDAL (`tifffile` + `Pillow`), reprojeção por
  cantos com `pyproj`, esticamento de contraste. Landsat/Planet como fundo do mapa.
- **`nexomap_renderer.py`:** grade DMS, raster local, hachuras, caixa de título, rosa-dos-ventos,
  inset "Tipologia vegetal", tabela flutuante, faixa inferior IMAP (localização/metadados-imagem/
  legenda/logo). **Cada elemento ligável/desligável via `elementos_layout`.**
- **`mapspec.py`:** campos `subtitulo`, `grade_tipo`, `raster_fundo`, `metadados_imagem`, `tabela`,
  `marca`, `versao`, `parent_job_id`; parser tolerante; edição determinística de fallback.
- **`nexomap_validation.py`:** checa imagem-presente, sem-sobreposição, sem-texto-cortado.
- **`nexomap_ai.py`:** **DeepSeek V4 Pro** como cérebro (chave em `secrets.local.json`); edição
  versionada (MapSpec = fonte de verdade, nunca PDF/PNG). "Remova o título preto" → `titulo_caixa=false`.
- **`nexomap_generator.py`:** `edit_map()` gera nova versão com linhagem; pipeline compartilhado.
- **`catalogo/camadas.json`:** camadas INCRA (SIGEF particular/público, SNCI, assentamentos).
- **`templates/marca/`:** logos oficiais IMAP.
- **Verificação:** flagship "Dinâmica 2000" reproduzido na área ATP real com Landsat 224/071 —
  10/10 checks OK; `pytest` 25 passed; loop DeepSeek gerar+editar validado ao vivo.

## 2026-07-09 — Paridade visual com o PDF-modelo IMAP (A4)

Renderer flagship calibrado **contra os PDFs reais do cliente** (série Dinâmica/Tipologia/
Embargos feitos no ArcMap, A4 paisagem) até ficar visualmente indistinguível. Guia completo:
[`docs/PADRAO_IMAP_RENDERER.md`](docs/PADRAO_IMAP_RENDERER.md).

- **Grade DMS estilo ArcMap:** rótulos sempre `g°m's"` (ex.: `52°15'0"W`), ~3 por eixo, ticks
  pretos na moldura; **sem linhas internas** por default (novo flag `grade_linhas`). Moldura preta 2.0.
- **Seta de norte ArcMap** (triângulo dividido preto/branco + "N"); rosa-dos-ventos vira opt-in.
- **Tabela padrão IMAP:** branca com grade preta, cabeçalho (2 linhas, altura 1.7×) e linha
  TOTAL em negrito, 1ª coluna mais larga — substitui o estilo web (cabeçalho azul + zebra).
- **METADADOS IMAGEM** centralizado com acentos (Satélite/Órbita/Ponto/Data/Datum), sem escala.
- **Minimapa de municípios (novo):** malhas municipais do IBGE (cache `~/.nexogeo/malhas/`),
  município do projeto em laranja rotulado, caixinha da UF, retângulo vermelho no imóvel +
  linha-guia até a moldura. Fallback para tiles sem internet.
- **Defaults IMAP no flagship:** sem barra de escala, sem rodapé "Fontes:", `inset_tipologia`
  desligado (tudo religável via `elementos_layout`). Caixa de título com borda preta.
- **Template novo `dinamica_a4_paisagem`** (297×210) — o padrão do cliente é A4; o teste rodava
  em A3 e abria demais o enquadramento. `NICE_SCALES` ganhou 20k/30k/40k (Lauri sai 1:20.000,
  modelo ≈1:22.000).
- **Estilos oficiais** propagados (script exemplo, `projeto.json` do lauri_teste, prompt do
  agente): lotes `#c00000`/`#00b0f0` 2.8, AVN `xxx` verde vazada, AC magenta vazada, AUAS `///`
  laranja; legenda dos lotes como retângulo vazado (swatch respeita `largura`).
- **Edição via chat validada ao vivo** (DeepSeek): "muda a cor da atp para amarelo" →
  `editar_camada` + `editar_legenda` + `validar_mapa` → nova versão do job com linhagem.
- **Verificação:** série completa regenerada (Dinâmica/Uso Consolidado/Tipologia) a 1:20.000;
  comparação lado a lado com o PDF-modelo; `pytest` 117 passed, 9 skipped.

## Pendências/decisões registradas

- **Matrícula 6350 (817,0640 ha)** — **Resolvido (2026-06-17):** é da *Fazenda Gabriela II*
  (CAR 70), confirmado pelo usuário. Fica no bloco `area_total` (visão de registro).
- **`pef_total_forcado` (2939,0992)**: mantido como campo **opcional** do projeto, explicitando
  o ajuste manual herdado. Quando ausente, usar o quantitativo espacial real do PEF.
- **Credenciais expostas** nos MXDs/scripts (authkey SEMA, api_key Planet): migrar para
  `secrets.local.json`; nunca reintroduzir no código.
