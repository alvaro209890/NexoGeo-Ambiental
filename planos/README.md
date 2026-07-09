# Planos de Implementação — NexoGeo IA Cartográfica

> **Estado atual (2026-07-09 00:30):** 95 testes passando, deploy Vercel + Cloudflare Tunnel,
> auth + chat persistente, IA com 17 tools + guia de estilos. Fases A-C completas, D em andamento.

## Roadmap por fases

| Fase | Planos | Status | Commits |
|------|--------|--------|---------|
| **A** — Layout dirigido pela IA | 01, 02 | ✅ Concluída | `0be6a67` |
| **B** — Tools da IA (function calling) | 00 | ✅ Concluída | `471db80` |
| **C** — Dados reais | 03, 04 | ✅ Concluída | `8a3cbf6` |
| **D** — Integração, UI e QA | 05, 06, 07 | 🚧 Em andamento | `3da5317` |
| **E** — Extensibilidade | 08 | ⬜ Não iniciado | — |
| **F** — Inteligência e validação | 09, **10** | 🚧 Plano 10 ✅ + Plano 09 (validar_mapa/sugerir_melhorias/aplicar_modelo) ✅ | — |
| **G** — Mapas por CAR (web) | **11** | ✅ Concluído 2026-07-09 | — |

## Fase G — Mapas por CAR (plano 11)

Fluxo web: card de modelo + número do CAR estadual → busca a ATP na SEMA, cruza com o
SIMCAR digital (uso consolidado, tipologia, APP/ARL/AVN/AUAS) e gera o mapa IMAP.
Backend (`nexomap_car`, `nexomap_modelos`, endpoints `/modelos` e `/car-mapa`), frontend
(`CarMapaView` — cards + previa + quantitativos), validado ao vivo. Ver [11](11-mapas-por-car.md).

## Novos planos (Fase F)

| # | Plano | Foco |
|---|-------|------|
| 09 | [Mais tools e inteligência na IA](09-mais-tools-inteligencia.md) | Comparação de mapas, validação automática, edição multi-step, sugestões proativas |
| 10 | [Validação com PDFs de referência](10-validacao-pdf-modelo.md) | Extrair padrões visuais do PDF-modelo IMAP, validar conformidade automática |

## O que já foi implementado além dos planos originais

- **Chat IA com streaming**: endpoint SSE `POST /api/nexomap/chat-tools`, frontend com tool cards
- **Sistema de clarificação**: tool `sugerir_opcoes` + botões clicáveis no chat
- **Auth + persistência**: login email/senha, chats salvos por usuário
- **Guia de estilos**: IA instruída com hachuras (`////`, `xxxx`, `----`, `....`), preenchimento, opacidade
- **Contexto de conversa**: IA recebe histórico das últimas mensagens
- **Deploy**: Vercel (frontend) + Cloudflare Tunnel (backend `nexogeo-api.cursar.space`)
- **Padrão IMAP**: título branco centro-topo, faixa inferior, template paisagem
- **Tabelas calculadas**: overlay shapely real com formatação brasileira
- **Projeto teste**: Querência/MT com dados reais da SEMA

## Para a próxima IA continuar

Ler **`docs/HANDOFF_NEXOGEO_2026-07-09.md`** — contém:
- Estado atual completo de cada módulo
- O que funciona e o que não funciona
- Próximos passos priorizados
- Gotchas e convenções do projeto
- Comandos de desenvolvimento e deploy
