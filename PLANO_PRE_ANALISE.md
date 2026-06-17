# Plano — Aba de Pré-Análise por Shapefile (.zip)

> **Status:** planejamento. Documento de plano + checklist para um novo módulo do software.
> **Não altera código** — guia para o desenvolvimento posterior.
> Complementa [`PLANO_SOFTWARE.md`](PLANO_SOFTWARE.md) (visão geral) e [`DESENVOLVIMENTO.md`](DESENVOLVIMENTO.md).

## 1. Objetivo

Uma **aba "Pré-Análise"** no sistema onde o usuário **importa um `.zip` contendo o shapefile
da área** (o `.shp` pode ter **um ou mais polígonos**, sem causar bug). A partir desse perímetro,
o sistema **gera automaticamente um Word de pré-análise** com o **máximo de dados possível**,
no formato do modelo [`Análise_de_area_1_pamera.docx`](../Análise_de_area_1_pamera.docx),
consultando os **WMS/WFS da SEMA-MT e demais fontes oficiais**, **baixando** recibos do SIMCAR e
APFs (como já é feito hoje), e dando **atenção especial a embargos, autos de infração e
desembargos** pela delicadeza jurídica do tema.

**Fora do escopo inicial:** a análise de **matrículas/dominialidade de cartório** (tabela de
proprietários, CRI/CNS, área de matrícula) — entra como preenchimento manual/placeholder.

---

## 2. Estrutura do documento de saída (espelha o modelo)

O modelo `Análise_de_area_1_pamera.docx` define as seções que a pré-análise deve produzir:

| # | Seção | Conteúdo | Origem dos dados |
|---|---|---|---|
| 1 | **DOMINIALIDADE** | Empreendimentos, município, tabela de proprietários (matrícula/CPF-CNPJ/área), registro (CRI/CNS), "Área total" certificação × matrícula | *Parcial:* proprietário vem do CAR; matrícula/CRI/CNS = **manual** (fora do escopo) |
| 2 | **CONTEXTO FUNDIÁRIO** | Nº de certificações INCRA (SIGEF/SNCI) por fazenda, código, data, averbação; **Sobreposições** | INCRA Acervo Fundiário *(já implementado: `ctx_fundiario`)* |
| 3 | **CONTEXTO AMBIENTAL (CAR)** | Por imóvel: nº CAR, proprietário, "Dados das Áreas dos Imóveis Rurais" (do recibo), situação, APF; **Sobreposições** | SEMA WFS + recibo SIMCAR + APF *(já implementado: `ctx_ambiental`)* |
| 4 | **ÁREAS PROTEGIDAS** | Terras Indígenas (sobreposição/divisa) e Unidades de Conservação (sobreposição/distância em km) | FUNAI (TI) + ICMBio/SEMA (UC) |
| 5 | **INFRAÇÕES, PENALIDADES E TACs** | TACs (consulta por CNPJ/CPF); **Embargos / Autos de Infração / Desembargos** (órgão, nome, CPF, dano, nº auto, termo de embargo, processo, área) | IBAMA (SISCOM/PAMGIA) + SEMA SIGA + consulta TAC ⚠️ |
| 6 | **ALERTAS** | MapBiomas Alertas (código, ano, área, observação) e Alertas SIGA-SEMA por ano (com figuras) | MapBiomas Alerta + SEMA SIGA |

> Os "Sobreposições" de cada seção e as proximidades das Áreas Protegidas são **cálculos
> geométricos** (interseção / distância) entre o perímetro importado e cada camada.

---

## 3. Fontes WMS/WFS por seção (com campos úteis das tabelas de atributos)

Levantadas dos MXDs do projeto (inclui `Arquivos Pamera/Lauri.mxd`) e do modelo. Catálogo base
em [`catalogo/servicos_geo.json`](catalogo/servicos_geo.json).

| Fonte | Endpoint | Camadas/temas | Atributos-chave a extrair |
|---|---|---|---|
| **SEMA-MT** (GeoServer) | `geo.sema.mt.gov.br/geoserver/ows` (authkey) | CAR (`MVW_REQUERIMENTO_ATP`), embargos/SIGA, autos de infração, áreas desembargadas, alertas SIGA, UC estadual, tipologia, APP/RL | nº estadual, **protocolo/recibo (id p/ SIMCAR)**, situação, proprietários; embargo: autuado, CPF/CNPJ, auto, processo, área, dano |
| **INCRA** Acervo Fundiário | `acervofundiario.incra.gov.br/i3geo/ogc.php` | SIGEF / SNCI | parcela_codigo, data, registro_matricula, qtd_area_peca_tecnica |
| **IBAMA** SISCOM | `siscom.ibama.gov.br/geoserver/publica/wms` | `publica:vw_brasil_adm_embargo_a` | nome/autuado, CPF/CNPJ, auto de infração, processo, área embargada |
| **IBAMA** PAMGIA (ArcGIS) | `pamgia.ibama.gov.br/server/services/01_Publicacoes_Bases/adm_embargos_ibama_a/MapServer` | embargos (REST/WMS) | idem — fonte alternativa/cruzamento |
| **FUNAI** | `geoserver.funai.gov.br/geoserver/ows` | Terras Indígenas | nome da TI, fase, sobreposição/distância |
| **ICMBio / SEMA** | (a definir — WFS ICMBio nacional + UC estadual SEMA) | Unidades de Conservação | nome da UC, esfera, distância em km |
| **MapBiomas Alerta** | `production.alerta.mapbiomas.org/geoserver/ows` | alertas de desmatamento | código do alerta, ano, área, fonte |
| **INPE** TerraBrasilis | `terrabrasilis.dpi.inpe.br/geoserver/prodes-legal-amz/wms` | PRODES (contexto histórico, opcional) | ano, área |
| **Planet / Google** | tiles | basemap p/ as **figuras** dos mapas | (geração de figuras = fase de mapas, v2) |

> **"demais WMS úteis":** priorizar os que têm **tabela de atributos rica** — embargos IBAMA,
> embargos/autos SEMA-SIGA, MapBiomas Alerta e FUNAI. UC nacional (ICMBio) precisa ser
> confirmada como serviço (endpoint a definir).

---

## 4. Importação do shapefile `.zip` (robustez com 1+ polígonos)

Fluxo previsto (reusa `core/geo`, que já lê `.prj` e une multipolígonos):

1. Receber o `.zip` (upload na aba) → extrair em pasta temporária.
2. Localizar o conjunto `.shp/.shx/.dbf/.prj` (procurar recursivamente; aceitar nomes quaisquer).
3. Ler com `pyshp` (encoding `latin-1` com fallback). **Suportar N polígonos** no mesmo shape:
   - manter cada feição individualmente **e** a **união** (perímetro geral) para consultas;
   - corrigir geometrias inválidas (`buffer(0)`), ignorar feições nulas.
4. Detectar CRS pelo `.prj`; se ausente, **perguntar/assumir** (4674) e avisar.
5. Reprojetar conforme a consulta: **UTM** (áreas) e **lon/lat 4326/4674** (WMS/WFS, bbox).
6. Calcular **bbox** + **buffer** (para "distância até UC" e "divisa com TI").
7. Validar e resumir (nº de polígonos, área total, CRS) antes de rodar.

**Casos a blindar (sem bug):** múltiplos polígonos; `.prj` ausente/!= esperado; multipart/holes;
encoding; `.shp` dentro de subpasta do zip; zip com arquivos extras.

---

## 5. Downloads (recibos SIMCAR + APFs)

- **Recibo do CAR (SIMCAR):** para cada CAR que intersecta a área, ler na camada SEMA
  `MVW_REQUERIMENTO_ATP` o **código/protocolo/id** (o "simcar em análise/não analisado"); usar esse
  id no portal **https://simcar-2hpta2.manus.space/** ("Download Recibo SIMCAR") para baixar o PDF.
  - ⚠️ **Análise do Portal SIMCAR (SPA em React):** O portal não expõe o PDF de forma estática. Abordagens propostas:
    1. **Prioridade (API Direta):** Fazer engenharia reversa das requisições (aba Network do navegador) e recriar a chamada (ex: `POST`/`GET`) diretamente para o endpoint interno usando back-end (`core/clients/simcar_api.py`).
    2. **Fallback (Scraping Headless):** Caso a API utilize tokens dinâmicos, CAPTCHA ou requeira contexto de navegador, utilizar Playwright ou Selenium (`core/clients/simcar_scraper.py`) para rodar em background, preencher o ID e capturar o PDF.
  - Depois, extrair "Dados das Áreas dos Imóveis Rurais" *(parser já existe: `core/recibo`)*.
- **APFs:** consulta + download das REGULAR *(já existe: `core/clients/apf_rural` + `automations/apf`)*.
- **Padrão de salvamento:** igual ao atual — recibos em `Consultas_Publicas/CAR/`, APFs em
  `Consultas_Publicas/APF/` (e TACs em `Consultas_Publicas/Consultas_TACs/`).

---

## 6. ⚠️ Atenção especial — embargos, autos de infração, desembargos e TACs

Tema **delicado** (dados pessoais e jurídicos: nomes, CPFs, processos, autuações). Regras:

1. **Fonte estritamente oficial e rastreável** — só IBAMA (SISCOM/PAMGIA) e SEMA-SIGA; registrar
   **fonte + data da consulta + nº do processo/auto** em cada item.
2. **Critério de vínculo duplo** — considerar um auto/embargo relacionado quando houver
   **interseção espacial** com a área **e/ou** correspondência por **CPF/CNPJ** do(s) titular(es)
   do CAR. Marcar claramente o critério que ligou cada registro.
3. **Não concluir "nada consta" de forma absoluta** — usar "**Nada consta nas fontes consultadas
   (X, Y) em DD/MM/AAAA**", distinguindo ausência de registro de "situação regular".
4. **Revisão humana obrigatória** — esta seção sai marcada como **"requer conferência"**; o sistema
   não deve publicar como definitiva sem confirmação do analista.
5. **Sem inferência/expansão** — não deduzir dano, área ou autoria além do que o atributo oficial
   traz; campos faltantes ficam como "não informado".
6. **Aviso de responsabilidade** no rodapé da seção (uso interno/pré-análise, sujeito a verificação).

---

## 7. Encaixe na arquitetura atual (Organização de Pastas)

A estrutura do módulo ficará organizada da seguinte forma, reaproveitando o núcleo existente:

- **`tmp/shapefiles_uploads/`** — Pasta temporária volátil para extração dos `.zip` recebidos via upload. **Requisito crítico:** Rotina de limpeza (garbage collection) após a geração do relatório para não sobrecarregar o disco do servidor.
- **`Consultas_Publicas/`** — Armazenamento persistente das evidências em PDF coletadas nas consultas (ex: subpastas `/CAR`, `/APF`).
- **`core/geo/`** — Motor geográfico: script `importar_shape.py` (leitura `.zip` e união de geometrias) e `overlay.py` (cálculos de interseção e distância para áreas protegidas/embargos).
- **`core/clients/`** — Módulos de comunicação com serviços externos: `funai.py`, `ibama.py` (SISCOM/PAMGIA), `mapbiomas.py`, `icmbio.py` (UC), e o extrator `simcar_api.py` (ou `simcar_scraper.py`).
- **`core/llm/deepseek.py`** — Módulo de Inteligência Artificial para processamento de dados e textos:
  - **DeepSeek v4 Flash:** Recebe o texto extraído dos PDFs (CAR e APF) e extrai perfeitamente as tabelas de "Dados das Áreas dos Imóveis Rurais" em formato JSON, evitando a fragilidade de leitores e parsers tradicionais.
  - **DeepSeek v4 Pro:** Recebe dados brutos de Termos de Embargo e Autos de Infração (Seção 5), analisa juridicamente o cruzamento e gera um resumo claro e preciso para o Word.
- **`core/docx_builder/`** — Responsável por ler o modelo base (`Análise_de_area_1_pamera.docx`) e injetar os dados gerados pela análise (inclusive os textos resumidos pelo LLM).
- **`automations/pre_analise.py`** — Orquestrador principal da rotina (seções 1 a 6).
- **API**: endpoint de upload do `.zip` + execução (progresso via SSE).
- **UI**: aba **"Pré-Análise"** — área de upload (arrastar `.zip`), resumo do shape importado, botão "Gerar pré-análise", progresso e botão final de download do Word.
- **Catálogo**: estender `catalogo/servicos_geo.json` com os WFS da FUNAI/ICMBio e atributos.

> As **figuras de mapa** (Alertas SIGA, Dinâmica) dependem de renderização cartográfica — ficam
> para a **fase de mapas (v2)**; na v1 da pré-análise, entram como **placeholders** ("Figura N").

---

## 8. Riscos e questões abertas

- **Portal SIMCAR (recibo):** SPA — endpoint/params do download a descobrir (inspeção de rede).
- **Esquemas de atributos** variam por camada (cada WMS tem nomes próprios) → precisa de um
  **mapa de campos por camada** (à semelhança do `mapa_campos` do CAR).
- **UC nacional (ICMBio):** confirmar o serviço WFS e o cálculo de **distância em km**.
- **Precisão embargos/autos:** risco de falso-positivo/negativo → daí a revisão humana obrigatória.
- **Disponibilidade/limites** dos serviços gov. (timeouts, quedas) → degradar com aviso, nunca quebrar.
- **Credenciais:** `sema_authkey` (CAR/embargos SEMA) via `secrets.local.json`; Planet (figuras, v2).
- **Dominialidade/matrículas:** sem fonte automática → seção sai parcial (placeholder p/ o analista).

---

## 9. CHECKLIST

### A. Importação do shapefile `.zip`
- [ ] Upload do `.zip` na aba e extração em pasta temporária
- [ ] Localizar `.shp/.shx/.dbf/.prj` (busca recursiva; nomes quaisquer)
- [ ] Ler com `pyshp`; suportar **1+ polígonos** (feições individuais **e** união)
- [ ] Corrigir geometria inválida (`buffer(0)`) e ignorar feições nulas
- [ ] Detectar CRS pelo `.prj`; tratar ausência (avisar/assumir 4674)
- [ ] Calcular bbox + buffer; resumo (nº polígonos, área, CRS) antes de rodar
- [ ] Testes com: 1 polígono, vários polígonos, sem `.prj`, multipart/holes, zip com subpastas

### B. Clientes de dados (WMS/WFS) + mapa de campos
- [ ] `core/overlay` — interseção (sim/não, área, %) e **distância** perímetro × camada
- [ ] Cliente FUNAI (Terras Indígenas) + sobreposição/divisa
- [ ] Cliente UC (ICMBio nacional e/ou UC estadual SEMA) + **distância em km**
- [ ] Cliente IBAMA embargos (SISCOM e PAMGIA) — atributos do auto/embargo
- [ ] Cliente SEMA-SIGA — embargos, autos de infração, desembargos, alertas
- [ ] Cliente MapBiomas Alerta — código/ano/área/observação
- [ ] Consulta de **TACs** por CPF/CNPJ (definir fonte)
- [ ] **Mapa de campos por camada** (nomes de atributos por serviço)
- [ ] Estender `catalogo/servicos_geo.json` (FUNAI, ICMBio, SIMCAR, campos)

### C. Downloads Automáticos e Extração por IA
- [ ] Extrair **id/protocolo do CAR** da camada SEMA `MVW_REQUERIMENTO_ATP`
- [ ] Implementar o download automático dos recibos (SPA SIMCAR API/Headless)
- [ ] Salvar recibos PDF baixados na pasta `Consultas_Publicas/CAR/`
- [ ] Consulta e download automático das APFs (REGULAR) → `Consultas_Publicas/APF/`
- [ ] Ler texto sujo/OCR dos PDFs baixados
- [ ] Acionar o **DeepSeek v4 Flash** enviando o texto dos PDFs para extrair os dados tabulares do Imóvel Rural como JSON estruturado.
- [ ] Acionar o **DeepSeek v4 Pro** para revisar e construir o texto descritivo dos embargos/autos de infração (Seção 5).

### D. Geração do documento (`automations/pre_analise.py`)
- [ ] Seção 1 — Dominialidade (proprietário do CAR; matrícula/CRI/CNS = placeholder manual)
- [ ] Seção 2 — Contexto Fundiário (reusar `ctx_fundiario`) + Sobreposições
- [ ] Seção 3 — Contexto Ambiental/CAR (reusar `ctx_ambiental`) + Sobreposições
- [ ] Seção 4 — Áreas Protegidas (TI: sobreposição/divisa; UC: distância km)
- [ ] Seção 5 — Infrações/Embargos/Autos/Desembargos/TACs **(com as regras do §6)**
- [ ] Seção 6 — Alertas (MapBiomas + SIGA; figuras como placeholder na v1)
- [ ] Estilo no padrão do modelo (Tahoma, bullets, filetes) via `core/docx_builder`
- [ ] Nota de fonte/data por seção; rodapé de responsabilidade na Seção 5

### E. ⚠️ Embargos/autos — salvaguardas (§6)
- [ ] Fonte + data + nº processo/auto em cada item
- [ ] Vínculo por **interseção espacial e/ou CPF/CNPJ** (registrar o critério)
- [ ] Texto "Nada consta nas fontes consultadas (…) em DD/MM/AAAA" (não absoluto)
- [ ] Marca **"requer conferência"** + aviso de responsabilidade
- [ ] Sem inferência além do atributo oficial (campos faltantes = "não informado")

### F. API + UI
- [ ] Endpoint de upload do `.zip` + validação + resumo do shape
- [ ] Endpoint de execução da pré-análise (progresso via SSE)
- [ ] Aba **"Pré-Análise"** na UI (drag-and-drop do `.zip`, resumo, "Gerar", progresso, download)

### G. Robustez e testes
- [ ] Degradação graciosa por serviço fora do ar (avisar, não quebrar)
- [ ] Teste ponta a ponta com a área atual (Querência) comparando ao `Análise_de_area_1_pamera.docx`
- [ ] Conferência manual da seção de embargos/autos no teste

---

*Próximo passo sugerido:* aprovar este plano, então (1) investigar o endpoint do portal SIMCAR e
(2) começar por `core/importar_shape` + `core/overlay`, que destravam todas as seções.
