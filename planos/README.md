# Planos de Implementação — NexoGeo IA Cartográfica

Esta pasta contém **apenas planos e checklists** (`.md`) para levar a IA cartográfica ao ponto
"perfeito": a IA deve **montar, mover, editar e versionar cada elemento do mapa**, **usar as bases
WMS/WFS** (SEMA e demais), **criar tabelas com dados reais** e ser operada por um **conjunto de
tools** (function calling). Nenhum código é alterado por estes documentos — eles guiam a
implementação futura.

> Estado atual do motor (já no `main`): ver
> [`../novas-implementacoes/2026-07-08-ia-cartografica-imap.md`](../novas-implementacoes/2026-07-08-ia-cartografica-imap.md).
> Fonte de verdade do mapa = **MapSpec** (JSON versionado), nunca PDF/PNG.

## Objetivo-guia

> _"A IA deve poder movimentar cada elemento do mapa, editar a legenda, saber usar as bases WMS da
> SEMA e mais WMS disponíveis, saber criar tabelas com dados e tudo mais — e ser operada por tools."_

## Índice

| # | Plano | Foco |
|---|-------|------|
| 00 | [Arquitetura de Tools da IA](00-arquitetura-tools-ia.md) | Function calling: tools que a IA chama para operar o mapa |
| 01 | [Mover e posicionar elementos](01-mover-posicionar-elementos.md) | Cada peça do layout com posição/âncora/tamanho editáveis |
| 02 | [Legenda editável](02-legenda-editavel.md) | Itens, rótulos, símbolos, ordem, posição e estilo da legenda |
| 03 | [Camadas WMS/WFS (SEMA e demais)](03-camadas-wms-wfs.md) | Catálogo completo, WMS GetMap, GML do INCRA, auth |
| 04 | [Tabelas com dados reais](04-tabelas-de-dados.md) | Modelo de tabela + cálculo automático de quantitativos |
| 05 | [Schema, exemplos e UI](05-schema-exemplos-ui.md) | Wire dos campos novos, endpoints e aba Mapas IA |
| 06 | [Validação e QA](06-validacao-qa.md) | Sobreposição, corte, cobertura de camadas, legibilidade |
| 07 | [Plano de testes](07-testes.md) | Unit, integração, visual e testes ao vivo |
| 08 | [Formatos e fontes de fundo](08-formatos-e-fontes.md) | TIF, Planet/Google, PDF-modelo, KMZ, extensibilidade |

## Roadmap por fases

- **Fase A — Layout dirigido pela IA (posição de tudo).** Planos 01, 02. Cada elemento vira um
  objeto posicionável no MapSpec; renderer lê posição/tamanho.
- **Fase B — Tools da IA (function calling).** Plano 00. Substitui o "devolve MapSpec inteiro" por
  chamadas de ferramenta atômicas (mover, editar, adicionar camada, criar tabela…).
- **Fase C — Dados reais.** Planos 03, 04. WMS/WFS completos + tabelas com quantitativos calculados
  por overlay (não digitados pela IA).
- **Fase D — Integração e QA.** Planos 05, 06, 07. Schema/UI/endpoints + validação + testes.
- **Fase E — Extensibilidade.** Plano 08. Novas fontes de fundo e formatos, sem inflar escopo.

## Convenções destes planos

Cada plano tem: **Objetivo · Estado atual · Escopo (in/out) · Design/contrato · Checklist de
implementação · Plano de testes · Critérios de aceite · Riscos e decisões abertas · Dependências**.

Checkboxes `- [ ]` marcam tarefas; ao concluir, marcar `- [x]` e mover o resumo para
`novas-implementacoes/` com a data.

## Princípios inegociáveis

- **Sem ArcMap** no produto principal (matplotlib nativo).
- **Segredos** só em `secrets.local.json` (gitignored), nunca no código.
- **Não inventar endpoints** — usar apenas os de `catalogo/servicos_geo.json` / confirmados.
- **MapSpec = fonte de verdade**; edição sempre parte do MapSpec, nunca do PDF/PNG.
- **Degradação graciosa**: falha de rede/camada vira aviso, não derruba a geração.
