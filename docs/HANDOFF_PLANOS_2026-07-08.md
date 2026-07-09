# HANDOFF — Estado atual do NexoGeo-Ambiental (2026-07-08 23:30)

## O que foi feito hoje (08/07/2026)

### Fase C — CONCLUÍDA (commit `8a3cbf6`)
- Plano 03 (camadas WMS/WFS): catálogo completo, parser GML, cache local, fetch paginado
- Plano 04 (tabelas calculadas): `nexomap_quantitativos.py`, overlay shapely, formatação BR
- 95 testes passando (90 offline + 5 rede ao vivo)

### Padrão IMAP (commit `67c4563`)
- Título: caixa branca topo-centro (não mais caixa escura à direita)
- Template padrão: `dinamica_a3_paisagem` (landscape) com faixa inferior
- Faixa inferior: minimapa | METADADOS IMAGEM | Legenda
- Feature labels: amarelo com stroke escuro

### Chat IA com Tools (commits `8f44efd`)
- Backend: `chat_tools_stream()` com SSE streaming de cada tool call
- Callback `on_tool_call` no `run_tool_loop` para eventos em tempo real
- Endpoint `POST /api/nexomap/chat-tools`
- Frontend `ChatView.jsx`: chat completo com tool cards coloridos e animações
- Sistema de clarificação: tool `sugerir_opcoes` + botões clicáveis no frontend

### Deploy (commits em andamento)
- Frontend no Vercel: `https://nexogeo-cursar.vercel.app` (precisa configurar domínio)
- Backend via Cloudflare Tunnel: `nexogeo-api.cursar.space` → `localhost:8000`
- DNS adicionado, aguardando propagação

### Correções
- `_flagship_furniture` suporta `band_rect=None` (não quebra com tabela em retrato)
- Polígono de teste com winding clockwise (sem warnings de orientação)
- `resolver_tabela_calculada` aceita strings ou dicts em `config.classes`
- Prompt do sistema descreve template paisagem + metadados para faixa inferior IMAP

## Próximos passos (Fase D)

1. **Plano 05** — Schema JSON + endpoints REST + UI de versões
2. **Plano 06** — Validação QA (sobreposição, cobertura, legibilidade)
3. **Plano 07** — Fixtures + testes visuais + documentação de setup

## Próximos passos (Fase E)

4. **Plano 08** — Basemaps Planet/Google + PDF-modelo como referência

## Projeto de teste

`projetos/querencia_teste/` com polígono real em Querência/MT.
Mapas gerados com DeepSeek V4 Pro (+16 tool calls por mapa).
Tabelas com dados reais: overlay CAR ATP + AVN + AUAS sobre área base.

## Comandos úteis

```bash
# Testes
.venv/bin/python -m pytest tests -q                    # offline (90)
NEXO_NET=1 SEMA_AUTHKEY=$(python3 -c "import json; print(json.load(open('secrets.local.json'))['sema_authkey'])") .venv/bin/python -m pytest tests/net -q  # rede (5)

# Servidor
.venv/bin/python -m uvicorn api.app:app --port 8000 --host 0.0.0.0

# Frontend
cd ui && npm run dev      # dev (porta 5173)
cd ui && npm run build    # produção

# Deploy
cd ui && npx vercel --prod
```

## Segredos (NUNCA commitar)

- `secrets.local.json` na raiz: `deepseek_api_key`, `sema_authkey`, `planet_api_key`
- MXDs em `templates/mxd/` têm credenciais embutidas (gitignored)
- Repo é PÚBLICO → cuidado máximo com segredos
