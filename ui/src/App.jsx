import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Archive,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Database,
  ExternalLink,
  FileText,
  FolderOpen,
  Gauge,
  Globe2,
  Layers,
  Loader2,
  MapPin,
  Play,
  RefreshCw,
  Settings,
  ShieldCheck,
  UploadCloud,
  XCircle,
  ChevronDown,
  ChevronUp,
  Network,
  FileDown,
  Plus,
  ArrowLeft,
} from 'lucide-react'
import './index.css'

const API = ''

const NAV = [
  { id: 'pre', label: 'Pré-Análise', icon: MapPin },
  { id: 'automations', label: 'Automações', icon: Activity },
  { id: 'results', label: 'Resultados', icon: Archive },
  { id: 'manual', label: 'Manual', icon: BookOpen },
]

const DEFAULT_PROJECT =
  'C:\\Users\\Usuario\\Downloads\\Analise_de_area\\Lauri_Analise_1\\projeto.json'
const DEFAULT_SHAPE =
  'C:\\Users\\Usuario\\Downloads\\Analise_de_area\\Lauri_Analise_1\\Shapes\\fazendas_unidas.zip'
const DEFAULT_OUT =
  'C:\\Users\\Usuario\\Downloads\\Analise_de_area\\Lauri_Analise_1\\Automacoes\\Resultados\\Pre_Analise_Final'

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

function fileName(path) {
  if (!path) return ''
  const parts = String(path).split(/[\\/]/)
  return parts[parts.length - 1] || path
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function cleanError(error) {
  const raw = error?.message || String(error)
  try {
    const parsed = JSON.parse(raw)
    if (parsed.detail) return parsed.detail
  } catch {
    return raw
  }
  return raw
}

function statusCopy(status) {
  if (!status) return 'Aguardando'
  if (status === 'done') return 'Concluído'
  if (status === 'error') return 'Erro'
  if (status === 'started') return 'Rodando'
  return status
}

function StatusBadge({ state = 'idle', children }) {
  const Icon = state === 'ok' || state === 'done' ? CheckCircle2 : state === 'error' ? XCircle : Activity
  return (
    <span className={`status-badge status-${state}`}>
      <Icon size={15} strokeWidth={2.3} />
      {children}
    </span>
  )
}

function IconButton({ children, title, onClick, disabled, kind = 'ghost' }) {
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

function Field({ label, value, onChange, icon: Icon, placeholder, onBrowse }) {
  return (
    <div className="field">
      <span>{label}</span>
      <div className="field-group">
        <div className="field-input">
          {Icon ? <Icon size={17} /> : null}
          <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
        </div>
        {onBrowse && (
          <IconButton onClick={(e) => { e.preventDefault(); onBrowse(); }} title="Selecionar" kind="soft">
            <FolderOpen size={18} />
          </IconButton>
        )}
      </div>
    </div>
  )
}

function MiniStat({ label, value, icon: Icon }) {
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

function MapPreview({ proj, resumo }) {
  const bbox = resumo?.bbox_wgs84 || resumo?.bbox || null
  const bboxText = bbox
    ? `${Number(bbox[0]).toFixed(4)}, ${Number(bbox[1]).toFixed(4)} / ${Number(bbox[2]).toFixed(4)}, ${Number(bbox[3]).toFixed(4)}`
    : 'Bounding box será calculado pelo shapefile'

  return (
    <section className="map-preview" aria-label="Resumo espacial">
      <div className="map-grid" />
      <svg className="polygon-sketch" viewBox="0 0 420 260" role="img" aria-label="Polígono ilustrativo da propriedade">
        <path d="M82 158 L142 78 L248 52 L337 117 L304 207 L183 226 Z" />
        <circle cx="142" cy="78" r="4" />
        <circle cx="248" cy="52" r="4" />
        <circle cx="337" cy="117" r="4" />
        <circle cx="304" cy="207" r="4" />
        <circle cx="183" cy="226" r="4" />
        <circle cx="82" cy="158" r="4" />
      </svg>
      <div className="map-preview-header">
        <span>Área de trabalho</span>
        <StatusBadge state={resumo ? 'ok' : 'idle'}>{resumo ? 'Geometria lida' : 'Preparação'}</StatusBadge>
      </div>
      <div className="map-preview-footer">
        <div>
          <strong>{proj?.imovel || 'Fazendas Unidas'}</strong>
          <span>
            {proj?.municipio?.nome || 'Nova Ubiratã'} / {proj?.municipio?.uf || 'MT'}
          </span>
        </div>
        <small>{bboxText}</small>
      </div>
    </section>
  )
}

function StepTimeline({ resumo, preStatus, running, erro }) {
  const steps = [
    {
      label: 'Shapefile',
      text: resumo ? `${resumo.feature_count || resumo.poligonos || 'OK'} feição(ões) importadas` : 'ZIP aguardando leitura',
      state: resumo ? 'done' : 'idle',
    },
    {
      label: 'Intersecções',
      text: resumo ? 'SEMA, CAR, APF, IBAMA, FUNAI e MapBiomas preparados' : 'Bases são consultadas no processamento',
      state: running ? 'started' : resumo ? 'done' : 'idle',
    },
    {
      label: 'Documentos',
      text: preStatus?.arquivo ? 'Recibos e APFs organizados em Consultas_Publicas' : 'Downloads automáticos serão salvos por origem',
      state: preStatus?.arquivo ? 'done' : running ? 'started' : 'idle',
    },
    {
      label: 'Relatório Word',
      text: preStatus?.nome || 'DOCX final ainda não gerado',
      state: preStatus?.arquivo ? 'done' : erro ? 'error' : 'idle',
    },
  ]

  return (
    <div className="timeline">
      {steps.map((step) => (
        <div className={`timeline-row ${step.state}`} key={step.label}>
          <div className="timeline-dot">
            {step.state === 'started' ? <Loader2 size={14} className="spin" /> : step.state === 'error' ? <XCircle size={14} /> : <CheckCircle2 size={14} />}
          </div>
          <div>
            <strong>{step.label}</strong>
            <span>{step.text}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

function EvidenceRail({ proj, resumo, results, preStatus }) {
  const folders = [
    { label: 'CAR', value: 'Consultas_Publicas/CAR' },
    { label: 'APF', value: 'Consultas_Publicas/APF' },
    { label: 'Relatório', value: fileName(preStatus?.arquivo) || 'Aguardando geração' },
  ]

  return (
    <aside className="evidence-rail">
      <div className="rail-section">
        <div className="section-title">
          <ShieldCheck size={18} />
          <span>Contexto do projeto</span>
        </div>
        <dl className="detail-list">
          <div>
            <dt>Cliente</dt>
            <dd>{proj?.cliente || '-'}</dd>
          </div>
          <div>
            <dt>Imóvel</dt>
            <dd>{proj?.imovel || '-'}</dd>
          </div>
          <div>
            <dt>Consulta</dt>
            <dd>{proj?.data_consulta || '-'}</dd>
          </div>
          <div>
            <dt>CRS</dt>
            <dd>{proj?.crs_utm || '-'}</dd>
          </div>
        </dl>
      </div>

      <div className="rail-section">
        <div className="section-title">
          <Database size={18} />
          <span>Geografia</span>
        </div>
        <div className="metric-stack">
          <MiniStat label="Área estimada" value={resumo?.area_ha ? `${Number(resumo.area_ha).toLocaleString('pt-BR')} ha` : '-'} icon={Layers} />
          <MiniStat label="Polígonos" value={resumo?.feature_count || resumo?.poligonos || '-'} icon={MapPin} />
        </div>
      </div>

      <div className="rail-section">
        <div className="section-title">
          <FolderOpen size={18} />
          <span>Evidências</span>
        </div>
        <div className="folder-list">
          {folders.map((item) => (
            <div className="folder-row" key={item.label}>
              <span>{item.label}</span>
              <strong title={item.value}>{item.value}</strong>
            </div>
          ))}
        </div>
      </div>

      <div className="rail-section compact">
        <div className="section-title">
          <FileText size={18} />
          <span>Arquivos recentes</span>
        </div>
        {results.length ? (
          <div className="recent-list">
            {results.slice(0, 4).map((item) => (
              <div key={item.path}>
                <strong>{item.nome}</strong>
                <span>{formatBytes(item.tamanho)}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">Nenhum resultado listado ainda.</p>
        )}
      </div>
    </aside>
  )
}

function PreAnalysisView({
  proj,
  resumo,
  preShape,
  setPreShape,
  preOut,
  setPreOut,
  preStatus,
  running,
  erro,
  onPreview,
  onRun,
  results,
}) {
  return (
    <div className="workspace-grid">
      <div className="workspace-main">
        <MapPreview proj={proj} resumo={resumo} />

        <section className="work-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Fluxo principal</span>
              <h1>Pré-Análise ambiental</h1>
            </div>
            <StatusBadge state={running ? 'started' : preStatus?.arquivo ? 'ok' : 'idle'}>
              {running ? 'Processando' : preStatus?.arquivo ? 'DOCX pronto' : 'Aguardando execução'}
            </StatusBadge>
          </div>

          <div className="analysis-grid">
            <Field 
              label="Shapefile compactado (.zip)" 
              value={preShape} 
              onChange={setPreShape} 
              icon={UploadCloud} 
              onBrowse={async () => {
                const res = await jget('/api/dialog/file')
                if (res.path) setPreShape(res.path)
              }} 
            />
            <Field 
              label="Pasta de saída" 
              value={preOut} 
              onChange={setPreOut} 
              icon={FolderOpen} 
              onBrowse={async () => {
                const res = await jget('/api/dialog/folder')
                if (res.path) setPreOut(res.path)
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
              Gerar relatório Word
            </PrimaryButton>
          </div>

          {erro ? (
            <div className="error-box">
              <AlertTriangle size={18} />
              <span>{erro}</span>
            </div>
          ) : null}
        </section>

        <section className="work-panel">
          <div className="panel-heading slim">
            <div>
              <span className="eyebrow">Rastreamento</span>
              <h2>Etapas e entregáveis</h2>
            </div>
          </div>
          <StepTimeline resumo={resumo} preStatus={preStatus} running={running} erro={erro} />
        </section>
      </div>

      <EvidenceRail proj={proj} resumo={resumo} results={results} preStatus={preStatus} />
    </div>
  )
}

function AutomationGrid({ autos, selected, setSelected, progress, running, onRun }) {
  const [expanded, setExpanded] = useState({})
  const selectedCount = Object.values(selected).filter(Boolean).length
  return (
    <section className="view-stack">
      <div className="section-header">
        <div>
          <span className="eyebrow">Execuções auxiliares</span>
          <h1>Automações do projeto</h1>
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
          const isExpanded = !!expanded[auto.id]
          
          return (
            <div className={`automation-card ${isSelected ? 'selected' : ''}`} key={auto.id}>
              <div 
                className="automation-card-header" 
                onClick={() => setSelected((old) => ({ ...old, [auto.id]: !isSelected }))}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => {}}
                />
                <div className="automation-card-body">
                  <div className="automation-icon">
                    <ClipboardList size={20} />
                  </div>
                  <div>
                    <strong>{auto.label}</strong>
                    <span>{auto.id}</span>
                  </div>
                </div>
                <div className="automation-card-actions">
                  <StatusBadge state={state === 'done' ? 'done' : state === 'error' ? 'error' : state === 'started' ? 'started' : 'idle'}>
                    {statusCopy(state)}
                  </StatusBadge>
                  <button 
                    type="button" 
                    className="expand-button"
                    onClick={(e) => {
                      e.stopPropagation()
                      setExpanded((old) => ({ ...old, [auto.id]: !isExpanded }))
                    }}
                    title={isExpanded ? "Ocultar detalhes" : "Mostrar detalhes"}
                  >
                    {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                  </button>
                </div>
              </div>
              
              {isExpanded && (
                <div className="automation-card-details">
                  <p>{auto.desc}</p>
                  <div className="detail-tags">
                    <span className="detail-tag"><FileDown size={14} /> Saída: .{auto.saida}</span>
                    {auto.rede && <span className="detail-tag warn"><Network size={14} /> Requer Internet</span>}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

function ResultsView({ results, onRefresh }) {
  return (
    <section className="view-stack">
      <div className="section-header">
        <div>
          <span className="eyebrow">Arquivos gerados</span>
          <h1>Resultados</h1>
        </div>
        <IconButton title="Atualizar resultados" onClick={onRefresh} kind="soft">
          <RefreshCw size={18} />
        </IconButton>
      </div>

      <div className="results-table">
        {results.length ? (
          results.map((item) => (
            <div className="result-row" key={item.path}>
              <div className="file-mark">
                <FileText size={18} />
              </div>
              <div className="result-main">
                <strong>{item.nome}</strong>
                <span>{item.path}</span>
              </div>
              <span>{formatBytes(item.tamanho)}</span>
              <span className="ext-pill">{item.ext || 'arquivo'}</span>
            </div>
          ))
        ) : (
          <div className="empty-state">
            <FileText size={34} />
            <strong>Nenhum resultado encontrado</strong>
            <span>Execute a Pré-Análise ou atualize a lista depois de gerar arquivos.</span>
          </div>
        )}
      </div>
    </section>
  )
}

function ManualView() {
  const sections = [
    {
      title: '1. Antes de rodar',
      items: [
        'Confirme o projeto.json da pasta raiz do trabalho.',
        'Use um shapefile compactado em .zip contendo .shp, .shx, .dbf e .prj.',
        'Mantenha secrets.local.json fora do Git quando houver chaves privadas.',
      ],
    },
    {
      title: '2. Fluxo da Pré-Análise',
      items: [
        'Carregue o projeto no topo da tela.',
        'Informe o ZIP da propriedade em Shapefile compactado.',
        'Escolha a pasta de saída e clique em Conferir geometria para validar área, CRS e bounding box.',
        'Clique em Gerar relatório Word para consultar bases, baixar documentos, processar textos e montar o DOCX.',
      ],
    },
    {
      title: '3. O que o sistema entrega',
      items: [
        'Um arquivo .docx com as seções técnicas e jurídicas da análise.',
        'Recibos do CAR em Consultas_Publicas/CAR.',
        'Autorizações Provisórias de Funcionamento em Consultas_Publicas/APF.',
        'Dados estruturados da IA para áreas, matrículas, posse, status e resumos jurídicos.',
      ],
    },
    {
      title: '4. Fontes consultadas',
      items: [
        'SEMA-MT, SIMCAR, APF Rural, INCRA, FUNAI, IBAMA/PAMGIA e MapBiomas.',
        'DeepSeek Flash estrutura recibos e APFs a partir de texto bruto.',
        'DeepSeek Pro resume autos de infração e embargos quando houver cruzamento espacial.',
      ],
    },
    {
      title: '5. Revisão obrigatória',
      items: [
        'Confirme manualmente registros de embargo, infração e sobreposição sensível antes de protocolar.',
        'Compare nomes, CPF/CNPJ, matrícula e áreas com os documentos públicos baixados.',
        'Quando uma fonte pública estiver indisponível, registre a indisponibilidade no relatório final.',
      ],
    },
  ]

  return (
    <section className="manual-layout">
      <div className="manual-intro">
        <span className="eyebrow">Manual operacional</span>
        <h1>NexoGeo Ambiental</h1>
        <p>
          Este módulo transforma o ZIP da propriedade em uma pré-análise Word auditável: geometria,
          consultas públicas, documentos baixados, leitura por IA e texto técnico pronto para revisão.
        </p>
      </div>
      <div className="manual-grid">
        {sections.map((section) => (
          <article className="manual-section" key={section.title}>
            <h2>{section.title}</h2>
            <ul>
              {section.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </section>
  )
}

function NewProjectForm({ onCancel, onCreate }) {
  const [nome, setNome] = useState('')
  const [cliente, setCliente] = useState('')
  const [destino, setDestino] = useState('')
  const [busy, setBusy] = useState(false)
  const [erro, setErro] = useState('')

  const handleCreate = async () => {
    if (!nome || !destino) {
      setErro('Nome e Destino são obrigatórios')
      return
    }
    setBusy(true)
    try {
      const res = await jpost('/api/projeto/novo', { nome, cliente, destino })
      if (res.path) {
        onCreate(res.path)
      }
    } catch (e) {
      setErro(cleanError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="new-project-modal">
      <div className="modal-content">
        <h2>Criar Novo Projeto</h2>
        <Field label="Nome do Imóvel/Projeto" value={nome} onChange={setNome} placeholder="Ex: Fazenda Boa Esperança" />
        <Field label="Cliente (opcional)" value={cliente} onChange={setCliente} placeholder="Nome do Produtor" />
        <Field 
          label="Pasta de Destino (Onde salvar)" 
          value={destino} 
          onChange={setDestino} 
          icon={FolderOpen} 
          onBrowse={async () => {
            const res = await jget('/api/dialog/folder')
            if (res.path) setDestino(res.path)
          }} 
        />
        {erro && <div className="error-box inline">{erro}</div>}
        <div className="modal-actions">
          <button className="btn-cancel" onClick={onCancel} disabled={busy}>Cancelar</button>
          <PrimaryButton onClick={handleCreate} disabled={busy} tone="solid">
            {busy ? <Loader2 size={18} className="spin" /> : 'Criar e Abrir'}
          </PrimaryButton>
        </div>
      </div>
    </div>
  )
}

function ProjectsLobby({ recentes, onOpen, onNew }) {
  return (
    <div className="projects-lobby">
      <div className="lobby-header">
        <div className="brand-mark large">
          <Globe2 size={34} />
        </div>
        <h1>Meus Projetos</h1>
        <p>Selecione um projeto recente ou crie uma nova análise estruturada.</p>
      </div>
      
      <div className="recent-grid">
        <div className="recent-card new-card" onClick={onNew}>
          <Plus size={28} />
          <strong>Criar Novo Projeto</strong>
        </div>
        {recentes.map(p => (
          <div className="recent-card" key={p.path} onClick={() => onOpen(p.path)}>
            <FolderOpen size={24} className="folder-icon" />
            <div className="rc-content">
              <strong>{p.nome}</strong>
              <span>{p.path}</span>
            </div>
            <ChevronRight size={20} className="arrow-icon" />
          </div>
        ))}
      </div>
    </div>
  )
}

export default function App() {
  const [appView, setAppView] = useState('lobby')
  const [recentes, setRecentes] = useState([])
  const [showNewForm, setShowNewForm] = useState(false)
  const [path, setPath] = useState(DEFAULT_PROJECT)
  const [proj, setProj] = useState(null)
  const [autos, setAutos] = useState([])
  const [selected, setSelected] = useState({})
  const [progress, setProgress] = useState({})
  const [results, setResults] = useState([])
  const [running, setRunning] = useState(false)
  const [busy, setBusy] = useState(false)
  const [erro, setErro] = useState('')
  const [activeView, setActiveView] = useState('pre')
  const [preShape, setPreShape] = useState(DEFAULT_SHAPE)
  const [preOut, setPreOut] = useState(DEFAULT_OUT)
  const [resumo, setResumo] = useState(null)
  const [preStatus, setPreStatus] = useState(null)

  const selectedCount = useMemo(() => Object.values(selected).filter(Boolean).length, [selected])

  async function carregarRecentes() {
    try {
      const cfg = await jget('/api/config')
      if (cfg.recentes) setRecentes(cfg.recentes)
    } catch (error) {
      console.error(error)
    }
  }

  async function carregar(projetoPath) {
    setBusy(true)
    setErro('')
    try {
      const [project, automationList] = await Promise.all([
        jpost('/api/projeto/validar', { path: projetoPath }),
        jget('/api/automacoes'),
      ])
      const resultList = await jget(`/api/resultados?path=${encodeURIComponent(projetoPath)}`).catch(() => [])
      setProj(project)
      setPath(projetoPath)
      setAutos(automationList)
      setResults(resultList)
      setSelected(Object.fromEntries(automationList.map((auto) => [auto.id, false])))
      setActiveView('pre')
      setAppView('project')
      setShowNewForm(false)
      carregarRecentes()
    } catch (error) {
      setErro(cleanError(error))
    } finally {
      setBusy(false)
    }
  }

  async function atualizarResultados() {
    if (!proj) return
    const resultList = await jget(`/api/resultados?path=${encodeURIComponent(path)}`).catch(() => [])
    setResults(resultList)
  }

  async function conferirGeometria() {
    setErro('')
    try {
      const shapeResumo = await jpost('/api/pre-analise/resumo', {
        path,
        shapefile_zip: preShape,
        saida_dir: preOut,
        usar_ia: false,
      })
      setResumo(shapeResumo)
    } catch (error) {
      setErro(cleanError(error))
    }
  }

  async function rodarPreAnalise() {
    setRunning(true)
    setErro('')
    try {
      const shapeResumo = await jpost('/api/pre-analise/resumo', {
        path,
        shapefile_zip: preShape,
        saida_dir: preOut,
        usar_ia: false,
      })
      setResumo(shapeResumo)
      const output = await jpost('/api/pre-analise/run', {
        path,
        shapefile_zip: preShape,
        saida_dir: preOut,
        usar_ia: true,
      })
      setPreStatus(output)
      await atualizarResultados()
    } catch (error) {
      setErro(cleanError(error))
    } finally {
      setRunning(false)
    }
  }

  async function runStream() {
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
          if (event.automacao) {
            setProgress((old) => ({ ...old, [event.automacao]: event }))
          }
        }
      }
      await atualizarResultados()
    } catch (error) {
      setErro(cleanError(error))
    } finally {
      setRunning(false)
    }
  }

  useEffect(() => {
    carregarRecentes()
  }, [])

  const ActiveIcon = NAV.find((item) => item.id === activeView)?.icon || MapPin

  if (appView === 'lobby') {
    return (
      <div className="app-shell lobby-shell">
        <main className="main-surface" style={{ border: 'none', borderRadius: 0, height: '100vh', display: 'flex', flexDirection: 'column' }}>
          {showNewForm ? (
            <NewProjectForm onCancel={() => setShowNewForm(false)} onCreate={carregar} />
          ) : (
            <ProjectsLobby recentes={recentes} onOpen={carregar} onNew={() => setShowNewForm(true)} />
          )}
          {erro && <div className="floating-error"><AlertTriangle size={18} /><span>{erro}</span></div>}
        </main>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Globe2 size={25} />
          </div>
          <div>
            <strong>NexoGeo</strong>
            <span>Ambiental</span>
          </div>
        </div>

        <nav className="nav-list" aria-label="Navegação principal">
          {NAV.map((item) => {
            const Icon = item.icon
            return (
              <button
                type="button"
                key={item.id}
                className={activeView === item.id ? 'active' : ''}
                onClick={() => setActiveView(item.id)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
                {activeView === item.id ? <ChevronRight size={16} /> : null}
              </button>
            )
          })}
        </nav>

        <div className="sidebar-footer">
          <span>Projeto ativo</span>
          <strong>{proj?.imovel || 'Nenhum projeto'}</strong>
          <small>{proj?.raiz || 'Carregue o projeto.json'}</small>
        </div>
      </aside>

      <main className="main-surface">
        <header className="topbar">
          <div className="topbar-title">
            <div className="topbar-icon">
              <ActiveIcon size={19} />
            </div>
            <div>
              <span>NexoGeo Ambiental</span>
              <strong>{NAV.find((item) => item.id === activeView)?.label || 'Pré-Análise'}</strong>
            </div>
          </div>

          <div className="project-command breadcrumb-command" style={{ gridTemplateColumns: '42px minmax(0, 1fr) 42px' }}>
            <IconButton title="Voltar ao Início" onClick={() => setAppView('lobby')} kind="soft">
              <ArrowLeft size={18} />
            </IconButton>
            <div className="breadcrumb" style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '0 12px', background: 'var(--panel)', borderRadius: '8px', border: '1px solid var(--border)' }}>
              <span style={{ color: 'var(--muted)', fontSize: '13px' }}>Projetos</span>
              <ChevronRight size={14} style={{ color: 'var(--muted)' }} />
              <strong style={{ fontSize: '14px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{proj?.imovel}</strong>
            </div>
            <IconButton title="Recarregar projeto" onClick={() => carregar(path)} disabled={busy} kind="soft">
              {busy ? <Loader2 size={18} className="spin" /> : <RefreshCw size={18} />}
            </IconButton>
          </div>

          <StatusBadge state={proj ? 'ok' : 'idle'}>{proj ? 'Projeto validado' : 'Sem projeto'}</StatusBadge>
        </header>

        <div className="content-surface">
          <>
            {activeView === 'pre' ? (
              <PreAnalysisView
                proj={proj}
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

            {activeView === 'automations' ? (
              <AutomationGrid
                autos={autos}
                selected={selected}
                setSelected={setSelected}
                progress={progress}
                running={running}
                onRun={runStream}
              />
            ) : null}

            {activeView === 'results' ? <ResultsView results={results} onRefresh={atualizarResultados} /> : null}
            {activeView === 'manual' ? <ManualView /> : null}

            {erro && activeView !== 'pre' ? (
              <div className="floating-error">
                <AlertTriangle size={18} />
                <span>{erro}</span>
              </div>
            ) : null}
          </>
        </div>
      </main>
    </div>
  )
}

