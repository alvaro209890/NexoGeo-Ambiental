# HANDOFF — Implementação dos planos da IA cartográfica (2026-07-08)

Documento de passagem para o próximo agente continuar a implementação dos planos
de `planos/` (roadmap fases A→E do `planos/README.md`). **Leia este arquivo
inteiro antes de tocar no código.**

## Decisões do usuário (Álvaro) — válidas para todo o trabalho

1. **Escopo**: implementar TODOS os planos (fases A→E na ordem do roadmap).
2. **Git**: um commit por fase concluída (suite verde), **push direto no `main`**
   de `alvaro209890/NexoGeo-Ambiental` (repo PÚBLICO — cuidado com segredos).
3. **Testes live**: usar a chave DeepSeek de `secrets.local.json` para todos os
   testes ao vivo; pesquisar os WMS da SEMA e fazer a IA usar corretamente as
   bases do **CAR digital** (feito, ver abaixo).
4. **Decisões abertas dos planos**: seguir a opção recomendada/v1 de cada plano.
5. **MXDs**: têm credenciais embutidas → **NUNCA commitá-los** (repo público).
   Ficam em `templates/mxd/` (gitignored). Só o PDF-modelo foi para o Git
   (`referencias/Mapas_unidos.pdf`). Decisão confirmada pelo usuário.

## Segredos (gitignored, já criado)

`secrets.local.json` na **raiz do repo** contém (extraídos dos MXDs + fornecido
pelo usuário): `deepseek_api_key`, `sema_authkey`,
`planet_api_key` (PLAK…, atual) e `planet_api_key_alt` (hex, antiga).
`core/secrets.py` procura o arquivo ao lado do `projeto.json` da análise — os
testes live copiam/derivam dele via env vars. **Nunca** colocar chave em código,
teste ou commit.

## Estado por fase

### Fase A — CONCLUÍDA e pushada (commit `0be6a67`)
Planos 01 (posição por elemento) e 02 (legenda editável):
- `core/nexomap_layout.py` (novo): âncoras `top|center|bottom` × `left|center|right`
  + prefixo `in-map-*` (relativo ao quadro do mapa); `resolve_rect` com clamping e
  aviso; `element_rect` / `element_text_anchor` (fallback = defaults atuais).
- `MapSpec` ganhou campos opcionais `layout` (`{"elementos": {id: {ancora,x,y,largura,altura[,estilo]}}}`)
  e `legenda` (`{modo, titulo, itens[], colunas, fonte_tamanho, posicao}`); ambos
  preservados na edição versionada (`spec_edit_from_prompt`).
- Renderer: todo o mobiliário (flagship e standard) consulta `layout.elementos`;
  título aceita `estilo {fundo, cor, tamanho}` → **caixa branca topo-centro é o
  padrão IMAP recente** (ver PDF-modelo); `_montar_legenda` resolve modos
  `auto`/`manual`/`misto` (itens vinculados a camada via `camada` herdam estilo +
  contagem); detecção de sobreposição agora compara os elementos do mobiliário
  entre si (`_layout_report` com `element_regions`).
- Prompt do sistema (`nexomap_ai._system_prompt`) documenta ids/âncoras/legenda.
- Testes: `tests/test_layout.py`, `tests/test_legenda.py`.

### Fase B — CONCLUÍDA e pushada (commit `471db80`)
Plano 00 (tools/function calling):
- `core/nexomap_tools.py` (novo): 16 tools + `TOOL_SCHEMAS` (formato OpenAI);
  cada tool é função pura `tool(spec_dict, ctx, **args) -> (spec_novo, msg)`;
  erro de argumento vira `"erro: …"` devolvido à IA (nunca derruba o loop).
- `core/nexomap_agent.py` (novo): `run_tool_loop` (limite de passos + timeout,
  provedor injetável p/ mock) e `run_rule_based` (fallback determinístico com
  `apply_rule_based_edit` registrado como pseudo-tool_call).
- `nexomap_ai.run_tools()`: chamada real com `tools`/`tool_choice:"auto"`,
  `thinking` desligado. **CONFIRMADO AO VIVO: DeepSeek V4 Pro suporta function
  calling** (risco do plano 00 resolvido).
- `nexomap_generator.chat_tools(project_path, prompt, parent_job_id=None)`:
  gera (IA chama `criar_mapa`) ou edita versão (linhagem `parent_job_id`/`versao`);
  registra tool_calls no `chat_history.jsonl` (entrada `modo: "tools"`), no
  `versoes.jsonl` e no `resultado.json` (`tool_calls`, `resumo`).
- Testes: `tests/test_tools.py` (19: unit + loop mock) e
  `tests/live/test_deepseek_tools.py` (**1 passed ao vivo**: pediu embargos SEMA +
  legenda no rodapé → tools corretas + PDF renderizado).
- Pendência do plano 00: endpoint `POST /api/nexomap/chat-tools` (é do plano 05).

### Fase C — EM ANDAMENTO (working tree NÃO commitado!)

**Plano 03 quase pronto; plano 04 nem começado.** Mudanças não commitadas:
`catalogo/camadas.json`, `core/mapspec.py`, `core/nexomap_catalog.py`,
`core/nexomap_generator.py`, `core/nexomap_layers.py`, `core/nexomap_renderer.py`,
`tests/test_layers.py` (novo), `tests/net/test_layers_net.py` (novo).

O que já foi implementado (plano 03):
- **Pesquisa ao vivo da SEMA (2026-07-08)**: GetCapabilities WFS de
  `https://geo.sema.mt.gov.br/geoserver/ows` com authkey → **135 camadas**.
  XML salvo no scratchpad da sessão (refazer se precisar:
  `curl "https://geo.sema.mt.gov.br/geoserver/ows?service=WFS&version=2.0.0&request=GetCapabilities&authkey=$AUTH"`).
- **CAR digital mapeado**: família `Geoportal:CAR_*` = CAR **validado**
  (`CAR_ATP`, `CAR_APP`, `CAR_APPD`, `CAR_APPRL`, `CAR_ARL`, `CAR_AVN`,
  `CAR_AUAS`, `CAR_AU`, `CAR_NASCENTE`) e família `Geoportal:SIMCAR_D_*` =
  temas **declarados** do SIMCAR digital (APP por faixa de módulos fiscais,
  rios por largura, veredas, tipologia etc.). `MVW_REQUERIMENTO_ATP` =
  requerimentos. **WFS JSON do CAR_ATP testado ao vivo: retorna polígonos.**
- **Bugs de catálogo achados e corrigidos** no `camadas.json`:
  - `tipologia_sema` apontava para `Geoportal:TIPOLOGIA`, **que NÃO existe** no
    GeoServer → corrigido para `Geoportal:SIMCAR_D_TIPOLOGIA_VEGETAL`.
  - `snci_particular_mt` usava tema `certificada_snci_particular_mt` → corrigido
    para `imoveiscertificados_privado_mt` (conforme `servicos_geo.json`).
  - INCRA: endpoints `http://` davam **301** → trocados para `https://` e tipo
    `wfs_gml` (o acervo devolve GML em EPSG:4326; campo novo `epsg: 4326` por
    camada é respeitado no fetch).
- **camadas.json reescrito**: + `car_atp/app/appd/arl/avn/auas/nascentes`,
  `embargos_siga`, `desembargos_sema`, `autos_siga`, `embargos_ibama_siscom`
  (tipo `wms_raster`), `alertas_mapbiomas_simpl`; TODAS as camadas com campo
  `descricao` (vai à IA via `public_context`, atualizado em `nexomap_catalog.py`).
- **`nexomap_layers.py`**: parser GML próprio (`gml_para_geojson`, tolera
  `coordinates` e `posList`, namespaces `ms:`), `wfs_gml` fetch, `wms_raster`
  (GetMap PNG por bbox reprojetado p/ UTM → `DrawnLayer.image`/`image_extent`),
  **cache local por (id, bbox)** via `cache_dir` (generator passa
  `<mapas_dir>/.cache`; rede falhou + cache existe → usa cache com aviso),
  `rotulo_atributo` por camada (ex.: `parcela_codigo` no SIGEF).
- **Renderer**: desenha camadas raster com `imshow` + opacidade do estilo;
  `_label_features` rotula feições (amarelo IMAP) quando `rotulo: true`.
- **`mapspec.py`**: fallback de embargo também adiciona `embargos_siga`.
- Testes escritos: `tests/test_layers.py` (offline: parser GML fixture, URL
  GetMap, auth ausente→aviso, cache, integridade do catálogo) e
  `tests/net/test_layers_net.py` (rede, skip sem `NEXO_NET=1`).

**Descobertas de rede (importantes):**
- SEMA WFS JSON: OK com authkey (a authkey extraída dos MXDs funciona).
- INCRA acervo: só via **https**; GML com `gml:featureMember`/`gml:coordinates`
  e atributos `ms:*` (`parcela_codigo`, `situacao_informada`…). Testado ao vivo: 6 feições.
- IBAMA **PAMGIA REST: OK** (GeoJSON, testado ao vivo) — fonte primária de embargos.
- IBAMA **SISCOM WMS: 403 Cloudflare** para clientes não-navegador (mesmo com
  UA de browser). A camada `embargos_ibama_siscom` fica no catálogo com
  degradação graciosa (aviso, nunca quebra); o teste de rede aceita ambos os
  resultados. Pode funcionar de IP residencial BR/navegador.
- bbox de teste com dados reais: `(-52.30, -12.60, -52.10, -12.45)` (Querência/MT),
  UTM 31982 — tem CARs, embargos e parcelas SIGEF.

**PRÓXIMO PASSO IMEDIATO (era o que ia rodar quando o trabalho parou):**
```bash
cd /home/acer/Documentos/NexoGeo-Ambiental
.venv/bin/python -m pytest tests -q          # suite offline (test_layers.py NUNCA foi rodado!)
NEXO_NET=1 SEMA_AUTHKEY=$(python3 -c "import json; print(json.load(open('secrets.local.json'))['sema_authkey'])") \
  .venv/bin/python -m pytest tests/net -q    # testes de rede
```
Corrigir o que falhar (código novo de camadas ainda sem nenhuma execução de teste).

Depois, ainda na Fase C:
1. **Plano 04 (tabelas calculadas)** — nada feito. Criar
   `core/nexomap_quantitativos.py` (área por classe via shapely/overlay, recorte
   pela area_base, m²→ha, %, linha total), resolver `tabela.fonte:
   "quantitativos"|"sigef_sobreposicao"` no pipeline ANTES do render (gravar as
   `linhas` calculadas no MapSpec resolvido), cabeçalho multinível
   (`colunas_grupos`) no `_draw_table`, formatação BR via `core/normalize.br`,
   e `tests/test_quantitativos.py`. A tool `criar_tabela` já aceita
   `fonte`/`config` e só armazena — falta o motor que resolve.
2. Marcar checkboxes dos planos 03/04 (com data), commit único da Fase C, push.

### Fase D — NÃO INICIADA
- **Plano 05**: schema (`schema/mapspec.schema.json` sem os campos novos:
  `subtitulo, grade_tipo, raster_fundo, metadados_imagem, tabela, marca, versao,
  parent_job_id, layout, legenda`), exemplos, endpoints `POST /api/nexomap/edit`
  (chama `nexomap_generator.edit_map`, SSE), `GET /api/nexomap/versoes`,
  `POST /api/nexomap/chat-tools` (chama `chat_tools`), UI `MapsAiView` em
  `ui/src/App.jsx` (botão Editar, timeline de versões, seletor de raster),
  `cd ui && npm run build`. GOTCHA: node do PC é 18 — Vite pode exigir ≥20
  (`nvm use`, ver memória do Ares).
- **Plano 06**: novos checks (`area_visivel`, `camadas_desenhadas`,
  `grade_presente`, `escala_coerente`, `legenda_presente`, `rotulos_legiveis`),
  severidade erro/aviso + `sugestao` (tool+args) por falha, loop de
  auto-correção com o agente (limite 2 tentativas). O renderer já computa
  `regioes_elementos` — dá para passar bounds da área ao validador.
- **Plano 07**: fixtures (`tests/fixtures/`: shape 1 km², geojson, gml,
  raster_min.tif), mover o GML fixture inline de `test_layers.py` para arquivo,
  `tests/test_visual.py`, `tests/test_raster.py`, documentar comando único.
  Convenções JÁ adotadas: rede = `NEXO_NET=1` (tests/net/), live =
  `DEEPSEEK_API_KEY` (tests/live/).

### Fase E — NÃO INICIADA
- **Plano 08**: provedores `planet` (usar `planet_api_key` do secrets; URL em
  `servicos_geo.json`: `tiles.planet.com/basemaps/v1/planet-tiles/{mosaic}/gmap/{z}/{x}/{y}.png`,
  mosaico mensal casa com a data da imagem) e `google` (xyz `lyrs=s`, opção
  explícita) em `core/basemap.py`; `basemap_config` no MapSpec; ordem
  `raster_fundo > basemap > neutro`; `core/nexomap_modelo.py` (PDF-modelo →
  resumo de estilo p/ prompt — usar `referencias/Mapas_unidos.pdf` como caso real).
- Ao final: atualizar `DESENVOLVIMENTO.md` + resumo em `novas-implementacoes/`
  com data, marcar checkboxes, commit, push.

## Referências visuais (novas nesta sessão)

- `referencias/Mapas_unidos.pdf` (commitado): 24 mapas IMAP reais — padrão a
  reproduzir: título em **caixa branca topo-centro**, faixa inferior
  [minimapa | METADADOS IMAGEM | Legenda | logo IMAP], rótulos de feição
  amarelos, perímetros azul/vermelho, N simples no canto sup. direito.
- `templates/mxd/*.mxd` (4 arquivos, LOCAIS, gitignored): Alertas_MAPBIOMAS_2,
  Dinamica_2008, Dinamica_2019, Embargos_IBAMA — úteis para consultar
  simbologia/serviços via `strings -el` (strings UTF-16). CONTÊM CREDENCIAIS.

## Gotchas de ambiente

- venv: `.venv/` (Python 3.12, pytest instalado). Rodar SEMPRE da raiz do repo.
- Suite estava **68 passed** antes das mudanças da Fase C (não commitadas).
- Testes de renderer usam `basemap: none`/`use_basemap=False` (sem rede).
- `tests/test_legenda.py` importa `_write_project` de `tests/test_layout.py`.
- `core/clients/http.py`: `verify=False` (TLS gov quebrado) — os fetches novos
  de camadas usam esse cliente.
- O plano 07 cita caminhos Windows (`C:\GIS\...`) — este checkout Linux usa
  `.venv/bin/python -m pytest tests -q`.
