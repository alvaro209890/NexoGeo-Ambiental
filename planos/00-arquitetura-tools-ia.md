# 00 — Arquitetura de Tools da IA (function calling)

## Objetivo

Fazer a IA **operar o mapa por meio de ferramentas (tools) atômicas** em vez de devolver o MapSpec
inteiro a cada pedido. Cada instrução do chat ("mova a legenda para baixo", "adicione embargos da
SEMA", "crie uma tabela de quantitativos") vira **uma ou mais chamadas de tool** que alteram o
MapSpec de forma incremental, previsível e auditável.

## Estado atual

- `core/nexomap_ai.py` já fala com DeepSeek (OpenAI-compatible) e faz:
  - `spec_from_prompt()` → MapSpec novo (JSON completo).
  - `spec_edit_from_prompt()` → edita o MapSpec inteiro a partir de uma instrução.
- Não há **tools/function calling**: a IA reescreve o JSON todo, o que é frágil para edições finas
  e para "mover cada elemento".

## Escopo

**Inclui**
- Definição de um **catálogo de tools** (nome, descrição, JSON Schema de argumentos).
- Camada `core/nexomap_tools.py` que **executa** cada tool sobre um MapSpec em memória.
- Loop de orquestração: IA → tool_calls → aplica → devolve estado → repete até `finalizar`.
- Fallback determinístico (sem IA) reaproveitando `apply_rule_based_edit`.

**Não inclui**
- Treinar modelo; usar apenas function calling do provedor (DeepSeek/OpenAI-compatible).
- Novos endpoints WMS (ver plano 03).

## Design / contrato

### Catálogo de tools (v1)

| Tool | Argumentos (resumo) | Efeito no MapSpec |
|------|--------------------|-------------------|
| `estado_atual` | — (read) | Retorna o MapSpec atual + camadas/elementos disponíveis |
| `listar_camadas` | — (read) | Lista `catalogo/camadas.json` (id, nome, tema, auth) |
| `criar_mapa` | `titulo, tipo, template, basemap, grade_tipo` | Cria MapSpec base |
| `definir_titulo` | `titulo, subtitulo` | Título/subtítulo |
| `mover_elemento` | `elemento, posicao{ancora,x,y}, tamanho?` | Reposiciona 1 peça (ver plano 01) |
| `alternar_elemento` | `elemento, visivel:bool` | Liga/desliga (`elementos_layout`) |
| `editar_estilo_elemento` | `elemento, props{fonte,cor,tamanho,fundo}` | Estilo de 1 peça |
| `adicionar_camada` | `fonte(catalogo.<id>/area_base), estilo{linha,preenchimento,hachura,opacidade}, rotulo` | +camada |
| `remover_camada` | `id` | −camada |
| `editar_camada` | `id, estilo?, rotulo?, filtro?` | Estilo/rótulo de camada |
| `editar_legenda` | `titulo?, itens[]?, posicao?, colunas?` | Legenda (ver plano 02) |
| `criar_tabela` | `titulo, colunas[], linhas[[]] \| fonte:"quantitativos"` | Tabela (ver plano 04) |
| `definir_metadados_imagem` | `satelite_sensor, data_aquisicao, orbita_ponto, datum` | Bloco METADADOS IMAGEM |
| `definir_raster_fundo` | `caminho \| fonte(planet/google)` | Fundo do mapa (ver plano 08) |
| `definir_escala` | `escala:int\|"auto"` | Escala |
| `finalizar` | `resumo` | Encerra o turno e dispara render |

Cada tool = função Python com assinatura tipada + JSON Schema exportável ao provedor no campo
`tools` da API. A IA responde com `tool_calls`; o orquestrador executa e devolve o resultado
(`role: "tool"`).

### Fluxo de orquestração (pseudo)

```
mapspec = carregar_ou_novo()
messages = [system(tools_prompt), user(pedido)]
loop (limite N passos):
    resp = provider.chat(messages, tools=SCHEMAS)
    se resp.tool_calls:
        para cada call: resultado = TOOLS[call.name](mapspec, **call.args)
        messages += tool_results
    senão:  # texto final / finalizar
        break
validar(mapspec); render(mapspec)
```

### Módulos novos (planejados)

- `core/nexomap_tools.py` — implementação das tools + `TOOL_SCHEMAS` (lista JSON Schema).
- `core/nexomap_agent.py` — loop de orquestração (IA↔tools), com limite de passos e logging.
- `nexomap_ai.py` — adicionar `run_tools(...)` que usa o campo `tools`/`tool_choice` da API.

## Checklist de implementação

- [ ] Especificar `TOOL_SCHEMAS` (JSON Schema de cada tool) em `core/nexomap_tools.py`.
- [ ] Implementar cada tool como função pura `tool(mapspec_dict, **args) -> (mapspec_dict, msg)`.
- [ ] Reaproveitar validações de `mapspec.py` dentro de cada tool (rejeitar camada/elemento inválido).
- [ ] Implementar `core/nexomap_agent.py` com o loop IA↔tools + limite de passos + timeout.
- [ ] Adicionar `run_tools()` em `nexomap_ai.py` (campo `tools`, `tool_choice:"auto"`).
- [ ] Fallback sem IA: mapear frases comuns → sequência de tools (reusar `apply_rule_based_edit`).
- [ ] Registrar cada tool_call no `chat_history.jsonl` e na linhagem de versões.
- [ ] Endpoint `POST /api/nexomap/chat-tools` (ver plano 05).

## Plano de testes

**Unit (`tests/test_tools.py`)**
- [ ] Cada tool aplica o efeito esperado e rejeita argumentos inválidos.
- [ ] `mover_elemento` altera só a posição do elemento alvo.
- [ ] `adicionar_camada`/`remover_camada` mantêm o MapSpec válido.
- [ ] Sequência de tools converge para um MapSpec válido.

**Integração (mock do provedor)**
- [ ] Simular `tool_calls` do provedor e verificar que o orquestrador aplica e encerra.
- [ ] Limite de passos respeitado; sem loop infinito.

**Ao vivo (DeepSeek, chave em secrets)**
- [ ] "Adicione embargos da SEMA e mova a legenda para o rodapé" → 2 tools corretas + render OK.

## Critérios de aceite

- IA executa edições finas via tools sem reescrever o MapSpec inteiro.
- Toda tool valida entrada e mantém o MapSpec sempre válido.
- Fallback sem IA cobre as instruções mais comuns.
- Histórico audita cada tool_call.

## Riscos e decisões abertas

- **Provedor suporta function calling?** DeepSeek é OpenAI-compatible; confirmar campo `tools`.
  Se não, manter o modo "MapSpec-diff" (atual) como caminho primário e tools como açúcar.
- **Passos/custo:** limitar nº de passos e `max_tokens`; `thinking` desligado para tools.

## Dependências

- Plano 01 (posição de elementos) e 02 (legenda) definem os argumentos de `mover_elemento`/`editar_legenda`.
- Plano 05 (endpoints/UI) expõe o loop de tools na aba Mapas IA.
