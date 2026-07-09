# HANDOFF — NexoGeo-Ambiental (2026-07-09 00:30)

Documento de passagem para a **próxima IA** continuar o desenvolvimento do NexoGeo-Ambiental.
**Leia este arquivo inteiro antes de tocar no código.**

---

## Visão geral

Motor cartográfico 100% nativo (Python/matplotlib, sem ArcMap) com IA (DeepSeek V4 Pro)
que cria, edita e versiona mapas no padrão IMAP (Mato Grosso) usando **function calling**.

A IA opera o mapa por **17 tools atômicas** — cada elemento é editável individualmente.
O frontend é um chat estilo Manus AI com streaming de tool calls, auth, e persistência.

---

## Estado atual (95 testes passando)

### Fase A — Layout ✅
Planos 01, 02. Cada elemento do mapa tem posição/âncora/tamanho editáveis via MapSpec.
Legenda com modos auto/manual/misto.

### Fase B — Tools ✅
Plano 00. 17 tools com function calling (DeepSeek). Loop IA<->tools com callback `on_tool_call`
para streaming SSE em tempo real.

### Fase C — Dados reais ✅
Planos 03, 04. Catálogo com 24 camadas WFS/WMS da SEMA/INCRA/IBAMA. Tabelas com
quantitativos calculados por overlay shapely real (área em ha, %, formatação BR).

### Fase D — Integração e UI 🚧
Planos 05, 06, 07. Schema JSON parcial, API REST + SSE, frontend React com chat.
Auth + persistência de chats implementados. **Falta:** schema completo, endpoints de
edição versionada, UI de timeline de versões, validação QA avançada.

### Extras implementados (além dos planos originais)
- Deploy Vercel + Cloudflare Tunnel (`nexogeo-api.cursar.space`)
- Sistema de login (email/senha, hash SHA256, token)
- Chat persistente por usuário em `~/Documentos/banco_dados_nexogeo/chats/`
- Contexto de conversa (histórico enviado à IA)
- Guia de estilos no system prompt (hachuras, preenchimento, opacidade)
- Tool `sugerir_opcoes` com botões clicáveis no frontend
- Padrão visual IMAP: título branco centro-topo, faixa inferior

---

## Arquitetura

```
api/app.py              ← FastAPI (endpoints REST + SSE streaming)
core/
  nexomap_agent.py      ← Loop IA<->tools, system prompt
  nexomap_ai.py         ← Provider DeepSeek, run_tools()
  nexomap_generator.py  ← Orquestração (chat_tools, chat_tools_stream, generate)
  nexomap_tools.py      ← 17 tools + TOOL_SCHEMAS
  nexomap_renderer.py   ← Renderer matplotlib (flagship + standard furniture)
  nexomap_quantitativos.py ← Cálculo de áreas por overlay shapely
  nexomap_layers.py     ← Fetch WFS/GML/REST/WMS com cache
  nexomap_layout.py     ← Resolução de âncoras/posições
  nexomap_catalog.py    ← Catálogo de camadas + templates
  nexomap_validation.py ← Validação de PDF gerado
  auth.py               ← Autenticação (registro, login, token)
  chat_store.py         ← Persistência de chats (JSON)
ui/
  src/ChatView.jsx      ← Chat com tool cards, auth modal, sidebar
  src/index.css         ← Tailwind 4 + CSS custom properties (dark theme)
projetos/
  querencia_teste/      ← Projeto de teste com shape real
planos/                 ← Roadmap (09 e 10 são NOVOS — não iniciados)
referencias/
  Mapas_unidos.pdf      ← 24 mapas IMAP reais (gabarito visual)
```

---

## O que funciona

- Geração de mapas via chat (prompt → tools → render → PDF)
- Edição de mapas existentes (chat_tools com parent_job_id)
- Streaming SSE de tool calls em tempo real
- Auth (registro/login) com persistência local
- Chat persistente (histórico, múltiplos chats por usuário)
- IA recebe contexto das mensagens anteriores
- Tabelas com dados reais (overlay shapely)
- 24 camadas ao vivo (SEMA GeoServer, INCRA, IBAMA)
- Hachuras e estilos configuráveis pela IA
- Deploy Vercel (frontend) + Cloudflare Tunnel (backend)

## O que NÃO funciona / precisa atenção

- Tunnel `nexogeo-api.cursar.space` pode não estar roteando ainda (DNS recente)
- Frontend Vercel aponta para `API = ''` (localhost) — precisa configurar `VITE_API_URL`
- Schema JSON (`schema/mapspec.schema.json`) está desatualizado com campos novos
- UI não tem timeline de versões (plano 05)
- Validação QA é básica (9 checks) — falta cobertura visual
- Testes de rede precisam de `NEXO_NET=1` + `SEMA_AUTHKEY`
- `referencias/Mapas_unidos.pdf` não está sendo usado para validação

---

## Próximos passos (priorizados)

### ✅ CONCLUÍDO 2026-07-09 — Plano 10 (validação PDF-modelo)
- `scripts/extrair_perfil_imap.py` → gera `referencias/perfil_imap.json` (24 mapas IMAP reais)
- `core/nexomap_validation.py`: `validar_contra_modelo(pdf, perfil)`, `extrair_metricas_pagina/pdf`,
  `load_perfil_imap`. Checks HARD (estrutura) vs SOFT (estilo). Flagship passa todos os HARD.
- Integrado no render: `validacao.json > conformidade_modelo` (best-effort, não bloqueia)
- `tests/test_validacao_modelo.py`: 6 testes. **Suite total: 96 offline + 6 skipped.**
- Gaps de estilo achados (soft): título nativo ~16pt vs IMAP ~25pt; norte não detectável por texto.

### ✅ CONCLUÍDO 2026-07-09 — Plano 09 (tools) + Plano 11 (Mapas por CAR)
- **Plano 09**: tools `validar_mapa` (valida MapSpec vs IMAP, checks HARD/SOFT, `core/nexomap_validation.py::validar_mapspec_imap`)
  e `sugerir_melhorias`; system prompt manda validar antes de finalizar e auto-corrigir. `tests/test_validar_mapa.py` (10 testes).
- **Plano 11 — Mapas por CAR (WEB)**: card de modelo + nº do CAR **estadual** → busca ATP na SEMA
  (`core/nexomap_car.py`), cruza com SIMCAR digital (uso consolidado/tipologia/APP/ARL/AVN/AUAS —
  novas camadas no catálogo), aplica modelo (`core/nexomap_modelos.py` + `catalogo/modelos_mapas.json`,
  7 modelos), renderiza IMAP. Endpoints `GET /api/nexomap/modelos` + `POST /api/nexomap/car-mapa` (SSE).
  Frontend `ui/src/CarMapaView.jsx` (cards + prévia + quantitativos + PDF), acessível no lobby.
  Projeto scaffold `projetos/car_web/`. **Validado ao vivo**: `MT313839/2025` → Fazenda Boa Vista V.
- Fix renderer: rótulos de grade UTM/DMS não contam como "texto cortado" (`_e_rotulo_grade`).
- **Suite: 114 offline + 8 skipped; net 7 (busca CAR ao vivo).**
- **Deploy**: frontend buildado com `VITE_API_URL=https://nexogeo-api.cursar.space`; backend+tunnel no ar.

### ✅ 2026-07-09 (2ª rodada) — cadastro-primeiro + fix "load failed" + persistência
- **Auth antes dos mapas**: `ui/src/AuthScreen.jsx`+`auth.js`; `App.jsx` gateia tudo até logar. Validado ao vivo (registrar+login via tunnel).
- **"Load failed" (raiz infra)**: backend agora é serviço systemd persistente (`deploy/nexogeo-backend.service`, Restart=always, linger); tunnel `saldopro-cloudflared.service` roda pelo UUID (ingress LOCAL c/ nexogeo-api→:8000) em vez do nome (ingress remoto sem a rota → 404 intermitente). `deploy/README.md`. 6/6 200; saldopro inalterado.
- **Redeploy Vercel** (público `ui-kappa-eight-82.vercel.app`) + push main.
- GOTCHA infra: NÃO subir uvicorn/cloudflared manual — usar os serviços systemd (`systemctl --user`). Backend persiste via linger.

### Próximo
1. **Schema JSON** (plano 05): campos novos (subtitulo, grade_tipo, raster_fundo, metadados_imagem, tabela, marca, layout, legenda, versao, parent_job_id)
2. **Endpoint de edição versionada** (plano 05): `POST /api/nexomap/edit` com SSE
3. Tipologia por classe de vegetação (atributo) no fluxo CAR; cache da ATP; basemap Planet (plano 08)

### Curto prazo
4. **Novas tools** (plano 09): `comparar_mapspecs`, `validar_mapa`, `sugerir_melhorias`,
   `aplicar_modelo`, `exportar_relatorio`
5. **Auto-correção**: se validação falhar, IA tenta corrigir (loop de 2 tentativas)
6. **Configurar VITE_API_URL** no Vercel para apontar para o tunnel

### Médio prazo
7. **UI de timeline** (plano 05): versões do mapa com diff visual
8. **Planet/Google basemaps** (plano 08)
9. **Fixtures e testes visuais** (plano 07)

---

## Comandos

```bash
cd /home/acer/Documentos/NexoGeo-Ambiental

# Venv
source .venv/bin/activate

# Testes
.venv/bin/python -m pytest tests -q                      # 90 offline
NEXO_NET=1 SEMA_AUTHKEY=$(python3 -c "import json; print(json.load(open('secrets.local.json'))['sema_authkey'])") \
  .venv/bin/python -m pytest tests/net -q                 # 5 rede

# Servidor
.venv/bin/python -m uvicorn api.app:app --port 8000 --host 127.0.0.1

# Frontend
cd ui && npm run dev      # dev (porta 5173)
cd ui && npm run build    # produção
cd ui && npx vercel --prod  # deploy

# Testar chat-tools (com servidor rodando)
curl -X POST http://localhost:8000/api/nexomap/chat-tools \
  -H 'Content-Type: application/json' \
  -d '{"path":"projetos/querencia_teste/projeto.json","prompt":"Mude o titulo para Teste"}'

# Registro
curl -X POST http://localhost:8000/api/auth/registrar \
  -H 'Content-Type: application/json' \
  -d '{"email":"a@b.com","senha":"1234","nome":"Teste"}'
```

---

## Gotchas

- **DeepSeek key** em `secrets.local.json` (gitignored) — NUNCA commitar
- **Repo é PÚBLICO** — cuidado com credenciais nos MXDs e secrets
- `npm run build` NÃO faz typecheck (só `tsc --noEmit`)
- Polygon winding: shapefile espera **clockwise** (shapely box é CCW → inverter)
- `_flagship_furniture` quebrava com `band_rect=None` (já corrigido)
- `config.classes` no `criar_tabela` pode vir como strings ou dicts (normalizado)
- Tunnel Cloudflare usa config em `/home/acer/.cloudflared/saldopro-config.yml`
- Backend salva dados em `~/Documentos/banco_dados_nexogeo/`

## Segredos

```bash
cat secrets.local.json
# {
#   "deepseek_api_key": "sk-...",
#   "sema_authkey": "541085de-...",
#   "planet_api_key": "PLAK..."
# }
```
