# 06 — Validação e QA visual

## Objetivo

Garantir que **todo mapa gerado seja publicável**: sem branco, sem sobreposição de elementos, sem
texto cortado, com imagem/camadas corretas, legível e com a área **dentro** do mapa. A validação é a
rede de segurança que permite a IA iterar sozinha com confiança.

## Estado atual

- `core/nexomap_validation.py` checa: PDF abre, tamanho mínimo, título presente, página não vazia,
  **`mapa_tem_imagem`** (variância de cor no quadro), **`sem_sobreposicao_elementos`** e
  **`sem_texto_cortado`** (relatório de layout do renderer).
- Bom começo, mas ainda **grosso**: não verifica se a **área aparece** no mapa, se as **camadas
  pedidas foram desenhadas**, contraste de rótulos, nem legibilidade da legenda.

## Escopo

**Inclui**
- Novos checks: área visível no quadro, cobertura de camadas (pedidas × desenhadas), densidade de
  rótulos, contraste texto/fundo, DMS presente, escala coerente.
- **Auto-correção sugerida**: quando um check falha, emitir uma **sugestão de tool** (ex.: mover
  legenda) para o agente aplicar (plano 00).
- Relatório `validacao.json` mais rico + severidade (erro/aviso).

**Não inclui**
- Verificação semântica de conteúdo (se a análise ambiental "faz sentido") — fora de escopo.

## Design / contrato

### Novos checks

| Check | Como | Severidade |
|-------|------|-----------|
| `area_visivel` | bbox da área ⊂ extent do mapa; % da área dentro do quadro | erro se <95% |
| `camadas_desenhadas` | cada camada do MapSpec com feições > 0 (ou aviso se recorte vazio) | aviso |
| `sem_sobreposicao_elementos` | IoU dos rects de topo (já existe) | erro |
| `sem_texto_cortado` | artistas de texto dentro da página (já existe) | erro |
| `mapa_tem_imagem` | variância de cor no quadro (já existe) | erro |
| `grade_presente` | rótulos DMS/UTM detectados nas bordas | aviso |
| `escala_coerente` | 1:N redondo e área ocupa 30–90% do quadro | aviso |
| `rotulos_legiveis` | nº de rótulos sobrepostos abaixo de limite | aviso |
| `legenda_presente` | quando há camadas, legenda existe e não vazia | aviso |

### Auto-correção (loop com o agente)

Cada falha carrega `sugestao` = tool + args (ex.: `{"tool":"mover_elemento","args":{"elemento":"legenda","posicao":{"ancora":"bottom-left"}}}`).
O agente (plano 00) pode reaplicar e re-renderizar até `ok` ou limite de tentativas.

## Checklist de implementação

- [ ] Implementar `area_visivel` (bbox área × extent) no validador (renderer passa os bounds).
- [ ] Implementar `camadas_desenhadas` (comparar MapSpec × `drawn_layers`).
- [ ] Implementar `grade_presente`, `escala_coerente`, `legenda_presente`, `rotulos_legiveis`.
- [ ] Adicionar **severidade** (erro/aviso) e `sugestao` por check.
- [ ] `ok` global = nenhum check de severidade "erro" falhou.
- [ ] Expor no `resultado.json` um resumo legível dos checks.

## Plano de testes

**Unit (`tests/test_validacao.py`)**
- [ ] Mapa em branco → `mapa_tem_imagem` falha.
- [ ] Legenda sobre metadados → `sem_sobreposicao_elementos` falha com `sugestao`.
- [ ] Área fora do extent → `area_visivel` falha.
- [ ] Texto na borda → `sem_texto_cortado` falha.
- [ ] Mapa bom → todos `ok`.

**Integração**
- [ ] Loop agente: injetar sobreposição, validar, aplicar `sugestao`, re-render → `ok`.

## Critérios de aceite

- Nenhum mapa com erro de layout é marcado `ok`.
- Cada erro traz uma sugestão acionável de correção.
- Falsos positivos raros (tolerâncias calibradas com mapas reais).

## Riscos e decisões abertas

- **Calibrar tolerâncias** (variância, IoU, contraste) com uma amostra de mapas bons e ruins.
- **Custo do loop de auto-correção** (re-render) → limitar tentativas (ex.: 2).

## Dependências

- Plano 00 (tools) para aplicar as sugestões.
- Plano 01 (posição) para as correções de layout.
