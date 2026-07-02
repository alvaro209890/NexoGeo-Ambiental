# NexoMap AI - Handoff para Continuidade

## Estado Atual

O NexoMap AI nao e mais um app separado. Ele e uma aba chamada **Mapas IA** dentro do
NexoGeo Ambiental.

O usuario continua abrindo o `projeto.json` normal da analise. Quando a aba Mapas IA e usada,
o backend cria/atualiza um contrato interno em:

```text
<raiz da analise>/.nexomap/projeto.nexomap.json
```

As saidas de mapas ficam em:

```text
<pasta Resultados da analise>/Mapas_IA/<job_id>/
```

Arquivos gerados por job:

- `mapspec.json`
- `mapa.pdf`
- `preview.png`
- `png_validacao.png`
- `validacao.json`
- `resultado.json`
- `mapa.mxd` somente quando ArcMap/template real estiver configurado

## Arquivos Principais

- `ui/src/App.jsx`: composicao da UI. A aba integrada e `MapsAiView`.
- `api/app.py`: endpoints FastAPI antigos e endpoints `/api/nexomap/*`.
- `core/nexomap_project.py`: contrato de projeto NexoMap e ponte `ensure_project_from_analysis`.
- `core/mapspec.py`: modelo, fallback local e validacao do `MapSpec`.
- `core/nexomap_ai.py`: adaptador de IA OpenAI-compatible/DeepSeek.
- `core/nexomap_generator.py`: orquestracao chat/MapSpec/render/validacao/ArcGIS.
- `core/nexomap_renderer.py`: render PDF/PNG sem ArcGIS.
- `core/nexomap_validation.py`: validacao visual basica com PyMuPDF.
- `core/arcgis_bridge.py`: ponte conservadora para ArcMap/ArcPy.
- `catalogo/camadas.json`: camadas que a IA pode usar.
- `templates/mxd/MANIFEST.json`: templates MXD permitidos.
- `templates/mxd/scripts/export_mxd.py`: script ArcPy chamado por subprocess.
- `schema/mapspec.schema.json`: schema do MapSpec.
- `schema/nexomap_project.schema.json`: schema do contrato interno NexoMap.
- `PLANO_NEXOMAP_AI.md`: checklist macro do modulo.

## Endpoints

### Ponte analise -> Mapas IA

```http
POST /api/nexomap/from-analysis
{
  "analysis_path": "C:\\...\\projeto.json",
  "area_path": "C:\\...\\area.zip"
}
```

Cria/atualiza `.nexomap/projeto.nexomap.json` usando dados do projeto de analise.

### Chat -> MapSpec

```http
POST /api/nexomap/chat
{
  "path": "C:\\...\\.nexomap\\projeto.nexomap.json",
  "prompt": "Gere um mapa com CAR e embargos",
  "allow_local_fallback": true
}
```

Sem chave de IA, usa fallback local deterministico. Com chave, chama o provedor configurado.

### Geracao

```http
POST /api/nexomap/generate
{
  "path": "C:\\...\\.nexomap\\projeto.nexomap.json",
  "mapspec": { "...": "..." },
  "strict_mxd": false
}
```

Retorna SSE. `strict_mxd=false` permite PDF/PNG validado mesmo sem ArcMap/template real.

### Resultados e arquivos

```http
GET /api/nexomap/resultados?path=<projeto.nexomap.json>
GET /api/nexomap/file?path=<png-ou-pdf-local>
GET /api/nexomap/doctor?path=<projeto.nexomap.json>
```

## Contratos de Dados

### Projeto de analise

Continua sendo o `schema/projeto.schema.json` existente. A aba Mapas IA nao deve substituir
esse arquivo.

### Projeto NexoMap interno

Gerado por `ensure_project_from_analysis()` em `core/nexomap_project.py`.

Campos importantes:

- `nome`, `cliente`, `municipio`, `crs`: herdados do projeto de analise.
- `raiz_dados`: raiz real da analise.
- `pastas.mapas`: `Automacoes/Resultados/Mapas_IA` ou equivalente da configuracao da analise.
- `area_base.path`: zip selecionado na aba Pre-Analise/Mapas IA.
- `metadata.analysis_project`: caminho do projeto de analise original.

### MapSpec

A IA so pode retornar JSON. O validador rejeita:

- `layout_template` inexistente no manifesto;
- camada inexistente em `catalogo/camadas.json`;
- `area_base` diferente de `projeto.area_base`;
- saidas fora de `mxd`, `pdf`, `png_validacao`.

## Segredos

Credenciais devem ficar no `secrets.local.json` da analise, nunca no codigo.

Chaves reconhecidas:

```json
{
  "sema_authkey": "...",
  "planet_api_key": "...",
  "deepseek_api_key": "...",
  "nexomap_ai_provider": "deepseek",
  "nexomap_deepseek_model": "deepseek-chat",
  "arcgis_python": "C:\\Python27\\ArcGIS10.8\\python.exe"
}
```

`core/llm/deepseek.py` nao deve voltar a ter chave hardcoded.

## Validacao Atual

Comandos que devem continuar passando:

```powershell
& "C:\Users\Usuario\AppData\Local\Programs\Python\Python311\python.exe" -m unittest discover -s tests -v
cd ui
npm run build
```

Smoke manual recomendado:

1. Rodar `python -m uvicorn api.app:app --host 127.0.0.1 --port 8000`.
2. Abrir `http://127.0.0.1:8000`.
3. Abrir um projeto de analise.
4. Selecionar ZIP na aba Pre-Analise.
5. Ir em Mapas IA -> Preparar aba -> Criar MapSpec -> Gerar mapa.
6. Verificar `VALIDADO` no preview e arquivos em `Resultados/Mapas_IA/<job_id>/`.

## Limitacoes Conhecidas

- O render proprio ainda desenha somente o perimetro base; camadas externas entram no
  `MapSpec` e na legenda/validacao, mas o download/recorte WFS ainda precisa ser implementado.
- `mapa.mxd` real depende de templates `.mxd` reais em `templates/mxd/` e ArcMap 10.x.
- `validacao.json` faz validacao basica: PDF abre, pagina existe, titulo aparece, PNG e
  pagina nao vazia. Validacao geometrica avancada ainda esta pendente.
- A UI usa parser local quando nao ha chave de IA. Isso e intencional para desenvolvimento.

## Proximas Tarefas Recomendadas

1. Implementar download/recorte WFS por bbox em `core/nexomap_renderer.py` ou modulo dedicado.
2. Copiar templates `.mxd` reais para `templates/mxd/` e atualizar `MANIFEST.json`.
3. Melhorar `templates/mxd/scripts/export_mxd.py` para repontar workspaces, ajustar extent,
   legenda, metadados e minimapa.
4. Expandir `core/nexomap_validation.py` para checar legenda/norte/perimetro por regioes de imagem.
5. Refatorar `ui/src/App.jsx` em componentes por aba quando a interface estabilizar.
6. Adicionar testes de ponta a ponta com shapefile fixture versionado pequeno.
