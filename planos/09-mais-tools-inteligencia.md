# 09 — Mais tools e inteligência na IA

## Objetivo

Expandir o repertório da IA com **tools de análise, comparação e validação**, além de torná-la
**proativa** — capaz de sugerir melhorias, detectar problemas e operar em **múltiplos passos**
com raciocínio próprio.

## Estado atual

- 17 tools implementadas: `criar_mapa`, `adicionar_camada`, `remover_camada`, `editar_camada`,
  `definir_titulo`, `mover_elemento`, `alternar_elemento`, `editar_estilo_elemento`,
  `editar_legenda`, `criar_tabela`, `definir_metadados_imagem`, `definir_raster_fundo`,
  `definir_escala`, `sugerir_opcoes`, `estado_atual`, `listar_camadas`, `finalizar`
- IA já usa function calling com DeepSeek V4 Pro
- System prompt inclui guia de estilos (hachuras, preenchimento, opacidade)
- Chat com contexto de mensagens anteriores

## Novas tools propostas

### Tool 1: `comparar_mapspecs`
Compara dois MapSpecs (ex: versão atual vs anterior) e retorna diff legível.
```
args: { job_id_anterior: str }
→ "3 camadas adicionadas, legenda movida para rodapé, título alterado"
```

### Tool 2: `validar_mapa`
Roda validações automáticas e retorna checklist de aprovação.
```
args: {}
→ "✅ Título presente | ✅ Legenda não sobrepõe | ⚠️ Escala ausente"
```
Integrar com `core/nexomap_validation.py` e o resultado de `validacao.json`.

### Tool 3: `sugerir_melhorias`
IA analisa o MapSpec atual e **sugere proativamente** melhorias (sem ser perguntada).
```
args: {}
→ "Sugestões: adicione grade de coordenadas, use hachura na AVN, aumente opacidade do CAR"
```

### Tool 4: `aplicar_modelo`
Aplica um **modelo predefinido** de mapa (ex: "modelo embargos", "modelo dinamica") com
camadas, estilos e layout padrão IMAP.
```
args: { modelo: "embargos"|"dinamica"|"car"|"tipologia" }
→ "Modelo 'embargos' aplicado: 4 camadas, legenda no rodapé, título padrão"
```
Modelos definidos em `catalogo/modelos_mapas.json`.

### Tool 5: `exportar_relatorio`
Gera um `.docx` ou `.xlsx` com o resumo do mapa (camadas, quantitativos, validações).
```
args: { formato: "docx"|"xlsx" }
→ "Relatório exportado em Resultados/relatorio.docx"
```

## Melhorias de inteligência

- [ ] **Raciocínio multi-step**: IA planeja antes de executar (ex: "vou precisar de 3 camadas, tabela e legenda")
- [ ] **Auto-correção**: se validação falhar, IA tenta corrigir automaticamente (até 2 tentativas)
- [ ] **Memória de preferências**: IA lembra escolhas do usuário (ex: "você prefere template paisagem")
- [ ] **Sugestão de camadas**: baseado no tipo de mapa pedido, IA sugere camadas relevantes
- [ ] **Detecção de conflitos**: IA avisa quando duas camadas vão se sobrepor visualmente

## Checklist

- [ ] `comparar_mapspecs` — diff entre versões
- [x] `validar_mapa` — checklist automático (nível-spec, `validar_mapspec_imap`; tool registrada)
- [x] `sugerir_melhorias` — proatividade (tool registrada)
- [x] `aplicar_modelo` — templates predefinidos (via `core/nexomap_modelos.py` + `catalogo/modelos_mapas.json`; usado no fluxo CAR, ver plano 11)
- [ ] `exportar_relatorio` — .docx/.xlsx
- [x] Auto-correção no loop — system prompt manda validar antes de finalizar e corrigir HARD (até 2x); testado
- [ ] `comparar_mapspecs` / memória de preferências / raciocínio multi-step explícito
- [x] Testes para as novas tools (`tests/test_validar_mapa.py`, 10 testes)
- [x] Documentação (este plano + plano 11 + handoff)

**Feito 2026-07-09:** `validar_mapa` valida o MapSpec contra o padrão IMAP (checks HARD
estrutura / SOFT estilo) prevendo o que `validar_contra_modelo` (plano 10) diria do PDF;
`sugerir_melhorias` dá dicas proativas; a IA chama `validar_mapa` antes de `finalizar` e
se auto-corrige no próprio loop de tools.

## Dependências

- Planos 00 (tools), 04 (tabelas), 06 (validação), 10 (PDF modelo)
