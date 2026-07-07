import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Archive,
  ArrowLeft,
  BookOpen,
  Bot,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Cpu,
  FileJson,
  FileText,
  FolderOpen,
  Gauge,
  Globe2,
  Image as ImageIcon,
  Layers,
  Loader2,
  Map,
  MapPin,
  MessageSquareText,
  MonitorCog,
  Play,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  UploadCloud,
  XCircle,
} from 'lucide-react'
import './index.css'

const API = ''

const NAV = [
  { id: 'pre', label: 'Pre-Analise', icon: MapPin },
  { id: 'maps_ai', label: 'Mapas IA', icon: MessageSquareText },
  { id: 'automations', label: 'Automacoes', icon: Activity },
  { id: 'results', label: 'Resultados', icon: Archive },
  { id: 'doctor', label: 'Doctor', icon: MonitorCog },
  { id: 'manual', label: 'Manual', icon: BookOpen },
]

const DEFAULT_PROMPTS = [
  'Gere um mapa com imagem de satelite, perimetro, CAR e embargos ambientais',
  'Monte um mapa de alertas MapBiomas e desmatamento PRODES',
  'Gere um mapa de terras indigenas e unidades de conservacao proximas',
]

async function jget(url) {
  const response = await fetch(API + url)
  if (!response.ok) throw new Error(await response.text())
  return response.json()
}

async function jpost(url, body) {
  const response = await fetch(API + url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json()
}

function cleanError(error) {
  const raw = error?.message || String(error)
  try {
    const parsed = JSON.parse(raw)
    return parsed.detail || raw
  } catch {
    return raw
  }
}

function fileName(path) {
  if (!path) return '-'
  const parts = String(path).split(/[\\/]/)
  return parts[parts.length - 1] || path
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatHa(value) {
  if (!Number.isFinite(Number(value))) return '-'
  return `${Number(value).toLocaleString('pt-BR', { minimumFractionDigits: 4, maximumFractionDigits: 4 })} ha`
}

function statusCopy(status) {
  if (status === 'done' || status === true || status === 'ok') return 'OK'
  if (status === 'error' || status === false) return 'Erro'
  if (status === 'started' || status === 'progress') return 'Rodando'
  return status || 'Aguardando'
}

function StatusBadge({ state = 'idle', children }) {
  const ok = state === true || state === 'ok' || state === 'done'
  const error = state === false || state === 'error'
  const active = state === 'started' || state === 'progress'
  const Icon = ok ? CheckCircle2 : error ? XCircle : active ? Loader2 : Gauge
  return (
    <span className={`status-badge ${ok ? 'status-ok' : error ? 'status-error' : active ? 'status-started' : ''}`}>
      <Icon size={15} className={active ? 'spin' : ''} />
      {children || statusCopy(state)}
    </span>
  )
}

function IconButton({ title, onClick, disabled, children, kind = 'soft' }) {
  return (
    <button className={`icon-button ${kind}`} type="button" title={title} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  )
}

function PrimaryButton({ children, onClick, disabled, tone = 'primary' }) {
  return (
    <button className={`primary-button ${tone}`} type="button" onClick={onClick} disabled={disabled}>
      {children}
    </button>
  )
}

function Field({ label, value, onChange, icon: Icon, onBrowse, placeholder, readOnly }) {
  return (
    <label className="field">
      <span>{label}</span>
      <div className="field-group">
        <div className="field-input">
          {Icon ? <Icon size={17} /> : null}
          <input value={value || ''} onChange={(event) => onChange?.(event.target.value)} placeholder={placeholder} readOnly={readOnly} />
        </div>
        {onBrowse ? (
          <IconButton title="Selecionar" onClick={onBrowse}>
            <FolderOpen size={18} />
          </IconButton>
        ) : null}
      </div>
    </label>
  )
}

function MiniStat({ icon: Icon, label, value }) {
  return (
    <div className="mini-stat">
      <div className="mini-stat-icon">{Icon ? <Icon size={18} /> : null}</div>
      <div>
        <strong>{value}</strong>
        <span>{label}</span>
      </div>
    </div>
  )
}

function ErrorBox({ children }) {
  return (
    <div className="error-box">
      <AlertTriangle size={18} />
      <span>{children}</span>
    </div>
  )
}

function NewAnalysisForm({ onCancel, onCreate }) {
  const [nome, setNome] = useState('')
  const [cliente, setCliente] = useState('')
  const [destino, setDestino] = useState('')
  const [busy, setBusy] = useState(false)
  const [erro, setErro] = useState('')

  async function create() {
    if (!nome.trim() || !destino.trim()) {
      setErro('Informe nome e pasta de destino.')
      return
    }
    setBusy(true)
    setErro('')
    try {
      const result = await jpost('/api/projeto/novo', { nome, cliente, destino })
      onCreate(result.path)
    } catch (error) {
      setErro(cleanError(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop">
      <section className="modal-content">
        <header>
          <h2>Novo projeto de analise</h2>
          <p>Cria a estrutura base do NexoGeo Ambiental.</p>
        </header>
        <Field label="Nome do imovel" value={nome} onChange={setNome} placeholder="Fazenda Exemplo" icon={Map} />
        <Field label="Cliente" value={cliente} onChange={setCliente} placeholder="Cliente" icon={ShieldCheck} />
        <Field
          label="Pasta de destino"
          value={destino}
          onChange={setDestino}
          icon={FolderOpen}
          onBrowse={async () => {
            const result = await jget('/api/dialog/folder')
            if (result.path) setDestino(result.path)
          }}
        />
        {erro ? <ErrorBox>{erro}</ErrorBox> : null}
        <footer className="modal-actions">
          <button className="btn-cancel" type="button" onClick={onCancel} disabled={busy}>Cancelar</button>
          <PrimaryButton onClick={create} disabled={busy} tone="solid">
            {busy ? <Loader2 size={18} className="spin" /> : <Plus size={18} />}
            Criar
          </PrimaryButton>
        </footer>
      </section>
    </div>
  )
}

function ProjectsLobby({ recentes, onOpen, onNew, erro }) {
  return (
    <main className="lobby">
      <section className="lobby-header">
        <div className="brand-mark large"><Globe2 size={34} /></div>
        <h1>NexoGeo Ambiental</h1>
        <p>Analise fundiaria e ambiental com automacoes, pre-analise e mapas por IA no mesmo projeto.</p>
      </section>
      <section className="recent-grid">
        <button className="recent-card new-card" type="button" onClick={onNew}>
          <Plus size={28} />
          <strong>Criar analise</strong>
        </button>
        <button className="recent-card" type="button" onClick={async () => {
          const result = await jget('/api/dialog/file')
          if (result.path) onOpen(result.path)
        }}>
          <FolderOpen size={24} className="folder-icon" />
          <div className="rc-content">
            <strong>Abrir projeto.json</strong>
            <span>Selecionar projeto de analise</span>
          </div>
          <ChevronRight size={20} className="arrow-icon" />
        </button>
        {recentes.map((item) => (
          <button className="recent-card" type="button" key={item.path} onClick={() => onOpen(item.path)}>
            <FileJson size={24} className="folder-icon" />
            <div className="rc-content">
              <strong>{item.nome}</strong>
              <span>{item.path}</span>
            </div>
            <ChevronRight size={20} className="arrow-icon" />
          </button>
        ))}
      </section>
      {erro ? <div className="floating-error"><AlertTriangle size={18} /><span>{erro}</span></div> : null}
    </main>
  )
}

function MapCanvas({ project, result, running }) {
  const image = result?.outputs?.png_validacao || result?.outputs?.preview_png
  return (
    <section className="map-canvas">
      {image ? (
        <img src={`/api/nexomap/file?path=${encodeURIComponent(image)}`} alt="" onError={(event) => { event.currentTarget.style.display = 'none' }} />
      ) : null}
      <div className="map-canvas-grid" />
      <div className="map-canvas-content">
        <div className="map-canvas-top">
          <span>{project?.municipio?.nome || 'Projeto'} / {project?.municipio?.uf || 'MT'}</span>
          <StatusBadge state={running ? 'progress' : result?.ok ? 'ok' : 'idle'}>
            {running ? 'Gerando' : result?.ok ? 'Validado' : 'Pronto'}
          </StatusBadge>
        </div>
        <div className="map-canvas-title">
          <strong>{result?.mapspec?.titulo || project?.nome || 'Mapas IA'}</strong>
          <span>{result?.job_id || 'Aguardando prompt cartografico'}</span>
        </div>
      </div>
    </section>
  )
}

function SpecPanel({ chatResult, result }) {
  const spec = chatResult?.mapspec || result?.mapspec
  const warnings = [...(chatResult?.warnings || []), ...(result?.warnings || [])]
  return (
    <aside className="spec-panel">
      <div className="section-title">
        <FileJson size={18} />
        <span>MapSpec</span>
      </div>
      {spec ? (
        <pre className="json-view">{JSON.stringify(spec, null, 2)}</pre>
      ) : (
        <div className="empty-inline"><Bot size={24} /><span>O JSON validado aparece aqui depois do chat.</span></div>
      )}
      {warnings.length ? (
        <div className="warning-list">
          {warnings.map((warning, index) => (
            <div key={`${warning}-${index}`}>
              <AlertTriangle size={15} />
              <span>{warning}</span>
            </div>
          ))}
        </div>
      ) : null}
    </aside>
  )
}

function PreAnalysisView({ project, resumo, preShape, setPreShape, preOut, setPreOut, preStatus, running, erro, onPreview, onRun, results }) {
  return (
    <div className="project-grid">
      <section className="view-stack">
        <section className="map-canvas compact-map">
          <div className="map-canvas-grid" />
          <div className="map-canvas-content">
            <div className="map-canvas-top">
              <span>{project?.municipio?.nome || 'Projeto'} / {project?.municipio?.uf || 'MT'}</span>
              <StatusBadge state={resumo ? 'ok' : 'idle'}>{resumo ? 'Geometria lida' : 'Aguardando'}</StatusBadge>
            </div>
            <div className="map-canvas-title">
              <strong>{project?.imovel || 'Pre-Analise ambiental'}</strong>
              <span>{resumo?.bbox_geo ? resumo.bbox_geo.map((n) => Number(n).toFixed(4)).join(' / ') : 'Sem bbox'}</span>
            </div>
          </div>
        </section>
        <section className="work-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Fluxo principal</span>
              <h1>Pre-Analise ambiental</h1>
            </div>
            <StatusBadge state={running ? 'progress' : preStatus?.arquivo ? 'ok' : 'idle'}>
              {running ? 'Processando' : preStatus?.arquivo ? 'DOCX pronto' : 'Aguardando'}
            </StatusBadge>
          </div>
          <div className="analysis-grid">
            <Field
              label="Geometria da area (.zip, .shp, .geojson, .kml, .kmz)"
              value={preShape}
              onChange={setPreShape}
              icon={UploadCloud}
              onBrowse={async () => {
                const result = await jget('/api/dialog/file')
                if (result.path) setPreShape(result.path)
              }}
            />
            <Field
              label="Pasta de saida"
              value={preOut}
              onChange={setPreOut}
              icon={FolderOpen}
              onBrowse={async () => {
                const result = await jget('/api/dialog/folder')
                if (result.path) setPreOut(result.path)
              }}
            />
          </div>
          <div className="action-row">
            <PrimaryButton onClick={onPreview} disabled={running}>
              <Gauge size={18} />
              Conferir geometria
            </PrimaryButton>
            <PrimaryButton onClick={onRun} disabled={running} tone="solid">
              {running ? <Loader2 size={18} className="spin" /> : <Play size={18} />}
              Gerar Word
            </PrimaryButton>
          </div>
          {erro ? <ErrorBox>{erro}</ErrorBox> : null}
        </section>
      </section>
      <aside className="spec-panel">
        <div className="section-title"><ShieldCheck size={18} /><span>Projeto</span></div>
        <dl className="detail-list">
          <div><dt>Cliente</dt><dd>{project?.cliente || '-'}</dd></div>
          <div><dt>Imovel</dt><dd>{project?.imovel || '-'}</dd></div>
          <div><dt>Data</dt><dd>{project?.data_consulta || '-'}</dd></div>
          <div><dt>CRS</dt><dd>{project?.crs_utm || '-'}</dd></div>
        </dl>
        <div className="metric-grid">
          <MiniStat icon={Layers} label="Area" value={formatHa(resumo?.area_ha)} />
          <MiniStat icon={MapPin} label="Poligonos" value={resumo?.feature_count || resumo?.poligonos || '-'} />
        </div>
        {resumo?.fazendas_intersectadas?.length ? (
          <div className="folder-list">
            {resumo.fazendas_intersectadas.map((fz) => (
              <div className="folder-row" key={fz.id}><span>{fz.nome}</span><strong>CAR</strong></div>
            ))}
          </div>
        ) : null}
        {resumo?.avisos?.length ? (
          <div className="warning-list">
            {resumo.avisos.map((warning, index) => (
              <div key={`${warning}-${index}`}>
                <AlertTriangle size={15} />
                <span>{warning}</span>
              </div>
            ))}
          </div>
        ) : null}
        <div className="section-title"><FileText size={18} /><span>Recentes</span></div>
        <div className="folder-list">
          {results.slice(0, 4).map((item) => (
            <div className="folder-row" key={item.path}>
              <span>{item.nome}</span>
              <strong>{formatBytes(item.tamanho)}</strong>
            </div>
          ))}
          {!results.length ? <p className="muted">Nenhum resultado listado.</p> : null}
        </div>
      </aside>
    </div>
  )
}

function MapsAiView({ analysisPath, preShape, mapProject, setMapProject, chatResult, setChatResult, mapResult, setMapResult, mapResults, setMapResults }) {
  const [prompt, setPrompt] = useState(DEFAULT_PROMPTS[0])
  const [running, setRunning] = useState(false)
  const [erro, setErro] = useState('')
  const [events, setEvents] = useState([])

  async function prepare() {
    if (!analysisPath) return null
    setErro('')
    try {
      const result = await jpost('/api/nexomap/from-analysis', {
        analysis_path: analysisPath,
        area_path: preShape || null,
      })
      setMapProject(result.project)
      await refreshResults(result.path)
      return result.project
    } catch (error) {
      setErro(cleanError(error))
      return null
    }
  }

  async function refreshResults(projectPath = mapProject?.arquivo) {
    if (!projectPath) return
    const data = await jget(`/api/nexomap/resultados?path=${encodeURIComponent(projectPath)}`).catch(() => [])
    setMapResults(data)
  }

  async function interpret() {
    const project = mapProject || await prepare()
    if (!project || !prompt.trim()) return
    setErro('')
    try {
      const result = await jpost('/api/nexomap/chat', { path: project.arquivo, prompt, allow_local_fallback: true })
      setChatResult(result)
      setEvents((old) => [...old, { status: 'done', stage: 'mapspec', text: `MapSpec criado por ${result.provider}` }])
    } catch (error) {
      setErro(cleanError(error))
    }
  }

  async function generate() {
    const project = mapProject || await prepare()
    if (!project) return
    setRunning(true)
    setErro('')
    setEvents([])
    try {
      const body = chatResult?.mapspec
        ? { path: project.arquivo, mapspec: chatResult.mapspec }
        : { path: project.arquivo, prompt }
      const response = await fetch(API + '/api/nexomap/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!response.ok || !response.body) throw new Error(await response.text())
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const chunks = buffer.split('\n\n')
        buffer = chunks.pop() || ''
        for (const chunk of chunks) {
          const line = chunk.split('\n').find((entry) => entry.startsWith('data: '))
          if (!line) continue
          const event = JSON.parse(line.slice(6))
          setEvents((old) => [...old, event])
          if (event.status === 'done') {
            setMapResult(event.result)
            setChatResult({ provider: event.result.provider, warnings: event.result.warnings, mapspec: event.result.mapspec })
          }
          if (event.status === 'error') setErro(event.erro)
        }
      }
      await refreshResults(project.arquivo)
    } catch (error) {
      setErro(cleanError(error))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="chat-grid">
      <div className="chat-main">
        <MapCanvas project={mapProject} result={mapResult} running={running} />
        <section className="work-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Mapas IA</span>
              <h1>Descreva o mapa</h1>
            </div>
            <StatusBadge state={running ? 'progress' : mapResult?.ok ? 'ok' : mapProject?.area_base?.exists ? 'ok' : 'idle'}>
              {running ? 'Gerando' : mapResult?.ok ? 'Validado' : mapProject?.area_base?.exists ? 'Preparado' : 'Aguardando'}
            </StatusBadge>
          </div>
          <Field label="Area base usada pela aba" value={preShape || mapProject?.area_base?.path || ''} icon={UploadCloud} readOnly />
          <textarea
            className="prompt-box"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Ex: Gere um mapa com imagem de satelite, perimetro, CAR e embargos ambientais."
          />
          <div className="example-row">
            {DEFAULT_PROMPTS.map((example) => (
              <button type="button" key={example} onClick={() => setPrompt(example)}>{example}</button>
            ))}
          </div>
          <div className="action-row">
            <PrimaryButton onClick={prepare} disabled={running || !analysisPath}>
              <Save size={18} />
              Preparar aba
            </PrimaryButton>
            <PrimaryButton onClick={interpret} disabled={running || !analysisPath}>
              <Sparkles size={18} />
              Criar MapSpec
            </PrimaryButton>
            <PrimaryButton onClick={generate} disabled={running || !analysisPath} tone="solid">
              {running ? <Loader2 size={18} className="spin" /> : <Play size={18} />}
              Gerar mapa
            </PrimaryButton>
          </div>
          {erro ? <ErrorBox>{erro}</ErrorBox> : null}
        </section>
        <section className="work-panel">
          <div className="section-title"><TerminalSquare size={18} /><span>Progresso</span></div>
          <div className="timeline">
            {events.length ? events.map((event, index) => (
              <div className={`timeline-row ${event.status === 'error' ? 'error' : event.status === 'done' ? 'done' : 'started'}`} key={`${event.stage}-${index}`}>
                <div className="timeline-dot">
                  {event.status === 'error' ? <XCircle size={14} /> : event.status === 'done' ? <CheckCircle2 size={14} /> : <Loader2 size={14} className="spin" />}
                </div>
                <div>
                  <strong>{event.stage || event.status}</strong>
                  <span>{event.erro || event.text || event.status}</span>
                </div>
              </div>
            )) : (
              <div className="empty-inline"><Cpu size={22} /><span>Nenhum job rodando.</span></div>
            )}
          </div>
        </section>
        <MapResultsInline results={mapResults} onRefresh={() => refreshResults()} />
      </div>
      <SpecPanel chatResult={chatResult} result={mapResult} />
    </div>
  )
}

function MapResultsInline({ results, onRefresh }) {
  return (
    <section className="work-panel">
      <div className="panel-heading slim">
        <div className="section-title"><ImageIcon size={18} /><span>Mapas gerados</span></div>
        <IconButton title="Atualizar mapas" onClick={onRefresh}><RefreshCw size={18} /></IconButton>
      </div>
      <div className="results-list compact-results">
        {results.length ? results.slice(0, 4).map((job) => (
          <article className="result-card" key={job.job_id}>
            <div className="file-mark"><FileText size={18} /></div>
            <div className="result-main">
              <strong>{job.titulo}</strong>
              <span>{job.job_dir}</span>
              {job.warnings?.length ? <small>{job.warnings[0]}</small> : null}
            </div>
            <StatusBadge state={job.ok ? 'ok' : 'error'}>{job.ok ? 'Validado' : 'Aviso'}</StatusBadge>
            <div className="result-actions">
              {['pdf', 'png_validacao', 'camadas', 'validacao'].map((key) => job.outputs?.[key] ? (
                <button type="button" key={key} onClick={() => jpost('/api/abrir', { alvo: job.outputs[key] })}>{key}</button>
              ) : null)}
              <button type="button" onClick={() => jpost('/api/abrir', { alvo: job.job_dir })}>pasta</button>
            </div>
          </article>
        )) : (
          <div className="empty-inline"><ImageIcon size={22} /><span>Nenhum mapa gerado nesta analise.</span></div>
        )}
      </div>
    </section>
  )
}

function AutomationGrid({ autos, selected, setSelected, progress, running, onRun }) {
  const selectedCount = Object.values(selected).filter(Boolean).length
  return (
    <section className="view-stack">
      <div className="section-header">
        <div>
          <span className="eyebrow">Execucoes auxiliares</span>
          <h1>Automacoes do projeto</h1>
        </div>
        <PrimaryButton onClick={onRun} disabled={running || selectedCount === 0} tone="solid">
          {running ? <Loader2 size={18} className="spin" /> : <Play size={18} />}
          Rodar selecionadas
        </PrimaryButton>
      </div>
      <div className="automation-grid">
        {autos.map((auto) => {
          const state = progress[auto.id]?.status
          const isSelected = !!selected[auto.id]
          return (
            <button
              type="button"
              className={`automation-card ${isSelected ? 'selected' : ''}`}
              key={auto.id}
              onClick={() => setSelected((old) => ({ ...old, [auto.id]: !isSelected }))}
            >
              <div className="automation-card-header">
                <div className="automation-card-body">
                  <div className="file-mark"><ClipboardList size={18} /></div>
                  <div>
                    <strong>{auto.label}</strong>
                    <span>{auto.desc}</span>
                  </div>
                </div>
                <StatusBadge state={state === 'done' ? 'done' : state === 'error' ? 'error' : state === 'started' ? 'progress' : 'idle'}>
                  {statusCopy(state)}
                </StatusBadge>
              </div>
            </button>
          )
        })}
      </div>
    </section>
  )
}

function ResultsView({ results, mapResults, onRefresh, onRefreshMaps }) {
  return (
    <section className="view-stack">
      <div className="section-header">
        <div>
          <span className="eyebrow">Arquivos gerados</span>
          <h1>Resultados</h1>
        </div>
        <div className="action-row inline-actions">
          <IconButton title="Atualizar documentos" onClick={onRefresh}><RefreshCw size={18} /></IconButton>
          <IconButton title="Atualizar mapas" onClick={onRefreshMaps}><ImageIcon size={18} /></IconButton>
        </div>
      </div>
      <div className="results-list">
        {results.length ? results.map((item) => (
          <article className="result-card" key={item.path}>
            <div className="file-mark"><FileText size={18} /></div>
            <div className="result-main">
              <strong>{item.nome}</strong>
              <span>{item.path}</span>
            </div>
            <StatusBadge state="ok">{item.ext || 'arquivo'}</StatusBadge>
            <div className="result-actions">
              <button type="button" onClick={() => jpost('/api/abrir', { alvo: item.path })}>abrir</button>
            </div>
          </article>
        )) : null}
        {mapResults.map((job) => (
          <article className="result-card" key={job.job_id}>
            <div className="file-mark"><ImageIcon size={18} /></div>
            <div className="result-main">
              <strong>{job.titulo}</strong>
              <span>{job.job_dir}</span>
            </div>
            <StatusBadge state={job.ok ? 'ok' : 'error'}>{job.ok ? 'mapa validado' : 'mapa com aviso'}</StatusBadge>
            <div className="result-actions">
              {['pdf', 'png_validacao', 'camadas', 'validacao'].map((key) => job.outputs?.[key] ? (
                <button type="button" key={key} onClick={() => jpost('/api/abrir', { alvo: job.outputs[key] })}>{key}</button>
              ) : null)}
            </div>
          </article>
        ))}
        {!results.length && !mapResults.length ? (
          <div className="empty-state">
            <FileText size={34} />
            <strong>Nenhum resultado encontrado</strong>
            <span>Execute a Pre-Analise, automacoes ou Mapas IA.</span>
          </div>
        ) : null}
      </div>
    </section>
  )
}

function DoctorView({ doctor, onRefresh }) {
  const engine = doctor?.engine
  const deps = engine?.dependencias || {}
  return (
    <section className="view-stack">
      <div className="section-header">
        <div>
          <span className="eyebrow">Ambiente</span>
          <h1>Doctor</h1>
        </div>
        <IconButton title="Atualizar doctor" onClick={onRefresh}><RefreshCw size={18} /></IconButton>
      </div>
      <div className="doctor-grid">
        <section className="work-panel">
          <div className="section-title"><MonitorCog size={18} /><span>Motor de mapas nativo</span></div>
          <dl className="detail-list">
            <div><dt>Motor</dt><dd>{engine?.motor || '-'}</dd></div>
            <div><dt>Dependencias</dt><dd>{Object.keys(deps).length ? Object.entries(deps).map(([k, v]) => `${k}${v ? '' : ' (ausente)'}`).join(', ') : '-'}</dd></div>
            <div><dt>Saidas</dt><dd>PDF, PNG e GeoJSON (abre no QGIS) — sem ArcMap</dd></div>
            <div><dt>Status</dt><dd>{engine?.message || '-'}</dd></div>
          </dl>
        </section>
        <section className="work-panel">
          <div className="section-title"><Bot size={18} /><span>IA e API</span></div>
          <dl className="detail-list">
            <div><dt>Python API</dt><dd>{doctor?.python || '-'}</dd></div>
            <div><dt>UI dist</dt><dd>{doctor?.ui_dist ? 'build presente' : 'sem build'}</dd></div>
            <div><dt>Fallback</dt><dd>parser local ativo</dd></div>
          </dl>
        </section>
      </div>
    </section>
  )
}

function ManualView() {
  return (
    <section className="manual-layout">
      <div className="manual-intro">
        <span className="eyebrow">Manual operacional</span>
        <h1>NexoGeo Ambiental</h1>
        <p>Use Pre-Analise para gerar o Word, Automacoes para os relatórios auxiliares e Mapas IA para gerar PDF/PNG validado a partir de um prompt cartografico.</p>
      </div>
      <div className="manual-grid">
        <article className="work-panel"><h2>Dados</h2><p className="muted">O projeto de analise continua sendo o `projeto.json` normal. A aba Mapas IA cria um arquivo interno `.nexomap/projeto.nexomap.json` na pasta da analise.</p></article>
        <article className="work-panel"><h2>Saidas</h2><p className="muted">Mapas entram em `Resultados/Mapas_IA/job_id/` com `mapa.pdf`, `png_validacao.png`, `validacao.json`, `mapspec.json` e a pasta `camadas/` com GeoJSON por camada.</p></article>
        <article className="work-panel"><h2>SIG aberto</h2><p className="muted">O motor de mapas e 100% nativo (sem ArcMap): PDF em escala verdadeira com basemap, camadas WFS reais, grade UTM e minimapa. Os GeoJSON de `camadas/` abrem direto no QGIS.</p></article>
        <article className="work-panel"><h2>IA</h2><p className="muted">Sem chave configurada, a aba usa parser local deterministico para MapSpec. Com `deepseek_api_key`, usa o provedor configurado em `secrets.local.json`.</p></article>
      </div>
    </section>
  )
}

export default function App() {
  const [appView, setAppView] = useState('lobby')
  const [activeView, setActiveView] = useState('pre')
  const [recentes, setRecentes] = useState([])
  const [showNewForm, setShowNewForm] = useState(false)
  const [path, setPath] = useState('')
  const [project, setProject] = useState(null)
  const [autos, setAutos] = useState([])
  const [selected, setSelected] = useState({})
  const [progress, setProgress] = useState({})
  const [results, setResults] = useState([])
  const [running, setRunning] = useState(false)
  const [busy, setBusy] = useState(false)
  const [erro, setErro] = useState('')
  const [preShape, setPreShape] = useState('')
  const [preOut, setPreOut] = useState('')
  const [resumo, setResumo] = useState(null)
  const [preStatus, setPreStatus] = useState(null)
  const [mapProject, setMapProject] = useState(null)
  const [chatResult, setChatResult] = useState(null)
  const [mapResult, setMapResult] = useState(null)
  const [mapResults, setMapResults] = useState([])
  const [doctor, setDoctor] = useState(null)

  const activeMeta = useMemo(() => NAV.find((item) => item.id === activeView) || NAV[0], [activeView])
  const ActiveIcon = activeMeta.icon

  async function loadRecentes() {
    const cfg = await jget('/api/config').catch(() => ({ recentes: [] }))
    setRecentes(cfg.recentes || [])
  }

  async function refreshResults(projectPath = path) {
    if (!projectPath) return
    const data = await jget(`/api/resultados?path=${encodeURIComponent(projectPath)}`).catch(() => [])
    setResults(data)
  }

  async function refreshMapResults(projectPath = mapProject?.arquivo) {
    if (!projectPath) return
    const data = await jget(`/api/nexomap/resultados?path=${encodeURIComponent(projectPath)}`).catch(() => [])
    setMapResults(data)
  }

  async function refreshDoctor(mapProjectPath = mapProject?.arquivo) {
    const suffix = mapProjectPath ? `?path=${encodeURIComponent(mapProjectPath)}` : ''
    const data = await jget(`/api/nexomap/doctor${suffix}`).catch(() => null)
    setDoctor(data)
  }

  async function carregar(projetoPath) {
    setBusy(true)
    setErro('')
    try {
      const [projectData, automationList] = await Promise.all([
        jpost('/api/projeto/validar', { path: projetoPath }),
        jget('/api/automacoes'),
      ])
      setPath(projetoPath)
      setProject(projectData)
      setAutos(automationList)
      setSelected(Object.fromEntries(automationList.map((auto) => [auto.id, false])))
      setPreOut(projectData?.pastas?.resultados?.path || '')
      setPreShape('')
      setResumo(null)
      setPreStatus(null)
      setMapProject(null)
      setChatResult(null)
      setMapResult(null)
      setMapResults([])
      setActiveView('pre')
      setAppView('project')
      await Promise.all([refreshResults(projetoPath), refreshDoctor(), loadRecentes()])
    } catch (error) {
      setErro(cleanError(error))
    } finally {
      setBusy(false)
      setShowNewForm(false)
    }
  }

  async function conferirGeometria() {
    setErro('')
    try {
      const data = await jpost('/api/pre-analise/resumo', {
        path,
        shapefile_zip: preShape,
        saida_dir: preOut,
        usar_ia: false,
      })
      setResumo(data)
    } catch (error) {
      setErro(cleanError(error))
    }
  }

  async function rodarPreAnalise() {
    setRunning(true)
    setErro('')
    try {
      const data = await jpost('/api/pre-analise/resumo', {
        path,
        shapefile_zip: preShape,
        saida_dir: preOut,
        usar_ia: false,
      })
      setResumo(data)
      const output = await jpost('/api/pre-analise/run', {
        path,
        shapefile_zip: preShape,
        saida_dir: preOut,
        usar_ia: true,
      })
      setPreStatus(output)
      await refreshResults(path)
    } catch (error) {
      setErro(cleanError(error))
    } finally {
      setRunning(false)
    }
  }

  async function runAutomations() {
    const ids = autos.filter((auto) => selected[auto.id]).map((auto) => auto.id)
    if (!ids.length) return
    setRunning(true)
    setErro('')
    setProgress({})
    try {
      const response = await fetch(API + '/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, ids }),
      })
      if (!response.ok || !response.body) throw new Error(await response.text())
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const chunks = buffer.split('\n\n')
        buffer = chunks.pop() || ''
        for (const chunk of chunks) {
          const line = chunk.split('\n').find((entry) => entry.startsWith('data: '))
          if (!line) continue
          const event = JSON.parse(line.slice(6))
          if (event.automacao) setProgress((old) => ({ ...old, [event.automacao]: event }))
        }
      }
      await refreshResults(path)
    } catch (error) {
      setErro(cleanError(error))
    } finally {
      setRunning(false)
    }
  }

  useEffect(() => {
    loadRecentes()
    refreshDoctor('')
  }, [])

  if (appView === 'lobby') {
    return (
      <div className="app-shell lobby-shell">
        {showNewForm ? (
          <NewAnalysisForm onCancel={() => setShowNewForm(false)} onCreate={carregar} />
        ) : (
          <ProjectsLobby recentes={recentes} onOpen={carregar} onNew={() => setShowNewForm(true)} erro={erro} />
        )}
      </div>
    )
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Globe2 size={25} /></div>
          <div><strong>NexoGeo</strong><span>Ambiental</span></div>
        </div>
        <nav className="nav-list" aria-label="Navegacao principal">
          {NAV.map((item) => {
            const Icon = item.icon
            return (
              <button type="button" key={item.id} className={activeView === item.id ? 'active' : ''} onClick={() => setActiveView(item.id)}>
                <Icon size={18} />
                <span>{item.label}</span>
                {activeView === item.id ? <ChevronRight size={16} /> : null}
              </button>
            )
          })}
        </nav>
        <div className="sidebar-footer">
          <span>Projeto ativo</span>
          <strong>{project?.imovel || 'Sem projeto'}</strong>
          <small>{project?.raiz || path}</small>
        </div>
      </aside>
      <main className="main-surface">
        <header className="topbar">
          <div className="topbar-title">
            <div className="topbar-icon"><ActiveIcon size={19} /></div>
            <div><span>NexoGeo Ambiental</span><strong>{activeMeta.label}</strong></div>
          </div>
          <div className="project-command">
            <input value={path} onChange={(event) => setPath(event.target.value)} placeholder="Caminho do projeto.json da analise" />
            <IconButton title="Abrir projeto" onClick={async () => {
              const result = await jget('/api/dialog/file')
              if (result.path) carregar(result.path)
            }}>
              <FolderOpen size={18} />
            </IconButton>
            <IconButton title="Recarregar" onClick={() => carregar(path)} disabled={busy || !path}>
              {busy ? <Loader2 size={18} className="spin" /> : <RefreshCw size={18} />}
            </IconButton>
          </div>
          <button className="back-button" type="button" onClick={() => setAppView('lobby')}>
            <ArrowLeft size={17} />
            Projetos
          </button>
        </header>
        <div className="content-surface">
          {activeView === 'pre' ? (
            <PreAnalysisView
              project={project}
              resumo={resumo}
              preShape={preShape}
              setPreShape={setPreShape}
              preOut={preOut}
              setPreOut={setPreOut}
              preStatus={preStatus}
              running={running}
              erro={erro}
              onPreview={conferirGeometria}
              onRun={rodarPreAnalise}
              results={results}
            />
          ) : null}
          {activeView === 'maps_ai' ? (
            <MapsAiView
              analysisPath={path}
              preShape={preShape}
              mapProject={mapProject}
              setMapProject={setMapProject}
              chatResult={chatResult}
              setChatResult={setChatResult}
              mapResult={mapResult}
              setMapResult={setMapResult}
              mapResults={mapResults}
              setMapResults={setMapResults}
            />
          ) : null}
          {activeView === 'automations' ? (
            <AutomationGrid
              autos={autos}
              selected={selected}
              setSelected={setSelected}
              progress={progress}
              running={running}
              onRun={runAutomations}
            />
          ) : null}
          {activeView === 'results' ? (
            <ResultsView
              results={results}
              mapResults={mapResults}
              onRefresh={() => refreshResults(path)}
              onRefreshMaps={() => refreshMapResults()}
            />
          ) : null}
          {activeView === 'doctor' ? <DoctorView doctor={doctor} onRefresh={() => refreshDoctor()} /> : null}
          {activeView === 'manual' ? <ManualView /> : null}
          {erro && activeView !== 'pre' ? (
            <div className="floating-error"><AlertTriangle size={18} /><span>{erro}</span></div>
          ) : null}
        </div>
      </main>
    </div>
  )
}
