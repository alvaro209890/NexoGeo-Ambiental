# Software de Análise de Área

Aplicativo Windows para rodar as automações de análise fundiária/ambiental em **várias
análises / vários imóveis**, dirigido por configuração. **Não contém dados de nenhuma
fazenda** — cada análise é descrita por um `projeto.json` que vive junto com os dados da
análise (não dentro deste repositório).

> Plano completo, inventário de serviços WMS/WFS e roadmap: [`PLANO_SOFTWARE.md`](PLANO_SOFTWARE.md).
> Diário de desenvolvimento: [`DESENVOLVIMENTO.md`](DESENVOLVIMENTO.md).

## Princípio: software genérico, dados externos

```
   ESTE REPOSITÓRIO (genérico)              SUA ANÁLISE (dados + config)
   software/                                 <pasta da análise>/
     core/        código reutilizável          projeto.json        <- descreve a análise
     catalogo/    serviços WMS/WFS              secrets.local.json  <- credenciais (não versionar)
     schema/      validação do projeto.json     Shapes/  Consultas_Publicas/  ...
     exemplos/    template + secrets exemplo
```

O `projeto.json` aponta para a raiz dos dados por `raiz_dados` (use `"."` quando ele fica na
raiz da própria análise). Assim o mesmo software roda qualquer imóvel.

## Decisões de stack (v1)

- **Backend / lógica:** Python 3.11 (reaproveita as automações existentes).
- **API local:** FastAPI (Fase 4).
- **Front-end:** React + Vite + TailwindCSS + MapLibre (Fase 4).
- **Shell desktop:** pywebview (WebView2) → `.exe` via PyInstaller (Fase 7).
- **Escopo v1:** geradores parametrizados (quantitativos, ctx ambiental, ctx fundiário,
  área total, APF) + UI de projeto/automações/resultados. Mapas e restrições/desmatamento → v2.

## Estrutura

```
software/
  core/                 # biblioteca reutilizável (genérica, sem dado de imóvel)
    config.py           # esquema + carga do projeto.json            [Fase 0 ✓]
    geo.py              # reprojeção (via .prj) + atribuição espacial [Fase 1 ✓]
    io.py               # convenção única de saída (Resultados/)      [Fase 1 ✓]
    xlsx_builder.py     # estilo padrão das planilhas (.xlsx)         [Fase 1 ✓]
    docx_builder.py     # estilo padrão dos documentos (.docx)        [Fase 1 ✓]
    normalize.py        # nomes, CNPJ, números/datas BR               [Fase 1 ✓]
    recibo.py           # parser do recibo PDF do CAR                 [Fase 1 ✓]
    secrets.py          # carga de secrets.local.json                 [Fase 1 ✓]
    clients/            # http, sema, incra, apf_rural (WFS/scraping) [Fase 1 ✓]
  automations/          # orquestradores finos por automação
    quantitativos.py    # área cultivável por CAR -> .xlsx            [Fase 2 ✓]
    area_total.py       # certificação × matrícula -> .docx           [Fase 2 ✓]
    ctx_ambiental.py    # situação CAR + APF + recibo -> .docx        [Fase 2 ✓]
    ctx_fundiario.py    # certificações INCRA -> .docx                [Fase 2 ✓]
    apf.py              # consulta APF SEMA -> .xlsx (+ PDFs)         [Fase 2 ✓]
  api/                  # FastAPI: validar/rodar (SSE)/resultados     [Fase 4 ✓]
  ui/                   # React + Vite + Tailwind (dist é servido)     [Fase 4 ✓]
  app.py                # shell pywebview (sobe API + abre janela)     [Fase 4 ✓]
  catalogo/
    servicos_geo.json   # catálogo de WMS/WFS (reutilizável)          [✓]
  schema/
    projeto.schema.json # JSON Schema do projeto.json                 [✓]
  exemplos/
    projeto.template.json   # template genérico (sem dado real)       [✓]
    secrets.example.json    # modelo de segredos                       [✓]
  requirements.txt
```

## Como rodar (validação — Fase 0)

Só usa a biblioteca padrão do Python — roda sem instalar nada. Aponte para o `projeto.json`
da sua análise (no exemplo, a análise está um nível acima):

```powershell
cd software
& "C:\Users\Usuario\AppData\Local\Programs\Python\Python311\python.exe" -m core.config ..\projeto.json
```

Carrega e valida o `projeto.json`, resolve as pastas de dados e lista as fazendas, indicando
se cada shapefile do CAR foi encontrado.

## Rodar as automações (Fase 2)

Cada automação roda isolada por linha de comando (a partir de `software/`), recebendo o
`projeto.json` e, opcionalmente, um caminho de saída (por padrão grava em `Resultados/`):

```powershell
python -m automations.quantitativos  ..\projeto.json   # área cultivável por CAR -> .xlsx
python -m automations.area_total     ..\projeto.json   # certificação × matrícula -> .docx
python -m automations.ctx_ambiental  ..\projeto.json   # situação CAR + APF + recibo -> .docx
python -m automations.ctx_fundiario  ..\projeto.json   # certificações INCRA -> .docx
python -m automations.apf            ..\projeto.json --pdfs   # APFs -> .xlsx (+ baixa PDFs)
```

- `ctx_ambiental`, `ctx_fundiario` e `apf` fazem **requisições externas** (SEMA, INCRA).
  Para a situação do CAR (`ctx_ambiental`), preencha `secrets.local.json` com a `sema_authkey` —
  sem ela, a automação degrada (proprietários do `.dbf`, situação "—").

## Rodar o aplicativo (Fase 4)

**Desenvolvimento** (hot-reload do front):

```powershell
# terminal 1 — API
cd software
python -m uvicorn api.app:app --port 8000
# terminal 2 — UI (http://localhost:5173, com proxy /api -> 8000)
cd software\ui
npm install
npm run dev
```

**Janela do app** (UI buildada servida pela API, em janela pywebview):

```powershell
cd software\ui ; npm run build      # gera ui/dist
cd ..                               # software/
pip install pywebview
python app.py                       # abre a janela do programa
```

Sem `pywebview`, o `app.py` mantém o servidor no ar e você abre `http://127.0.0.1:8000`.

## Criar uma nova análise

1. Crie a pasta da análise com os dados (`Shapes/`, `Shapes/CAR/`, `Consultas_Publicas/`).
2. Copie `software/exemplos/projeto.template.json` para `<análise>/projeto.json` e preencha.
3. (Opcional) Copie `software/exemplos/secrets.example.json` para `<análise>/secrets.local.json`
   e preencha as credenciais (authkey SEMA / api_key Planet).
4. Valide: `python -m core.config <caminho>\projeto.json`.

## Segredos

Credenciais **não** entram no código nem no `projeto.json`. Ficam em `secrets.local.json`
(ignorado pelo Git), na pasta da análise.

## Próximas fases

Ver [`DESENVOLVIMENTO.md`](DESENVOLVIMENTO.md) para o estado atual e o que vem a seguir.
