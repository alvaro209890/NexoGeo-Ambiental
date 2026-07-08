# 05 — Schema, exemplos e UI

## Objetivo

Expor tudo que foi criado (campos novos do MapSpec, edição versionada, tools) no **schema**, nos
**exemplos**, na **API** e na **aba Mapas IA** da UI — para o usuário operar por chat e ver o
histórico de versões.

## Estado atual

- `schema/mapspec.schema.json` **não** contém os campos novos (`subtitulo`, `grade_tipo`,
  `raster_fundo`, `metadados_imagem`, `tabela`, `marca`, `versao`, `parent_job_id`) nem `layout`/`legenda`.
- `exemplos/nexomap.projeto.template.json` não ilustra o padrão IMAP.
- `api/app.py` tem `/api/nexomap/chat`, `/generate`, `/resultados`, `/doctor` — **falta** edição
  versionada (`edit_map`) e o loop de tools.
- `ui/src/App.jsx` (`MapsAiView`) não expõe: editar mapa existente, histórico de versões,
  controles de elementos, nem seleção de raster de fundo.

## Escopo

**Inclui**
- Atualizar `schema/mapspec.schema.json` com todos os campos (validação de forma).
- Atualizar `exemplos/` com um MapSpec padrão IMAP (satélite + tipologia + tabela + metadados).
- Endpoints: `POST /api/nexomap/edit` (edição versionada) e `POST /api/nexomap/chat-tools`.
- UI: botão "Editar" por mapa gerado, campo de instrução, timeline de versões, seleção de raster.
- Rodar `npm run build` e validar.

**Não inclui**
- Editor visual drag-and-drop (a UI envia instruções de texto/tool).

## Design / contrato

### Schema (adicionar propriedades, todas opcionais)

- `subtitulo:string`, `grade_tipo:enum[dms,utm]`, `raster_fundo:string`,
  `metadados_imagem:object`, `tabela:object`, `marca:object`,
  `versao:integer`, `parent_job_id:string`, `layout:object`, `legenda:object`.
- Manter os campos obrigatórios atuais; novos campos não quebram MapSpecs antigos.

### Endpoints

```http
POST /api/nexomap/edit
{ "path": "...projeto.nexomap.json", "parent_job_id": "<job>", "prompt": "remova o titulo preto" }
-> SSE started/progress/done com o novo job (versao = pai+1, parent_job_id setado)

POST /api/nexomap/chat-tools           # quando o plano 00 estiver pronto
{ "path": "...", "parent_job_id?": "...", "prompt": "mova a legenda para o rodape" }
-> aplica tools -> render -> resultado
```

### UI (`MapsAiView`)

- **Lista de resultados** já existe → adicionar botão **"Editar"** por job (abre campo de instrução →
  chama `/edit` com `parent_job_id`).
- **Timeline de versões**: ler `versoes.jsonl` (`GET /api/nexomap/versoes?path=...`) e mostrar a
  linhagem (v1→v2→…), permitindo abrir qualquer versão.
- **Seleção de raster de fundo** (.tif/.tiff) na preparação da aba (grava em `raster_fundo`).
- Mensagens de aviso (camada sem authkey, sem rede) já retornam em `warnings` → exibir.

## Checklist de implementação

- [ ] Atualizar `schema/mapspec.schema.json` (campos novos, todos opcionais).
- [ ] Atualizar `exemplos/nexomap.projeto.template.json` + um `exemplos/mapspec.imap.exemplo.json`.
- [ ] Endpoint `POST /api/nexomap/edit` chamando `nexomap_generator.edit_map` (SSE).
- [ ] Endpoint `GET /api/nexomap/versoes` lendo `versoes.jsonl`.
- [ ] (Após plano 00) `POST /api/nexomap/chat-tools`.
- [ ] UI: botão Editar + campo de instrução + timeline de versões + seletor de raster.
- [ ] `cd ui && npm install && npm run build` → `dist/` sem erros.
- [ ] Atualizar `docs/NEXOMAP_AGENT_HANDOFF.md` e o Manual da UI.

## Plano de testes

**Unit/integração (`tests/test_api_nexomap.py`, TestClient)**
- [ ] `/edit` cria job com `versao = pai+1` e `parent_job_id` correto.
- [ ] `/versoes` devolve a linhagem esperada.
- [ ] `/generate` e `/edit` continuam passando com MapSpec padrão IMAP.

**UI/build**
- [ ] `npm run build` gera `dist/` (CSS/JS) sem erro.
- [ ] Smoke manual: abrir projeto → gerar → editar "remova o título preto" → ver v2 sem a caixa.

## Critérios de aceite

- Schema valida MapSpecs novos e antigos.
- Aba Mapas IA permite gerar, **editar** e navegar **versões**.
- `npm run build` limpo.

## Riscos e decisões abertas

- **Refatorar `ui/src/App.jsx`** (grande) em componentes por aba antes de crescer mais? Recomendado.
- **SSE na UI** já usado em `/generate`; reusar o mesmo padrão em `/edit`.

## Dependências

- Planos 00–04 definem os campos/tools a expor.
