import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  Layers,
  Loader2,
  LogOut,
  Map,
  MapPin,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { API, authError } from './auth.js'

// Icone por modelo (usa nomes garantidos do lucide para evitar import quebrado).
const ICONES = {
  car: Layers,
  uso_consolidado: MapPin,
  tipologia: Sparkles,
  dinamica: Activity,
  embargos: ShieldCheck,
  alertas: AlertTriangle,
  areas_protegidas: Map,
}

function fileUrl(path) {
  return `${API}/api/nexomap/file?path=${encodeURIComponent(path)}`
}

export function CarMapaView({ onBack, usuario, onLogout }) {
  const [modelos, setModelos] = useState([])
  const [carregandoModelos, setCarregandoModelos] = useState(true)
  const [erroModelos, setErroModelos] = useState('')
  const [modeloSel, setModeloSel] = useState(null)
  const [numeroCar, setNumeroCar] = useState('')
  const [rodando, setRodando] = useState(false)
  const [etapa, setEtapa] = useState('')
  const [erro, setErro] = useState('')
  const [resultado, setResultado] = useState(null)
  const [tentativa, setTentativa] = useState(0)

  useEffect(() => {
    let vivo = true
    setCarregandoModelos(true)
    setErroModelos('')
    fetch(`${API}/api/nexomap/modelos`)
      .then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json() })
      .then((d) => { if (vivo) setModelos(d.modelos || []) })
      .catch((e) => { if (vivo) setErroModelos(authError(e)) })
      .finally(() => { if (vivo) setCarregandoModelos(false) })
    return () => { vivo = false }
  }, [tentativa])

  const tabela = useMemo(() => {
    const t = resultado?.mapspec?.tabela
    if (!t || !Array.isArray(t.linhas)) return null
    return t
  }, [resultado])

  async function gerar() {
    const numero = numeroCar.trim()
    if (!numero || !modeloSel) return
    setRodando(true)
    setErro('')
    setResultado(null)
    setEtapa('Consultando a SEMA…')
    try {
      const resp = await fetch(`${API}/api/nexomap/car-mapa`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ numero_car: numero, modelo: modeloSel.id, use_basemap: true }),
      })
      if (!resp.ok || !resp.body) throw new Error(await resp.text())
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const partes = buffer.split('\n\n')
        buffer = partes.pop() || ''
        for (const parte of partes) {
          const linha = parte.split('\n').find((l) => l.startsWith('data:'))
          if (!linha) continue
          let ev
          try { ev = JSON.parse(linha.slice(5).trim()) } catch { continue }
          if (ev.status === 'progress' && ev.stage === 'consultando_sema') setEtapa('Buscando o imovel no CAR…')
          else if (ev.status === 'progress' && ev.stage === 'renderizado') setEtapa('Montando o mapa…')
          else if (ev.status === 'error') { setErro(ev.erro || 'Falha ao gerar o mapa'); setEtapa('') }
          else if (ev.status === 'done') { setResultado(ev.result); setEtapa('') }
        }
      }
    } catch (e) {
      setErro(authError(e))
    } finally {
      setRodando(false)
      setEtapa('')
    }
  }

  return (
    <div className="carmap">
      <Estilos />
      <header className="carmap-top">
        {onBack ? (
          <button type="button" className="carmap-back" onClick={onBack}>
            <ArrowLeft size={17} /> Inicio
          </button>
        ) : <span />}
        <div className="carmap-title">
          <span className="eyebrow">NexoGeo · SEMA-MT</span>
          <h1>Mapas por CAR</h1>
          <p>Escolha um modelo, informe o numero do CAR estadual e o sistema busca a propriedade no SIMCAR digital e monta o mapa no padrao IMAP.</p>
        </div>
        {usuario ? (
          <div className="carmap-user">
            <span>{usuario.nome || usuario.email}</span>
            {onLogout ? (
              <button type="button" className="carmap-back" onClick={onLogout}><LogOut size={14} /> Sair</button>
            ) : null}
          </div>
        ) : <span />}
      </header>

      {/* Cards de modelos */}
      <section className="carmap-cards" aria-label="Modelos de mapa">
        {carregandoModelos ? (
          <div className="carmap-loading"><Loader2 size={20} className="spin" /> Carregando modelos…</div>
        ) : erroModelos ? (
          <div className="carmap-erro-box">
            <AlertTriangle size={18} />
            <span>{erroModelos}</span>
            <button type="button" onClick={() => setTentativa((n) => n + 1)}>
              <RefreshCw size={15} /> Tentar novamente
            </button>
          </div>
        ) : modelos.map((m) => {
          const Icon = ICONES[m.id] || Map
          const ativo = modeloSel?.id === m.id
          return (
            <button
              key={m.id}
              type="button"
              className={`carmap-card${ativo ? ' ativo' : ''}`}
              style={{ '--cor': m.cor }}
              onClick={() => { setModeloSel(m); setResultado(null); setErro('') }}
            >
              <span className="carmap-card-ic"><Icon size={22} /></span>
              <span className="carmap-card-cat">{m.categoria}</span>
              <strong>{m.titulo}</strong>
              <span className="carmap-card-desc">{m.descricao}</span>
              {m.tem_tabela ? <span className="carmap-card-badge">com quantitativos</span> : null}
            </button>
          )
        })}
      </section>

      {/* Painel de geracao */}
      {modeloSel ? (
        <section className="carmap-form">
          <div className="carmap-form-row">
            <div className="carmap-input">
              <Search size={17} />
              <input
                value={numeroCar}
                onChange={(e) => setNumeroCar(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') gerar() }}
                placeholder="Numero do CAR estadual — ex.: MT313839/2025"
                disabled={rodando}
              />
            </div>
            <button type="button" className="carmap-gen" onClick={gerar} disabled={rodando || !numeroCar.trim()}>
              {rodando ? <Loader2 size={18} className="spin" /> : <RefreshCw size={18} />}
              {rodando ? 'Gerando…' : `Gerar “${modeloSel.titulo}”`}
            </button>
          </div>
          {etapa ? <div className="carmap-etapa"><Loader2 size={15} className="spin" /> {etapa}</div> : null}
          {erro ? <div className="carmap-erro"><AlertTriangle size={16} /> {erro}</div> : null}
        </section>
      ) : null}

      {/* Resultado */}
      {resultado ? (
        <section className="carmap-result">
          <div className="carmap-result-head">
            <div>
              <strong>{resultado.mapspec?.titulo}</strong>
              <span>{resultado.car?.nome} · CAR {resultado.car?.numero} · {fmtHa(resultado.car?.area_ha)}</span>
            </div>
            <div className="carmap-badges">
              {resultado.validacao?.conformidade_modelo?.ok
                ? <span className="carmap-ok"><CheckCircle2 size={15} /> Conforme IMAP</span>
                : <span className="carmap-warn"><AlertTriangle size={15} /> Revisar layout</span>}
              {resultado.outputs?.pdf ? (
                <a className="carmap-pdf" href={fileUrl(resultado.outputs.pdf)} target="_blank" rel="noreferrer">
                  <Download size={15} /> PDF
                </a>
              ) : null}
            </div>
          </div>
          <div className="carmap-preview">
            {resultado.outputs?.preview_png || resultado.outputs?.png_validacao ? (
              <img
                src={fileUrl(resultado.outputs.preview_png || resultado.outputs.png_validacao)}
                alt={resultado.mapspec?.titulo}
              />
            ) : <div className="carmap-noimg">Sem previa</div>}
          </div>
          {tabela ? (
            <div className="carmap-tabela">
              <h3>{tabela.titulo || 'Quantitativos'}</h3>
              <table>
                <tbody>
                  {tabela.linhas.map((linha, i) => (
                    <tr key={i} className={String(linha[0]).toLowerCase() === 'total' ? 'total' : ''}>
                      {linha.map((cel, j) => <td key={j}>{cel}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {resultado.warnings?.length ? (
            <details className="carmap-avisos">
              <summary>{resultado.warnings.length} aviso(s)</summary>
              <ul>{resultado.warnings.slice(0, 8).map((w, i) => <li key={i}>{w}</li>)}</ul>
            </details>
          ) : null}
        </section>
      ) : null}
    </div>
  )
}

function fmtHa(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '— ha'
  return `${n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ha`
}

function Estilos() {
  return (
    <style>{`
    .carmap { max-width: 1080px; margin: 0 auto; padding: 22px 20px 60px; }
    .carmap-top { display:flex; align-items:flex-start; gap:16px; margin-bottom:22px; }
    .carmap-back { display:inline-flex; align-items:center; gap:6px; background:transparent; border:1px solid var(--line,#2b3444); color:inherit; border-radius:10px; padding:7px 12px; cursor:pointer; font-size:.85rem; }
    .carmap-back:hover { border-color:#3b82f6; }
    .carmap-title h1 { margin:.2rem 0; font-size:1.6rem; }
    .carmap-title .eyebrow { font-size:.72rem; letter-spacing:.12em; text-transform:uppercase; opacity:.6; }
    .carmap-title p { opacity:.75; max-width:640px; font-size:.9rem; }
    .carmap-user { margin-left:auto; display:flex; align-items:center; gap:10px; font-size:.82rem; opacity:.85; }
    .carmap-erro-box { grid-column:1/-1; display:flex; align-items:center; gap:12px; flex-wrap:wrap; padding:16px;
      border:1px solid #7f1d1d; background:rgba(248,113,113,.08); border-radius:14px; color:#fca5a5; font-size:.9rem; }
    .carmap-erro-box button { display:inline-flex; align-items:center; gap:6px; margin-left:auto; padding:8px 14px;
      border:0; border-radius:10px; background:#2563eb; color:#fff; cursor:pointer; font-weight:600; }
    .carmap-cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:14px; margin-bottom:22px; }
    .carmap-card { text-align:left; display:flex; flex-direction:column; gap:6px; padding:16px; border-radius:16px; border:1px solid var(--line,#2b3444); background:var(--panel,#141a24); cursor:pointer; transition:.15s; position:relative; color:inherit; }
    .carmap-card:hover { transform:translateY(-2px); border-color:var(--cor,#3b82f6); box-shadow:0 8px 24px rgba(0,0,0,.18); }
    .carmap-card.ativo { border-color:var(--cor,#3b82f6); box-shadow:0 0 0 2px var(--cor,#3b82f6) inset; }
    .carmap-card-ic { width:40px; height:40px; border-radius:11px; display:grid; place-items:center; color:#fff; background:var(--cor,#3b82f6); }
    .carmap-card-cat { font-size:.68rem; letter-spacing:.08em; text-transform:uppercase; opacity:.6; }
    .carmap-card strong { font-size:1.02rem; }
    .carmap-card-desc { font-size:.82rem; opacity:.72; line-height:1.35; }
    .carmap-card-badge { margin-top:4px; align-self:flex-start; font-size:.7rem; padding:3px 8px; border-radius:999px; background:color-mix(in srgb, var(--cor,#3b82f6) 18%, transparent); color:var(--cor,#3b82f6); }
    .carmap-loading, .carmap-etapa { display:flex; align-items:center; gap:8px; opacity:.8; font-size:.9rem; }
    .carmap-form { background:var(--panel,#141a24); border:1px solid var(--line,#2b3444); border-radius:16px; padding:16px; margin-bottom:20px; }
    .carmap-form-row { display:flex; gap:10px; flex-wrap:wrap; }
    .carmap-input { flex:1; min-width:260px; display:flex; align-items:center; gap:8px; padding:0 12px; border:1px solid var(--line,#2b3444); border-radius:11px; background:var(--bg,#0d1117); }
    .carmap-input input { flex:1; background:transparent; border:0; outline:0; color:inherit; padding:12px 0; font-size:.95rem; }
    .carmap-gen { display:inline-flex; align-items:center; gap:8px; padding:12px 18px; border:0; border-radius:11px; background:#2563eb; color:#fff; font-weight:600; cursor:pointer; }
    .carmap-gen:disabled { opacity:.55; cursor:not-allowed; }
    .carmap-etapa { margin-top:10px; }
    .carmap-erro { margin-top:10px; display:flex; align-items:center; gap:8px; color:#f87171; font-size:.88rem; }
    .carmap-result { background:var(--panel,#141a24); border:1px solid var(--line,#2b3444); border-radius:16px; padding:16px; }
    .carmap-result-head { display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:12px; }
    .carmap-result-head strong { display:block; font-size:1.1rem; }
    .carmap-result-head span { opacity:.7; font-size:.85rem; }
    .carmap-badges { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
    .carmap-ok, .carmap-warn, .carmap-pdf { display:inline-flex; align-items:center; gap:5px; font-size:.8rem; padding:6px 10px; border-radius:9px; text-decoration:none; }
    .carmap-ok { background:rgba(34,197,94,.16); color:#22c55e; }
    .carmap-warn { background:rgba(234,179,8,.16); color:#eab308; }
    .carmap-pdf { background:#2563eb; color:#fff; }
    .carmap-preview img { width:100%; border-radius:12px; border:1px solid var(--line,#2b3444); display:block; }
    .carmap-noimg { padding:40px; text-align:center; opacity:.6; }
    .carmap-tabela { margin-top:16px; overflow-x:auto; }
    .carmap-tabela h3 { font-size:.95rem; margin:0 0 8px; }
    .carmap-tabela table { width:100%; border-collapse:collapse; font-size:.86rem; }
    .carmap-tabela td { padding:7px 10px; border-bottom:1px solid var(--line,#2b3444); }
    .carmap-tabela tr.total td { font-weight:700; border-top:2px solid var(--line,#2b3444); }
    .carmap-avisos { margin-top:14px; font-size:.82rem; opacity:.8; }
    .carmap-avisos summary { cursor:pointer; }
    `}</style>
  )
}
