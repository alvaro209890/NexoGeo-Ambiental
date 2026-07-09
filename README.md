# NexoGeo-Ambiental — Motor de Mapas IA no Padrão IMAP

Motor cartográfico 100% nativo (Python/matplotlib, sem ArcMap) com IA (DeepSeek V4 Pro)
que **cria, edita e versiona mapas** no padrão IMAP (Mato Grosso) usando function calling.
A IA opera o mapa por **tools atômicas** — cada elemento (título, legenda, camadas, tabela,
escala) é editável individualmente.

## Status atual (2026-07-08)

| Fase | Status |
|------|--------|
| A — Layout dirigido pela IA | ✅ Pushado |
| B — Function calling (16 tools) | ✅ Pushado |
| C — Camadas WMS/WFS + Tabelas calculadas | ✅ Pushado |
| D — Schema/API/UI | 🚧 Em andamento |
| E — Extensibilidade (Planet/Google) | ⬜ Não iniciado |

**Suíte:** 90 testes offline + 5 rede = 95 passando.

## Rodar local

```bash
cd /home/acer/Documentos/NexoGeo-Ambiental
source .venv/bin/activate

# Servidor API
uvicorn api.app:app --port 8000 --host 0.0.0.0

# Frontend (outro terminal)
cd ui && npm run dev
```

Acessar: http://localhost:5173 → aba "Mapas IA"

## Deploy

- **Frontend:** [Vercel](https://ui-kappa-eight-82.vercel.app) (auto-deploy do `main`)
  - Domínio principal: https://nexogeo-cursar.vercel.app (a configurar)
- **Backend:** Cloudflare Tunnel → `https://nexogeo-api.cursar.space` (roda neste PC)
- **Domínio:** `cursar.space` gerenciado via Cloudflare

## Correções aplicadas (2026-07-09)

- **Chat hardcoded:** endpoint `/api/chats/mensagem` agora aceita `path` opcional
  (antes usava sempre `querencia_teste`; fallback mantido se não informado).
- **PRODES/INPE:** corrigido `tipo` de `wms_wfs` para `wms_raster`, endpoint HTTP→HTTPS
  e layer de `prodes-legal-amz` para `accumulated_deforestation_2007`.
- **SEMA authkey:** presente em `secrets.local.json`; busca de CAR funcionando ao vivo
  (testado com `MT313839/2025` — Fazenda Boa Vista V, 253.97 ha).
- **117 testes offline passando**, 9 skip de rede.

## Estrutura

```
core/               ← motor do mapa (renderer, layers, tools, AI)
api/                ← FastAPI (endpoints REST + SSE)
ui/                 ← React 18 + Vite + Tailwind 4
catalogo/           ← catálogo de camadas (SEMA, INCRA, IBAMA, etc.)
templates/          ← layouts de página (A3/A4 retrato/paisagem)
projetos/           ← projetos de mapa (área base + resultados)
planos/             ← planos de implementação (roadmap fases A→E)
tests/              ← pytest (unit + rede + live)
```

## Chat IA com Tools

Endpoint: `POST /api/nexomap/chat-tools` (SSE streaming)

A IA recebe o pedido do usuário e opera o mapa via **17 tools**:
`criar_mapa`, `adicionar_camada`, `remover_camada`, `editar_camada`, `definir_titulo`,
`mover_elemento`, `alternar_elemento`, `editar_estilo_elemento`, `editar_legenda`,
`criar_tabela`, `definir_metadados_imagem`, `definir_raster_fundo`, `definir_escala`,
`sugerir_opcoes`, `estado_atual`, `listar_camadas`, `finalizar`.

Cada tool call é transmitido em tempo real via SSE para o frontend, que renderiza
cards animados com cores por tipo de operação.

**Sistema de clarificação:** quando a IA encontra ambiguidade, ela chama `sugerir_opcoes`
e o frontend renderiza botões clicáveis para o usuário decidir.

## Camadas disponíveis (ao vivo da SEMA/MT)

CAR digital (ATP, APP, APPD, ARL, AVN, AUAS, Nascentes), embargos SEMA/SIGA/IBAMA,
tipologia vegetal SIMCAR, terras indígenas FUNAI, unidades de conservação,
alertas MapBiomas, PRODES INPE, SIGEF/SNCI INCRA, autos de infração.

## Tabelas com dados reais

A IA pode criar tabelas com `fonte: "quantitativos"`. O pipeline resolve interseção
real das geometrias (shapely overlay) com o perímetro da área base, calcula áreas
em hectares e formata em padrão brasileiro (1.234,56).

## Projeto de teste

`projetos/querencia_teste/` — polígono em Querência/MT (UTM 31982).
Mapas gerados com camadas reais da SEMA + tabelas calculadas.
