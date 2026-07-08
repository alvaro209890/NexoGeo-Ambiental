# 07 — Plano de testes global

## Objetivo

Definir a **estratégia de testes** que sustenta a evolução da IA cartográfica: unit rápidos e
offline, integração com rede marcada como opcional, testes visuais e testes ao vivo com o DeepSeek.
Meta: `pytest`/`unittest` sempre verde no `main`; regressões visuais pegas cedo.

## Estado atual

- `tests/` tem 25 testes (unittest) passando: `test_geo_formats`, `test_matriculas`,
  `test_nexomap`, `test_renderer`. Rodam **offline** (basemap desligado, sem rede).
- Falta cobertura para: tools, layout/posição, legenda, quantitativos, WMS/GML, validação avançada,
  API nexomap e edição versionada.

## Escopo

**Inclui**
- Novos arquivos de teste por plano (unit + integração).
- Convenção para **testes com rede** (marcados/pulados por padrão).
- **Fixtures** pequenas versionadas (shape/GeoJSON/GML/TIF minúsculos) em `tests/fixtures/`.
- Teste de **regressão visual** (hash/estrutura do PNG, não pixel-perfeito).
- Runner e comando único documentado.

**Não inclui**
- CI em nuvem (pode vir depois; por ora, rodar local no Python311).

## Design / contrato

### Camadas de teste

| Camada | Onde | Rede? | Exemplos |
|--------|------|-------|----------|
| Unit | `tests/test_*.py` | não | tools, layout, legenda, quantitativos, mapspec, validação |
| Integração local | `tests/test_pipeline.py` | não | `generate()`/`edit_map()` com fixture + raster fixo |
| Integração rede | `tests/net/test_*_net.py` | **sim** (skip default) | WFS SEMA, GML INCRA, WMS IBAMA |
| Ao vivo IA | `tests/live/test_deepseek.py` | sim + chave | gerar/editar via DeepSeek |
| Visual | `tests/test_visual.py` | não | estrutura do PNG (tamanho, regiões não vazias) |

### Convenções

- Testes com rede: `@unittest.skipUnless(os.environ.get("NEXO_NET"), "rede")`.
- Testes ao vivo: `@unittest.skipUnless(os.environ.get("DEEPSEEK_API_KEY"), "sem chave")` —
  **nunca** hardcodar chave; ler de env/secrets.
- Fixtures minúsculas e determinísticas; nada de dado de fazenda real versionado.

### Fixtures a criar (`tests/fixtures/`)

- [ ] `area_quadrado.zip` (1 km², já gerado em memória hoje → materializar).
- [ ] `camada.geojson` e `camada.gml` (poucas feições) para parsers.
- [ ] `raster_min.tif` (GeoTIFF minúsculo com georreferência conhecida) para `core/raster.py`.

## Checklist de implementação

- [ ] `tests/fixtures/` com shape/geojson/gml/tif mínimos + `.prj`.
- [ ] `tests/test_tools.py` (plano 00).
- [ ] `tests/test_layout.py` (plano 01).
- [ ] `tests/test_legenda.py` (plano 02).
- [ ] `tests/test_layers.py` + `tests/net/test_layers_net.py` (plano 03).
- [ ] `tests/test_quantitativos.py` (plano 04).
- [ ] `tests/test_api_nexomap.py` (plano 05).
- [ ] `tests/test_validacao.py` (plano 06).
- [ ] `tests/test_raster.py` (para `core/raster.py`, com `raster_min.tif`).
- [ ] `tests/test_visual.py` (regressão estrutural do PNG).
- [ ] Documentar comando único no README dos planos e no DESENVOLVIMENTO.md.

## Comando padrão

```powershell
$py = "C:\Users\Usuario\AppData\Local\Programs\Python\Python311\python.exe"
$env:PYTHONPATH = "C:\GIS\NexoGeo-Ambiental"
& $py -m pytest tests -q                    # offline (default)
$env:NEXO_NET = "1"; & $py -m pytest tests/net -q   # com rede (opcional)
```

## Critérios de aceite

- Suite offline verde no `main` a cada mudança.
- Testes de rede/ao vivo isolados e puláveis (não quebram o CI local sem rede/chave).
- Cada plano (00–06, 08) tem cobertura mínima antes de ser marcado concluído.

## Riscos e decisões abertas

- **Regressão visual** sem flakiness: comparar **estrutura** (regiões não vazias, presença de
  elementos) em vez de pixels exatos (fontes/versões de matplotlib variam).
- **Segredos em teste**: sempre via env/secrets; garantir que fixtures não vazem chave.

## Dependências

- Todos os planos contribuem seus testes aqui.
