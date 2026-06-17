# Plano de Desenvolvimento — Software de Análise de Área

> Documento de planejamento para transformar as automações de análise fundiária/ambiental
> (hoje scripts soltos em `Automacoes/Scripts/`) em um **programa Windows** reutilizável,
> dirigido por configuração, capaz de rodar várias análises para vários imóveis.
> Complementa [`ANALISE_TECNICA.md`](ANALISE_TECNICA.md) (auditoria dos scripts) e
> [`AUTOMACOES.md`](AUTOMACOES.md) (guia de execução).

**Status:** decisões de stack/escopo fechadas (ver §12) — iniciando a **Fase 0** (fundação).

---

## 1. Objetivo

Um aplicativo de desktop (Windows) com **interface moderna, bonita e responsiva** onde o
analista:

1. cria um **projeto** (= uma análise de um imóvel/cliente) preenchendo um formulário;
2. importa os shapes do CAR e os recibos;
3. marca quais automações rodar (quantitativos, contextos, APF, restrições, mapas);
4. acompanha o progresso e abre os resultados (`.xlsx`/`.docx`/`.pdf`) — tudo de dentro do app.

A regra de ouro: **o que muda entre análises é só o projeto (configuração) — nunca o código.**

---

## 2. Inventário de serviços geoespaciais (WMS / WFS / tiles)

Extraído dos 30 arquivos `.mxd` do projeto (raiz + `MXD/` + `MXD/claude/`). Estes são os
serviços que o software precisa consumir — **WFS** para *análise* (extrair feições e cruzar
com o perímetro) e **WMS/XYZ/WMTS** para *visualização* (render do mapa na tela e nas figuras).

| # | Provedor | Tema / camadas | Endpoint base | Tipo | Auth | Uso na automação |
|---|---|---|---|---|---|---|
| 1 | **SEMA-MT** (GeoServer) | CAR (`MVW_REQUERIMENTO_ATP`), embargos SEMA/SIGA, autos de infração, áreas desembargadas, APP/RL, tipologia | `https://geo.sema.mt.gov.br/geoserver/ows` | WMS + WFS | **authkey** | Situação do CAR + restrições estaduais + render |
| 2 | **INCRA** Acervo Fundiário | SIGEF (`certificada_sigef_particular_mt`), SNCI (`imoveiscertificados_privado_mt`) | `http://acervofundiario.incra.gov.br/i3geo/ogc.php?tema=…` | WFS (GML) | não | Certificações (já em uso) |
| 3 | **IBAMA** SISCOM | Embargos federais (`publica:vw_brasil_adm_embargo_a`) | `http://siscom.ibama.gov.br/geoserver/publica/wms` | WMS (+WFS) | não | Sobreposição embargos IBAMA |
| 4 | **IBAMA** PAMGIA | Embargos (ArcGIS Server `adm_embargos_ibama_a`) | `https://pamgia.ibama.gov.br/server/services/01_Publicacoes_Bases/adm_embargos_ibama_a/MapServer/WMSServer` | WMS (ArcGIS) | não | Fonte alternativa de embargos IBAMA |
| 5 | **INPE** TerraBrasilis | PRODES desmatamento (`prodes-legal-amz`) | `http://terrabrasilis.dpi.inpe.br/geoserver/prodes-legal-amz/wms` | WMS (+WFS) | não | Desmatamento histórico (Amazônia Legal) |
| 6 | **MapBiomas** Alerta | Alertas de desmatamento | `https://production.alerta.mapbiomas.org/geoserver/ows` | WMS + WFS | não | Alertas recentes sobre o imóvel |
| 7 | **FUNAI** (GeoServer) | Terras Indígenas | `https://geoserver.funai.gov.br/geoserver/ows` | WMS + WFS | não | Sobreposição com TI |
| 8 | **Planet** Basemaps | Mosaicos mensais de satélite (`global_monthly_AAAA_MM_mosaic`) | `https://tiles.planet.com/basemaps/v1/planet-tiles/…/{TileMatrix}/{TileCol}/{TileRow}.png` | WMTS / XYZ | **api_key** | Imagem de fundo da série temporal "Dinâmica" |
| 9 | **Google** Satellite | Basemap de satélite | `http://mt0.google.com/vt/lyrs=s&x={col}&y={row}&z={level}` | XYZ | não | Basemap de referência |

### Camadas temáticas que cada MXD revela (viram automações de "restrição/sobreposição")

Os MXDs deixam claro que a análise vai **muito além** do que os scripts atuais cobrem. Cada
tema abaixo é uma verificação de sobreposição entre o perímetro de cada fazenda e uma camada
oficial — exatamente a mesma mecânica do `gerar_contexto_fundiario.py` (interseção > 50% / ou
qualquer interseção, conforme o caso):

- **Embargos** — IBAMA (SISCOM/PAMGIA) e SEMA/SIGA → o imóvel tem área embargada?
- **Autos de infração** (SEMA-MT) → existe auto incidindo no imóvel?
- **Áreas desembargadas** (SEMA-MT) → histórico de desembargo.
- **Terras Indígenas** (FUNAI) → sobreposição com TI.
- **Unidades de Conservação** → sobreposição com UC (camada SEMA-MT / federal).
- **Desmatamento PRODES** (INPE) e **Alertas MapBiomas** → supressão de vegetação por ano.
- **Tipologia / vegetação** → enquadramento da cobertura.
- **Dinâmica temporal** (imagens Planet/CBERS/Landsat) → série de imagens por ano para as figuras.

> **Insight de arquitetura:** todas essas verificações compartilham um mesmo motor —
> *“baixa feições de um serviço por bbox do imóvel → cruza com cada fazenda → reporta
> sobreposição (sim/não, área, %)”*. No software isso vira **um único módulo genérico de
> sobreposição** (`core/overlay`) parametrizado por uma lista de "camadas de restrição",
> e cada tema acima é só uma entrada de configuração (endpoint + nome da camada + tipo).

### ⚠️ Credenciais expostas (tratar antes de distribuir)

Embutidas em texto claro nos `.mxd` (e no script do contexto ambiental):

- **SEMA authkey:** `541085de-…` (também hardcoded em `gerar_contexto_ambiental.py`).
- **Planet api_key:** dois valores distintos (`PLAK11beb…` e `8e928c25…`).

No software essas chaves **não podem ficar no código nem versionadas**. Vão para um arquivo
de segredos local (fora do Git) ou para o cofre do projeto, e a UI deve permitir editá-las.

---

## 3. Catálogo de automações do software

Consolidação das que já existem + as novas implícitas nos MXDs. Todas passam a ler do
**projeto** (config), sem nada hardcoded.

| Grupo | Automação | Origem | Status | Saída |
|---|---|---|---|---|
| **Quantitativos** | Área cultivável / AUAS / PEF por CAR | shapes locais | existe (refatorar) | `.xlsx` |
| **Contexto ambiental** | Situação CAR + APF + áreas do recibo | SEMA WFS + recibo PDF | existe | `.docx` |
| **Contexto fundiário** | Certificações SIGEF/SNCI | INCRA WFS | existe (corrigir paths) | `.docx` |
| **Área total** | Certificação × matrícula | config (matrículas) | existe | `.docx` |
| **APF** | Consulta + download dos PDFs | SEMA (scraping) | existe (tirar path abs.) | `.xlsx` + PDFs |
| **Restrições** *(novo)* | Embargos, autos, TI, UC, desembargos | IBAMA, FUNAI, SEMA | **novo** | `.docx`/`.xlsx` |
| **Desmatamento** *(novo)* | PRODES + alertas MapBiomas por ano | INPE, MapBiomas | **novo** | `.docx`/`.xlsx` |
| **Mapas** | Figuras temáticas + série "Dinâmica" | WMS/tiles + shapes | hoje ArcGIS | `.png`/`.pdf` (ver §7) |

---

## 4. Arquitetura (config-driven, em camadas)

Mesma estrutura do estudo já apresentado:

```
Interface (GUI)  →  Automações (orquestram)  →  Núcleo (lib reutilizável)  →  Dados
                         ▲
                    Projeto (config .json)  ← parametriza tudo
```

- **Núcleo (`core/`)** — biblioteca sem nada específico de imóvel:
  - `geo` — reprojeção (UTM por região) + atribuição/sobreposição espacial.
  - `overlay` — motor genérico de cruzamento perímetro × camada de restrição.
  - `clients/` — `sema`, `incra`, `ibama`, `funai`, `inpe`, `mapbiomas`, `planet` (WFS/WMS).
  - `recibo` — parser do recibo PDF do CAR (PyMuPDF).
  - `docx_builder` / `xlsx_builder` — estilo padronizado (hoje copiado em 3–4 scripts).
  - `normalize` — nomes (Title Case, conectores), CNPJ/CPF, datas BR.
  - `io` — convenção única de pastas e gravação em `Resultados/`.
- **Automações (`automations/`)** — cada uma é um orquestrador fino que recebe o projeto.
- **Projeto (`projeto.json`)** — a única coisa que muda entre análises (ver §6).
- **Backend de serviço (`api/`)** — expõe as automações para a interface (ver §5).
- **Interface (`ui/`)** — front moderno (ver §5 e §8).

---

## 5. Stack tecnológica recomendada

Para atender "**bonita, moderna e responsiva**", a UI deve ser construída com tecnologia web
(HTML/CSS/JS) — é o que entrega o visual mais moderno e layout responsivo — com o **Python
existente** rodando por baixo (não reescrevemos a lógica geoespacial).

| Camada | Recomendação | Por quê | Alternativa |
|---|---|---|---|
| Lógica/automações | **Python 3** (o atual) | já existe, libs geo maduras | — |
| Backend local | **FastAPI** + uvicorn | expõe automações como API local, com progresso (WebSocket/SSE) | Flask |
| Frontend | **React + Vite + TailwindCSS** + biblioteca de componentes (shadcn/ui) | visual moderno, responsivo, rápido | Vue, ou HTML+Tailwind+Alpine (mais simples) |
| Mapa interativo | **MapLibre GL JS** | consome os WMS/XYZ do §2 num mapa bonito e fluido | Leaflet |
| Shell desktop | **pywebview** (usa o WebView2 do Windows) | leve, empacota o front como app nativo | **Tauri** (shell Rust, ainda mais leve) ou Electron (mais pesado) |
| Empacotamento | **PyInstaller** → instalador único `.exe` | usuário não instala Python | Briefcase / MSIX |

**Pilha primária sugerida:** `FastAPI + React/Tailwind + MapLibre`, embrulhado em **pywebview**,
distribuído via **PyInstaller**. Mantém todo o backend em Python e entrega uma interface de
nível profissional.

> ⚠️ **ArcGIS continua à parte.** O `conformar_mxd_dinamica.py` depende de ArcPy (Python 2.7
> do ArcMap 10.8) e **não entra no `.exe`**. Ver §7 para a estratégia de mapas.

---

## 6. Esquema do projeto (`projeto.json`)

A peça mais importante. Rascunho do formato (a detalhar na Fase 1):

```jsonc
{
  "imovel": "Fazendas Gabriela/Espírito Santo",
  "cliente": "—",
  "municipio": { "nome": "Querência", "uf": "MT", "ibge": "5107065" },
  "crs_utm": 31982,                 // fuso UTM da região (aqui 22S)
  "data_consulta": "auto",          // "auto" = data de execução
  "pastas": {                       // relativas à raiz do projeto
    "shapes": "Shapes", "car": "Shapes/CAR",
    "consultas": "Consultas_Publicas", "resultados": "Automacoes/Resultados"
  },
  "fazendas": [
    {
      "id": "esp_santo",
      "nome": "Fazenda Espírito Santo",
      "shape_car": "CAR_ATP (69)",
      "car_federal": "MT-5107065-9491FC2FD8F247C58D512512B479987B",
      "car_estadual": "MT29241/2017",
      "recibo_pdf": "recibo_FAZENDA_ESPIRITO_SANTO.pdf",
      "matriculas": [
        { "numero": "5298", "area_ha": 556.7785 },
        { "numero": "5299", "area_ha": 6.5449 },
        { "numero": "5300", "area_ha": 667.4198 }
      ]
    }
    // … demais fazendas
  ],
  "mapa_campos": {                  // nomes das colunas do .dbf do CAR
    "area_ha": "AREA_HA", "num_estadual": "NUMEROESTA",
    "proprietarios": "NOMESPROPR", "car_federal": "CAR_FEDERA"
  },
  "camadas_restricao": [           // alimenta o motor genérico de sobreposição
    { "tema": "Embargos IBAMA", "provedor": "ibama_siscom",
      "layer": "publica:vw_brasil_adm_embargo_a", "tipo": "wfs" },
    { "tema": "Terras Indígenas", "provedor": "funai", "layer": "…", "tipo": "wfs" },
    { "tema": "Embargos SEMA", "provedor": "sema", "layer": "…", "tipo": "wfs" }
    // … autos, UC, desembargos, PRODES, MapBiomas
  ],
  "automacoes": ["quantitativos", "ctx_ambiental", "ctx_fundiario",
                 "area_total", "apf", "restricoes", "desmatamento"]
}
```

Segredos (authkey SEMA, api_key Planet) ficam **fora** deste arquivo, em `secrets.local.json`
não versionado.

---

## 7. Estratégia de mapas (a parte mais delicada)

Três caminhos possíveis para as figuras cartográficas; decidir antes da Fase 4:

1. **Manter ArcGIS (curto prazo).** O software só orquestra: detecta o Python do ArcMap e
   dispara `conformar_mxd_dinamica.py` por fora. Menor esforço, mas continua dependendo do
   ArcMap instalado e do Python 2.7.
2. **Migrar para ArcGIS Pro (médio prazo).** ArcPy em Python 3 — empacotável junto, mas exige
   licença Pro e reescrever o script de layout.
3. **Render próprio sem ArcGIS (alvo ideal).** Gerar as figuras dentro do app com os WMS/tiles
   do §2 — via mapa MapLibre (export PNG) no front, ou via `matplotlib`/`contextily`/`cartopy`
   no Python. Elimina a dependência ArcGIS e casa com a "interface bonita". Maior esforço.

**Recomendação:** começar pelo caminho 1 (orquestrar o ArcGIS atual) para não travar o resto,
e evoluir para o caminho 3 como meta — primeiro um **mapa interativo na tela** (MapLibre
consumindo os WMS), depois o export das figuras padronizadas.

---

## 8. Interface — diretrizes de UI/UX

Telas principais:

1. **Início / Projetos** — lista de análises recentes, botão "Novo projeto", "Abrir".
2. **Projeto** — formulário do `projeto.json` (dados do imóvel, fazendas, camadas), com
   importação dos shapes/recibos por arrastar-e-soltar.
3. **Mapa** — mapa interativo (MapLibre) com o perímetro das fazendas + camadas de restrição
   ligáveis (embargos, TI, UC, desmatamento) e basemaps (Planet/Google).
4. **Automações** — cartões selecionáveis, botão "Rodar selecionadas", barra de progresso e
   **log ao vivo** por automação.
5. **Resultados** — galeria dos arquivos gerados, com "abrir" e "abrir pasta".

Design system:
- Layout **responsivo** (painel lateral recolhível + área principal fluida), tema claro/escuro.
- Tipografia limpa, cantos arredondados, cores sóbrias com um tom de destaque (o azul
  institucional `#1F4E79` já usado nos relatórios é um bom acento).
- Feedback sempre visível: estados de carregando, sucesso, erro; nada de "tela congelada"
  enquanto uma consulta WFS roda (processamento assíncrono no backend).

---

## 9. Segurança e robustez

- **Credenciais** fora do código e do Git (`secrets.local.json` + `.gitignore`); UI para editar.
- **SSL:** hoje todos os scripts usam `verify=False`. Centralizar a política de TLS num cliente
  HTTP único, com retry/backoff e timeout — e tentar reativar verificação onde os servidores
  permitirem.
- **Tolerância a serviço fora do ar:** consultas externas (SEMA/INCRA/IBAMA/FUNAI/INPE) podem
  cair; cada automação deve degradar com elegância (avisar, não quebrar tudo).
- **Datas automáticas:** nunca mais digitar `DATA_CONSULTA` à mão.

---

## 10. Padronizações necessárias (pré-requisitos de qualquer fase)

Herdadas do estudo de arquitetura — são o trabalho de base:

1. Esquema do `projeto.json` (§6) — fundação de tudo.
2. **Mapa de campos** do `.dbf` do CAR (nomes de coluna podem variar por origem).
3. CRS por região (não cravar UTM 22S).
4. Identidade única por fazenda (acabar com o vínculo por índice posicional frágil).
5. I/O único gravando em `Resultados/` (hoje 4 scripts gravam em lugares diferentes).
6. Regras de normalização de nomes centralizadas.
7. Catálogo de camadas de restrição (§2) como configuração, não código.

---

## 11. Roadmap em fases

| Fase | Entrega | Depende de |
|---|---|---|
| **0. Fundação** | Esquema `projeto.json` + recriar a análise atual de Querência só com ele (prova de conceito) | §6, §10 |
| **1. Núcleo** | Extrair `core/` (geo, builders, normalize, io); scripts atuais importam dele | Fase 0 |
| **2. Automações parametrizadas** | Quantitativos, contextos, área total e APF lendo do projeto; corrigir paths/credenciais | Fase 1 |
| **3. Restrições/desmatamento** | Motor `overlay` + clientes IBAMA/FUNAI/INPE/MapBiomas; novas automações | Fase 1 |
| **4. Backend + UI** | FastAPI + React/Tailwind; telas de projeto, automações, resultados | Fases 2–3 |
| **5. Mapa interativo** | MapLibre consumindo os WMS/§2; camadas ligáveis | Fase 4 |
| **6. Mapas/figuras** | Orquestrar ArcGIS (curto prazo) → render próprio (meta) | Fase 5, §7 |
| **7. Empacotamento** | Instalador `.exe` (PyInstaller), gestão de segredos, docs | Fases 4–6 |

---

## 12. Decisões (fechadas)

| Tema | Decisão | Observação |
|---|---|---|
| **Stack da UI** | **React + Vite + TailwindCSS + MapLibre**, em **pywebview** (WebView2), empacotado com **PyInstaller**. Backend **FastAPI** (Python). | Mapa entra na UI mais tarde (mapas fora do v1), mas a stack já o suporta. |
| **Escopo do v1** | **Geradores atuais parametrizados + UI básica** (Fases 0–4): `projeto.json` + núcleo + 5 automações (quantitativos, ctx ambiental, ctx fundiário, área total, APF) + telas de projeto / rodar / resultados. | Restrições e desmatamento (Fase 3) ficam para o v2. |
| **Mapas/figuras** | **Fora do v1.** Foco em `.xlsx`/`.docx`. Estratégia cartográfica (orquestrar ArcGIS vs. render próprio) decidida depois. | Ver §7. |
| **Distribuição** | App local de máquina única (`.exe`). | — |

### Roadmap do v1 (recorte das fases)

- **Fase 0** — esquema `projeto.json` + recriar a análise de Querência só com ele (PoC).
- **Fase 1** — extrair `core/` (geo, builders, normalize, io).
- **Fase 2** — automações lendo do projeto; corrigir paths/credenciais.
- **Fase 4** — backend FastAPI + UI React/Tailwind (projeto, automações, resultados).

*(Fase 3 — restrições/desmatamento — e Fases 5–6 — mapa interativo e figuras — ficam para o v2.)*

---

*Em andamento:* **Fase 0** — esquema final do `projeto.json` + estrutura de pastas do
repositório do software (pasta `software/` na raiz do projeto, pensada para virar repositório
próprio, tendo cada análise como um "projeto" externo).
