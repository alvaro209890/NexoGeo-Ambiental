# Plano de Melhorias — NexoGeo 100% funcional (SHP + matrículas → tudo)

> **Status:** plano aprovado — o desenvolvimento **começa pelo checklist do §11** (ordem M0→M6).
> Complementa [`PLANO_SOFTWARE.md`](PLANO_SOFTWARE.md), [`PLANO_PRE_ANALISE.md`](PLANO_PRE_ANALISE.md)
> e [`DESENVOLVIMENTO.md`](DESENVOLVIMENTO.md). Criado em 02/07/2026.
>
> **Como usar:** marcar `[x]` somente com o critério de verificação do item atendido; cada
> marco fechado ganha registro no `DESENVOLVIMENTO.md` e uma tag `git` (`m1`, `m2`, …).

## 0.1 Decisões fechadas com o usuário (02/07/2026)

| Tema | Decisão | Consequência no plano |
|---|---|---|
| **Mapas/ArcGIS** | **ArcGIS agora, migrar depois.** Ponte arcpy + MXD-templates (caminho validado na Harmonia); render próprio fica como meta pós-v2. | M2/M3 como planejados; o `.exe` exige ArcMap 10.8 para a automação `mapas` (o "doctor" avisa). |
| **Matrículas** | **Entram por PDF do cartório + IA.** O usuário faz upload dos PDFs de matrícula; o DeepSeek extrai nº, denominação, proprietário, CPF/CNPJ e área; o analista **confere numa grade editável** antes de gerar (dado jurídico → conferência obrigatória). | M1 ganha o cliente de extração de matrícula; a grade da UI (M5) vira etapa de conferência/correção, não de digitação. Planilha .xlsx sai do escopo. |
| **Abrangência** | **Só Mato Grosso na v2.** Municípios de MT (minimapa IBGE), UTM 21S/22S, órgão estadual = SEMA-MT. | Sem abstração de outros estados por ora; `municipio.uf` validado como "MT". |
| **IA (DeepSeek)** | **Obrigatória.** Chave DeepSeek é pré-requisito para a pré-análise (extração de PDFs e resumo de embargos sempre via IA). | Sem chave configurada, a pré-análise **falha rápido com mensagem clara** (não degrada silenciosamente); o "doctor" e a tela Config validam a chave. |

### 0.1.1 Decisões adicionais (02/07/2026, tarde — após o NexoMap AI)

| Tema | Decisão | Consequência no plano |
|---|---|---|
| **Repo público** | O repo `alvaro209890/NexoGeo-Ambiental` está **público e assim permanece por ora** (risco assumido pelo usuário: `pre_analise.py` publicado contém matrículas/CNPJ reais da São Judas). | O M1 remove o hardcode do working tree; os dados **permanecem no histórico do git** — reavaliar visibilidade/`git filter-repo` depois. LICENSE proprietária adicionada. |
| **Série padrão × NexoMap AI** | A série padrão de mapas vira a **automação `mapas`** (determinística, sem chat), **reusando a infraestrutura NexoMap** já criada: `core/arcgis_bridge.py`, `templates/mxd/MANIFEST.json`, validação PNG, convenção de saída. A aba **Mapas IA** (chat → MapSpec → mapa avulso) continua existindo em paralelo. | M2/M3 deixam de criar a ponte do zero — **estendem** a existente (timeout/exit-124/locks, receitas por template no MANIFEST). |
| **Templates MXD fora do Git** | Os **20 MXDs** (90 MB, com authkey SEMA embutida nas camadas WMS — inviável limpar o binário nesta máquina sem o arcpy travar) **não são versionados**. `templates/mxd/*.mxd` entra no `.gitignore`; o MANIFEST (versionado) aponta para uma **pasta local de templates configurável** (secrets/app config). | Item "copiar 18 MXDs para o repo" do M2 vira "manifesto + pasta configurável"; a pasta canônica local é `MXD/claude` (agora com 20: + `Dinamica_2026_cultivo`, `PEF`). |

## 0. Meta final (definição de "pronto")

O usuário fornece **apenas duas coisas**:

1. o **shapefile da área** (`.zip`, 1+ polígonos), e
2. os **PDFs das matrículas** (a IA extrai os campos; o analista confere na grade);

e o software entrega, sem intervenção manual e sem erro:

- o **Word completo** no padrão de `Análise_de_area_Fazenda_Harmonia.docx`
  (6 seções: Dominialidade, Contexto Fundiário, Contexto Ambiental/CAR, Áreas Protegidas,
  Infrações/Penalidades/TACs, Alertas — **com as figuras dos mapas embutidas**);
- os **MXDs editados** (cópias dos templates adaptadas ao imóvel); e
- os **PDFs dos mapas** exportados (série Dinâmica + temáticos + `Mapas_unidos.pdf`).

Critério de aceite global: rodar de ponta a ponta com **um imóvel nunca visto** (não Querência,
não Harmonia) e obter Word + mapas corretos sem tocar em código.

---

## 1. Diagnóstico do estado atual

### O que já funciona
- Fundação config-driven: `projeto.json` + schema + `core/` (geo, io, builders, normalize,
  recibo, secrets, overlay) + 5 automações verificadas + `pre_analise` (930 linhas).
- Clientes web: SEMA, INCRA, IBAMA, FUNAI, MapBiomas, SCCON, APF Rural, SIMCAR, HTTP único.
- LLM (`core/llm/deepseek.py`) para extração de tabelas de PDFs e resumo de embargos.
- API FastAPI (validar/run com SSE/resultados/novo projeto/diálogos) + UI React/Tailwind
  (tema escuro, projetos recentes) + shell pywebview.
- Figuras de alertas SCCON via matplotlib (dentro da pré-análise).

### Problemas e lacunas (por gravidade)

| # | Problema | Onde | Efeito |
|---|---|---|---|
| P1 | **Dados da Querência hardcoded na pré-análise**: `DOMINIALIDADE_PADRAO` (9 matrículas da São Judas), `ORDEM_CAR` (ids esp_santo/gabriela_*), `NOME_PADRAO`/`ZIP_PADRAO` ("Fazendas_Unidas") | `automations/pre_analise.py` | Qualquer outro imóvel sai com dominialidade ERRADA — viola o princípio nº 1 do projeto |
| P2 | **Matrículas não são entrada do sistema** — a Seção 1 (Dominialidade) ficou como placeholder fixo em vez de formulário | schema/UI/pre_analise | Impossível cumprir a meta "SHP + matrículas" |
| P3 | **Módulo de mapas inexistente** — zero código de MXD/arcpy/export no software; tudo que foi feito na Harmonia foi manual (scripts em `Automacoes/Scripts/mxd_harmonia/`) | (não existe) | Sem os 19 PDFs nem as figuras do Word |
| P4 | **Word final sem figuras de mapa** — o modelo tem 18 figuras embutidas; a pré-análise só gera as figuras SCCON | `pre_analise.py` §figuras | Documento incompleto vs. modelo |
| P5 | `VERIFY_TLS = False` global; authkey SEMA e api_key Planet ainda em texto claro dentro dos MXD-modelo | `core/clients/http.py`, MXDs | Risco de segurança ao distribuir |
| P6 | Encoding/caminhos com acento: argv `mbcs` quebra com bash/uploads (`ç`, `ã`, `á`); cwd relativo se perde em subprocesso | export/adapt scripts, futura ponte ArcGIS | Erros "Invalid MXD filename" (já ocorreu em 02/07) |
| P7 | UI monolítica (`App.jsx` único), sem aba de matrículas nem de mapas; sem exibição de avisos de degradação | `ui/src` | UX incompleta p/ o fluxo-alvo |
| P8 | Sem suíte de testes; verificação é manual | repo | Regressões passam batidas |
| P9 | Templates MXD vivem na análise (`MXD/claude`, hoje 18 arquivos após limpeza manual), não no software; contêm caminhos absolutos da máquina/OneDrive | `MXD/claude` | Não portável; template pode ser editado por engano |

---

## 2. Frente A — Generalizar a pré-análise (mata P1/P2)

1. **Novo bloco `dominialidade` no `projeto.json`** (e no schema):
   ```jsonc
   "dominialidade": {
     "registro": { "cri": "<comarca>", "cns": "<nº>" },
     "matriculas": [
       { "numero": "7.569", "denominacao": "Fazenda Harmonia", "proprietario": "…",
         "cpf_cnpj": "…", "area_ha": 3823.9033 }
     ]
   }
   ```
   `DOMINIALIDADE_PADRAO`, `ORDEM_CAR`, `NOME_PADRAO` e `ZIP_PADRAO` **saem do código**;
   nome do arquivo de saída derivado de `projeto.imovel`; ordem dos CARs = ordem de
   `fazendas[]` (ou área desc. quando vier só do shape).
2. **Modo "só shape"**: quando o zip é a única entrada (sem `fazendas[]` no projeto), a
   pré-análise descobre os CARs pela camada SEMA `MVW_REQUERIMENTO_ATP` (já faz) e cria as
   fazendas dinamicamente — validar que nada mais depende de ids fixos.
3. **Extração de matrículas por PDF + IA** (decisão §0.1): upload de 1+ PDFs de matrícula →
   texto via fitz (com OCR fallback se digitalizado) → **DeepSeek** extrai
   nº/denominação/proprietário/CPF-CNPJ/área em JSON → preenche `dominialidade.matriculas`
   → **grade de conferência obrigatória** na UI antes de gerar (dado jurídico).
   Novo prompt/função em `core/llm/deepseek.py` + client de upload na API.
4. Critério de aceite: rodar a pré-análise da **Harmonia** (zip do ATP + matrículas 7.569 etc.)
   e comparar seção a seção com `Análise_de_area_Fazenda_Harmonia.docx`.

## 3. Frente B — Módulo de Mapas: editar MXD + exportar PDF (mata P3/P9)

É a maior frente. Estratégia = **caminho 1 do §7 do PLANO_SOFTWARE** (orquestrar o ArcGIS
instalado), portando para o software o que foi feito e validado manualmente na Harmonia.

### B.1 Ponte ArcGIS (`core/arcgis_bridge.py`, Python 3)
- Localiza `C:\Python27\ArcGIS10.8\python.exe` (configurável em `secrets/app config`).
- Roda os scripts arcpy **por subprocess com timeout** (o arcpy desta máquina trava em
  acesso a dados — regra documentada), tolerando exit 124 no `save()`.
- **Regras anti-P6:** sempre caminhos absolutos; argumentos via arquivo JSON temporário
  (UTF-8) em vez de argv (elimina o problema `mbcs` com `ç/ã/á`); nunca depender de cwd.
- Detecta ArcMap aberto/locks e avisa antes de rodar.

### B.2 Templates de MXD versionados (`nexogeo/templates/mxd/`)
- Copiar os **18 MXDs limpos** de `MXD/claude` (pós-limpeza manual de 02/07) para o software
  como templates canônicos: Dinâmica (8), Quantitativos, DLA, Tipologia, Alertas (3),
  Embargos (IBAMA + SEMA/SIGA), Terras Indígenas, Unidade de Conservação.
- **Generalizar antes de versionar:** remover a authkey/api_key embutidas (P5) trocando as
  camadas WMS por versões parametrizadas na hora da cópia; documentar os "homônimos"
  esperados (`Fazendas_Unidas.shp`, `SIEGEF.shp`, `Fazenda_Santa_Clara[.shp|\AUAS…]`,
  `Embargo.shp`, `air_mapbiomas/air_prodes/AIR.shp`) num `templates/mxd/MANIFEST.json`
  com a **receita por mapa** (que shapes precisa, CRS do frame, textos a editar).
- O minimapa do template é de **Vila Rica** → o manifesto marca os elementos que dependem do
  município (camada do minimapa, texto "Vila Rica", retângulo indicador) e a v1 do módulo
  suporta municípios de MT via camada `lml_municipio_a` (mesma base IBGE já usada).

### B.3 Port dos scripts validados (py2, chamados pela ponte)
Portar de `Automacoes/Scripts/mxd_harmonia/` para `nexogeo/templates/mxd/scripts/`,
parametrizados pelo JSON da ponte (nada de caminho fixo):
- `adapt_generico.py` — fusão de `adapt_dinamica.py` + `adapt_tematico.py` + `adapt_bloco2.py`:
  repontagem por `findAndReplaceWorkspacePaths`, remoção de camadas mortas
  (**teste por `os.path.exists`, nunca `isBroken` pós-repontagem**), renomeio/dedupe do
  perímetro **sem remover camadas donas de entrada de legenda** (lição da Harmonia),
  extensão por bbox (UTM ou Web Mercator conforme o frame), títulos/metadados/escala.
- `fix_minimap_rect.py` — recentrar retângulo + linha-guia (já genérico, só remover paths fixos).
- `export_pdf.py` — exporta lote a 150 dpi (nomes com acento via JSON, não argv).
- Posicionamento de linha/texto de distância TI/UC por matemática de página (como feito).

### B.4 Preparação de dados geo (Python 3, sem arcpy)
Novo `automations/mapas.py` orquestra:
1. gerar os shapes homônimos em UTM via **ogr2ogr/pyshp+pyproj** a partir do zip + shapes do
   CAR baixados (AUAS/AC/AVN/TIPOLOGIA quando existirem);
2. `calc_geo` port: áreas (ha, UTM) e **TI/UC mais próximos** (nome + distância + pontos da
   linha) com shapely — alimenta os mapas TI/UC e a Seção 4 do Word;
3. gerar a **tabela de quantitativos** (PNG via PIL — port de `gen_tabela_quantitativos.py`);
4. gerar os shapes de alertas (`AIR.shp`) a partir dos JSONs MapBiomas/SCCON (código já existe
   na pré-análise — extrair para `core/`);
5. chamar a ponte ArcGIS: adaptar cada template → exportar PDFs → juntar `Mapas_unidos.pdf`
   (PyMuPDF);
6. **validação automática**: renderizar cada PDF em PNG e checar (a) página não vazia,
   (b) retângulo do minimapa sobre o centroide esperado, (c) textos-chave presentes
   (título, escala) — os três bugs que apareceram na prática.

### B.5 Registro e API
- Nova automação `mapas` no `api/registry.py` (`rede: True`, `saida: "pdf"`), com progresso
  SSE por mapa (adaptando → exportando → validando).
- Configuração de quais mapas gerar no `projeto.json` (`"mapas": ["dinamica", "tipologia", …]`).

## 4. Frente C — Word final com figuras (mata P4)

1. `pre_analise.py` ganha etapa final **"montar figuras"**: para cada mapa exportado pela
   Frente B, converter a 1ª página do PDF em PNG (fitz, dpi ~180) e inserir na seção
   correspondente com legenda "Figura N — …" (ordem do modelo Harmonia: Dinâmicas 1-8,
   Quantitativos, DLA, Tipologia, Alertas, Embargos, TI, UC).
2. Ordem de execução no `/api/run`: `mapas` antes de `pre_analise` quando ambos marcados
   (dependência declarada no registry); sem mapas → placeholders "Figura N" (comportamento atual).
3. Aceite: diff estrutural (títulos, nº de tabelas, nº de figuras) entre o Word gerado e
   `Análise_de_area_Fazenda_Harmonia.docx`.

## 5. Frente D — UI (mata P2/P7)

1. **Refatorar `App.jsx`** em componentes (`src/components/`): Projetos, PreAnalise, Mapas,
   Resultados, Config.
2. Aba **Pré-Análise** completa: drag-drop do `.zip` → resumo do shape (nº polígonos, área,
   CRS, municípios detectados) → **upload dos PDFs de matrícula** → IA extrai → **grade de
   conferência editável** (o analista valida/corrige cada matrícula antes de prosseguir) →
   "Gerar" com progresso e avisos de degradação por seção → download do Word.
3. Aba **Mapas**: seleção dos mapas, progresso por mapa, miniaturas (PNG de validação),
   abrir PDF / pasta.
4. Config: caminhos (Python ArcGIS, ogr2ogr), edição do `secrets.local.json` (authkey SEMA,
   api_key Planet, DeepSeek) — nunca gravado no projeto.
5. Exibir claramente "requer conferência" na seção de embargos (regra do PLANO_PRE_ANALISE §6).

## 6. Frente E — Robustez e segurança (mata P5/P6)

1. TLS: política por host (tentar `verify=True`; fallback com aviso único registrado).
2. Varredura dos templates MXD para **remover credenciais** antes de versionar (P5);
   authkey/api_key injetadas em runtime (camada WMS reescrita na cópia de trabalho).
3. Encoding: proibir argv com não-ASCII nas pontes py2 (JSON UTF-8 sempre); testes com
   caminhos acentuados; normalizar saídas de subprocess (`mbcs` → utf-8).
4. Limpeza de `tmp/shapefiles_uploads/` e das cópias de trabalho de MXD após cada execução.
5. Degradação graciosa auditável: todo aviso vai para o Word (nota de rodapé da seção) e
   para a UI — nunca silencioso.

## 7. Frente F — Testes e empacotamento (mata P8)

1. **Testes rápidos (pytest)**: config/schema, normalize, recibo (PDFs reais), geo
   (área/atribuição), overlay, montagem docx (estrutura), manifesto dos templates.
2. **Teste ponta a ponta offline**: fixtures com respostas WFS gravadas (requests-mock) —
   roda no CI sem rede.
3. **Smoke test com ArcGIS** (opcional, marcado `@arcgis`): adapta 1 template e exporta 1 PDF.
4. PyInstaller: incluir `ui/dist`, `catalogo/`, `templates/mxd/` (scripts py2 vão como dados);
   verificação pós-build ("doctor": acha ArcGIS? ogr2ogr? WebView2?).
5. `.gitignore`: garantir `__pycache__/`, `ui/node_modules/`, `tmp/`, `secrets*` fora do Git.

---

## 8. Ordem de execução (fases) e critérios de aceite

| Fase | Entrega | Aceite |
|---|---|---|
| **M1** | Frente A (generalizar pré-análise + matrículas no projeto/schema) | Pré-análise da Harmonia correta só com zip + matrículas; nenhum dado de imóvel em `git grep` |
| **M2** | Frente B.1-B.2 (ponte ArcGIS + templates versionados com manifesto, sem credenciais) | Copiar template → abrir sem links quebrados nos homônimos de exemplo |
| **M3** | Frente B.3-B.5 (adapt genérico + export + validação + automação `mapas`) | Regerar os 19 PDFs da Harmonia pelo software, byte-a-byte equivalentes em conteúdo visual |
| **M4** | Frente C (Word com figuras) | Word da Harmonia com 18 figuras = modelo |
| **M5** | Frente D (UI: matrículas + mapas + config) | Fluxo completo pela UI sem tocar em arquivo na mão |
| **M6** | Frentes E + F (segurança, testes, PyInstaller) | Suíte verde; `.exe` roda a M5 numa máquina limpa (com ArcGIS) |

Regra transversal: **cada fase re-testa com a Harmonia** (dados completos e Word-modelo
disponíveis) e registra o resultado no `DESENVOLVIMENTO.md`.

## 9. Riscos principais

- **ArcGIS/arcpy**: instabilidade conhecida (hang em acesso a dados) — mitigada pela ponte
  com timeout + só `arcpy.mapping` + validação por PNG; plano B permanece o render próprio
  (matplotlib/contextily) para a série Dinâmica, já parcialmente provado nas figuras SCCON.
- **Minimapa por município**: templates são de Vila Rica; gerar minimapa correto para outro
  município exige recentrar o frame do minimapa + retângulo (a mecânica já existe no
  `fix_minimap_rect`); risco médio, tratado no manifesto (B.2).
- **Serviços governamentais fora do ar** no momento da geração dos mapas (WMS SEMA/Planet):
  detectar página em branco na validação B.4-6 e re-tentar/avisar.
- **Matrículas por IA**: extração automática do PDF pode errar em documento escaneado ruim —
  mitigada pela **grade de conferência obrigatória** (o analista valida cada campo antes de
  gerar) e por validações duras (CPF/CNPJ, área numérica). A responsabilidade final segue
  sendo do analista.
- **IA obrigatória (DeepSeek)**: API fora do ar ou sem crédito **bloqueia a pré-análise**
  (decisão consciente do §0.1) — o sistema deve dizer exatamente o quê e como resolver
  (mensagem com link da tela Config); monitorar custo por análise.

---

## 10. Preparação do repositório GitHub (fazer ANTES do M1)

> **Executado em 02/07/2026 com desvios** (ver §0.1.1): o repo existe como
> `alvaro209890/NexoGeo-Ambiental` e está **público** por decisão do usuário
> (o plano abaixo previa privado). Passos 3-5 conferidos/aplicados.

A pasta do sistema já se chama **`nexogeo/`** (renomeada de `software/` em 02/07/2026 —
o `.git` interno não é afetado pelo rename da pasta). Passos para publicar:

1. Criar o repo no GitHub: **`nexogeo`** (privado — o domínio é sensível: análises
   fundiárias/jurídicas de clientes).
2. `git remote add origin <url>` + `git push -u origin main` (renomear branch `master`→`main`
   se for o caso).
3. Conferências pré-push (na pasta `nexogeo/`):
   - `git ls-files | grep -iE "secret|authkey|apikey"` → vazio;
   - `git grep -iE "541085de|PLAK|api_key.*=" -- "*.py" "*.json"` → nenhuma credencial real
     (só `secrets.example.json` com placeholders);
   - `git ls-files | grep -E "__pycache__|node_modules|ui/dist"` → vazio (já ok em 02/07);
   - nenhum dado de imóvel real versionado (`git grep -i "harmonia\|santa clara\|são judas"`
     → apenas o hardcode do P1, que o M1 elimina).
4. Adicionar `LICENSE` (proprietária/All rights reserved) e revisar o `README.md` (já com o
   nome NexoGeo Ambiental).
5. Convenções: branches `m<N>-<frente>` (ex.: `m1-dominialidade`), commits em português no
   imperativo, PR só quando o critério de aceite do marco passar; tag `m<N>` no merge.

---

## 11. CHECKLIST DE DESENVOLVIMENTO

### M0 — Kickoff do repositório (§10)
- [x] Repo criado no GitHub (`alvaro209890/NexoGeo-Ambiental`) e `origin` configurado — **público por decisão do usuário (§0.1.1)**, não privado como planejado
- [x] Varredura de credenciais/dados de imóvel (02/07): nenhuma credencial versionada; **dados São Judas presentes no `pre_analise.py` publicado** (risco assumido; M1 remove do working tree, histórico permanece)
- [x] `LICENSE` (proprietária) + README revisado + push inicial
- [x] Tag `m0`

### M1 — Generalizar a pré-análise (Frente A → mata P1/P2)
> Em execução na branch `m1-dominialidade` (02/07/2026).
- [x] Bloco `dominialidade` no `schema/projeto.schema.json` + `core/config.py` (dataclasses) — verificado por `tests/test_matriculas.py`
- [x] `exemplos/projeto.template.json` atualizado com `dominialidade` (placeholders)
- [x] `pre_analise.py`: remover `DOMINIALIDADE_PADRAO` → ler de `projeto.dominialidade` (seção reescrita, com avisos quando faltam matrículas/CRI)
- [x] `pre_analise.py`: remover `ORDEM_CAR` → ordem de `fazendas[]`; removidos também os hacks Querência de `_coletar_fundiario`, `_coletar_alertas` (alerta fixo Gabriela III), `_legal` (ordem desembargos), `_areas_protegidas` ("QUEL") e a seção SIGA com anos fixos
- [x] `pre_analise.py`: remover `NOME_PADRAO`/`ZIP_PADRAO` → `Pre_Analise_<imovel>.docx`; zip = único `.zip` em `shapes/` (erro claro se 0 ou 2+)
- [ ] Modo "só shape": código pronto (`_fazendas_via_sema` via `MVW_REQUERIMENTO_ATP`, ordem = interseção desc.) — **falta validar contra o WFS real** (nomes de campos do imóvel)
- [x] Extração de matrícula: `core/llm/deepseek.py` ganha `extrair_matricula()` (JSON com nº/denominação/proprietário/CPF-CNPJ/área/CRI/CNS + `confianca` por campo); validadores `validar_cpf/cnpj/cpf_cnpj` e `numero_br` em `core/normalize.py` com testes
- [x] Endpoints `/api/matriculas/extrair` (PDFs → fitz + OCR fallback → IA → lista p/ grade, com `conferir[]` por item) e `/api/dominialidade/salvar` (grava o conferido no projeto.json com validações duras) — `core/matriculas.py`
- [x] IA obrigatória (§0.1): `gerar()` falha rápido sem `deepseek_api_key`/`DEEPSEEK_API_KEY` com mensagem apontando a tela Config; `--sem-ia` removido do CLI; `usar_ia` da API ignorado (deprecated)
- [x] Validação de escopo: `municipio.uf` ≠ "MT" → `ProjetoError` claro na carga (teste unitário)
- [x] **Verificação:** `git grep -iE "sao judas|esp_santo|gabriela|fazendas_unidas" automations core api` → vazio (inclusive docstrings com CNPJ real removidas de `normalize.py`)
- [ ] **Aceite M1:** pré-análise da Harmonia (zip ATP + matrículas) confere com `Análise_de_area_Fazenda_Harmonia.docx` seções 1-3 — requer `projeto.json` da Harmonia + chaves reais (DeepSeek/SEMA); rodar com o usuário; tag `m1` no aceite

### M2 — Ponte ArcGIS + templates MXD (Frente B.1-B.2 → mata P9, prepara P3)
> Base já existente (NexoMap AI, 02/07): `core/arcgis_bridge.py` (subprocess + JSON UTF-8 via
> env var + doctor) e `templates/mxd/MANIFEST.json`. O M2 **estende** essa base — não recriar.
- [ ] Estender `core/arcgis_bridge.py`: exit 124 tolerado no `save()` (arcpy trava — verificar `os.path.exists` da saída), detecção de `*.lock`/ArcMap aberto, timeout configurável por script
- [ ] "Doctor" da ponte via CLI: `python -m core.arcgis_bridge --check` informa ArcGIS/ogr2ogr achados (hoje só existe via API `/api/nexomap/doctor`)
- [ ] Templates **fora do Git** (§0.1.1): `templates/mxd/*.mxd` no `.gitignore`; pasta local de templates configurável (`mxd_templates_dir` em secrets/app config; padrão = `MXD/claude` da análise 4, hoje com 20 MXDs)
- [ ] Injeção de credenciais em runtime na cópia de trabalho (authkey SEMA nas camadas WMS fica no binário local; nunca versionada)
- [ ] `templates/mxd/MANIFEST.json` real: substituir os 2 placeholders pelos **20 mapas** → shapes homônimos exigidos, CRS do frame, textos/títulos editáveis, elementos do minimapa, dependências (tabela PNG, AIR.shp, distâncias TI/UC)
- [ ] **Aceite M2:** cópia de trabalho de 1 template abre sem link quebrado com homônimos de exemplo; nenhum segredo nem `.mxd` em `git ls-files`; tag `m2`

### M3 — Automação `mapas` completa (Frente B.3-B.5 → mata P3/P6)
> A automação `mapas` é **determinística** (série padrão, sem chat) e reusa a infra NexoMap
> (bridge, MANIFEST, validação PNG, `Resultados/`). A aba Mapas IA continua em paralelo (§0.1.1).
- [ ] Port py2 `templates/mxd/scripts/adapt_generico.py` (fusão adapt_dinamica/tematico/bloco2; broken = `os.path.exists`, nunca `isBroken` pós-repontagem; dedupe sem matar camada dona de legenda)
- [ ] Port py2 `fix_minimap_rect.py` (retângulo + linha-guia; centro do imóvel vindo do JSON)
- [ ] Port py2 `export_pdf.py` (lote 150 dpi, nomes via JSON)
- [ ] `core/geo`: homônimos UTM via ogr2ogr/pyproj a partir do zip + shapes CAR (AUAS/AC/AVN/TIPOLOGIA quando houver)
- [ ] `core/geo`: port do `calc_geo` (áreas ha + TI/UC mais próximos: nome, distância, pontos da linha) — alimenta mapas TI/UC **e** Seção 4 do Word
- [ ] `core/`: gerador da tabela de quantitativos PNG (port do `gen_tabela_quantitativos.py`, valores dinâmicos)
- [ ] `core/`: extrair da pré-análise o gerador de `AIR.shp` (alertas MapBiomas/SCCON → shape)
- [ ] `automations/mapas.py`: orquestra homônimos → adapt → minimap → export → `Mapas_unidos.pdf` (PyMuPDF), progresso por mapa
- [ ] Validação automática pós-export: página não vazia + retângulo do minimapa no lugar + título/escala presentes (render PNG via fitz)
- [ ] Registrar `mapas` no `api/registry.py` (`rede: True`, `saida: "pdf"`, dependência declarável)
- [ ] Seleção de mapas no `projeto.json` (`"mapas": ["dinamica", "tipologia", …]`) + schema
- [ ] Limpeza das cópias de trabalho/tmp após execução
- [ ] **Aceite M3:** regerar os 19 PDFs da Harmonia pelo software com validação automática verde; tag `m3`

### M4 — Word final com figuras (Frente C → mata P4)
- [ ] `pre_analise.py`: etapa "montar figuras" — PDF→PNG (fitz ~180 dpi) + legenda "Figura N — …" na ordem do modelo
- [ ] Ordenação de dependência no `/api/run` (`mapas` antes de `pre_analise` quando ambos marcados)
- [ ] Fallback sem mapas: placeholders "Figura N" (comportamento atual preservado)
- [ ] Seção 4 (Áreas Protegidas) alimentada pelo `calc_geo` (distâncias reais TI/UC)
- [ ] **Aceite M4:** diff estrutural (títulos/tabelas/nº figuras) Word gerado × `Análise_de_area_Fazenda_Harmonia.docx` = igual; tag `m4`

### M5 — UI (Frente D → mata P2/P7)
- [ ] Refatorar `App.jsx` em componentes (`Projetos`, `PreAnalise`, `Mapas`, `Resultados`, `Config`)
- [ ] Aba Pré-Análise: drag-drop `.zip` → resumo do shape (polígonos, área, CRS, municípios)
- [ ] Upload dos PDFs de matrícula → extração IA → **grade de conferência editável** (obrigatória; destaque para campos de baixa confiança)
- [ ] Progresso por seção com avisos de degradação visíveis; selo "requer conferência" em embargos
- [ ] Aba Mapas: seleção, progresso por mapa, miniaturas de validação, abrir PDF/pasta
- [ ] Tela Config: caminhos (ArcGIS/ogr2ogr) + edição do `secrets.local.json`
- [ ] **Aceite M5:** fluxo completo (zip + matrículas → Word + PDFs) 100% pela UI; tag `m5`

### M6 — Robustez, testes e empacotamento (Frentes E+F → mata P5/P8)
- [ ] TLS por host (`verify=True` com fallback avisado) em `core/clients/http.py`
- [ ] Testes pytest: config/schema, normalize, recibo, geo, overlay, docx (estrutura), MANIFEST dos templates
- [ ] Teste ponta a ponta offline com respostas WFS gravadas (requests-mock)
- [ ] Smoke test `@arcgis` opcional (1 template → 1 PDF)
- [ ] Testes de encoding: projeto em pasta com acento; nomes de mapa com `ç/ã`
- [ ] PyInstaller: incluir `ui/dist`, `catalogo/`, `templates/mxd/`; comando "doctor" pós-instalação (ArcGIS, ogr2ogr, WebView2, **chave DeepSeek válida**, authkey SEMA)
- [ ] **Aceite M6:** suíte verde + `.exe` executa o fluxo M5 em máquina limpa (com ArcGIS); tag `m6` = release `v2.0`
