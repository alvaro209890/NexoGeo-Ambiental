/* ── Chat IA com Tools (Mapas IA) ── */
import { useEffect, useRef, useState } from 'react'
import {
  AlertTriangle, Bot, ChevronRight, Cpu, FileText, FolderOpen,
  Image as ImageIcon, Loader2, Save, Sparkles,
} from 'lucide-react'

const API = ''

async function jget(url) {
  const r = await fetch(API + url)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}
async function jpost(url, body) {
  const r = await fetch(API + url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}
function cleanError(e) {
  const raw = e?.message || String(e)
  try { const p = JSON.parse(raw); return p.detail || raw } catch { return raw }
}

const DEFAULT_PROMPTS = [
  'Gere um mapa com imagem de satelite, perimetro, CAR e embargos ambientais',
  'Monte um mapa de alertas MapBiomas e desmatamento PRODES',
  'Gere um mapa de terras indigenas e unidades de conservacao proximas',
]

export function ChatView({ analysisPath, preShape, mapProject, setMapProject, mapResults, setMapResults }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [running, setRunning] = useState(false)
  const [erro, setErro] = useState('')
  const [streamingTools, setStreamingTools] = useState([])
  const [finalResult, setFinalResult] = useState(null)

  const chatEnd = useRef(null)
  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, streamingTools])

  async function prepare() {
    if (!analysisPath) return null
    setErro('')
    try {
      const result = await jpost('/api/nexomap/from-analysis', { analysis_path: analysisPath, area_path: preShape || null })
      setMapProject(result.project)
      await refreshResults(result.path)
      return result.project
    } catch (error) { setErro(cleanError(error)); return null }
  }

  async function refreshResults(projectPath = mapProject?.arquivo) {
    if (!projectPath) return
    const data = await jget(`/api/nexomap/resultados?path=${encodeURIComponent(projectPath)}`).catch(() => [])
    setMapResults(data)
  }

  async function sendMessage() {
    const text = input.trim()
    if (!text || running) return
    const project = mapProject || await prepare()
    if (!project) return

    setInput('')
    setErro('')
    setFinalResult(null)
    setStreamingTools([])
    setRunning(true)

    const userMsg = { role: 'user', content: text, ts: Date.now() }
    setMessages(prev => [...prev, userMsg])

    try {
      const response = await fetch(API + '/api/nexomap/chat-tools', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: project.arquivo, prompt: text, allow_local_fallback: false, max_steps: 12 }),
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
          const line = chunk.split('\n').find(e => e.startsWith('data: '))
          if (!line) continue
          const ev = JSON.parse(line.slice(6))
          if (ev.status === 'tool') {
            setStreamingTools(prev => [...prev, ev])
          } else if (ev.status === 'done') {
            setFinalResult(ev.result)
            setMessages(prev => [...prev, {
              role: 'assistant',
              content: ev.result?.resumo || 'Mapa gerado com sucesso!',
              ts: Date.now(),
              result: ev.result,
              tools: [...streamingTools, ev].filter(e => e.status === 'tool'),
            }])
            await refreshResults(project.arquivo)
          } else if (ev.status === 'error') {
            setErro(ev.erro)
            setMessages(prev => [...prev, { role: 'assistant', content: '❌ ' + ev.erro, ts: Date.now(), error: true }])
          }
        }
      }
    } catch (error) {
      setErro(cleanError(error))
      setMessages(prev => [...prev, { role: 'assistant', content: '❌ ' + cleanError(error), ts: Date.now(), error: true }])
    } finally {
      setRunning(false)
      setStreamingTools([])
    }
  }

  const handleKeyDown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }

  const toolLabels = {
    estado_atual: '🔍 Consultando estado atual',
    listar_camadas: '📋 Listando camadas disponíveis',
    criar_mapa: '🗺️ Criando novo mapa',
    definir_titulo: '✏️ Definindo título',
    adicionar_camada: '➕ Adicionando camada',
    remover_camada: '➖ Removendo camada',
    editar_camada: '🎨 Editando estilo da camada',
    editar_legenda: '📚 Editando legenda',
    criar_tabela: '📊 Criando tabela de dados',
    mover_elemento: '📍 Reposicionando elemento',
    alternar_elemento: '👁️ Alternando visibilidade',
    editar_estilo_elemento: '🎨 Ajustando estilo',
    definir_metadados_imagem: '🖼️ Configurando metadados',
    definir_raster_fundo: '🛰️ Definindo imagem de fundo',
    definir_escala: '📐 Ajustando escala',
    finalizar: '✅ Finalizando mapa',
  }

  const toolColors = {
    criar_mapa: '#35d08a', adicionar_camada: '#48d8c8', editar_camada: '#f2b84b',
    editar_legenda: '#a78bfa', criar_tabela: '#60a5fa', mover_elemento: '#fb923c',
    finalizar: '#35d08a', definir_titulo: '#c084fc',
  }

  return (
    <div className="chat-shell">
      {/* ── Header ── */}
      <div className="chat-header">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-brand/15 flex items-center justify-center">
            <Bot size={20} className="text-brand" />
          </div>
          <div>
            <h2 className="text-base font-bold text-ink">Helô Cartógrafa</h2>
            <p className="text-xs text-muted">
              {running ? 'Trabalhando...' : mapProject ? 'Pronta para criar mapas' : 'Configure a área base primeiro'}
            </p>
          </div>
        </div>
        {!mapProject && (
          <button onClick={prepare} disabled={running || !analysisPath}
            className="px-4 py-2 rounded-xl bg-brand hover:bg-brand-strong text-black font-semibold text-sm transition-all">
            <Save size={15} className="inline mr-1" /> Preparar projeto
          </button>
        )}
        {mapProject && (
          <span className="text-xs text-muted bg-panel-strong px-3 py-1 rounded-full">
            {mapProject?.area_base?.exists ? '✅ Área carregada' : '⚠️ Sem área base'}
          </span>
        )}
      </div>

      {/* ── Messages ── */}
      <div className="chat-messages">
        {messages.length === 0 && !running && (
          <div className="chat-welcome">
            <div className="w-14 h-14 rounded-2xl bg-brand/10 flex items-center justify-center mb-4">
              <Sparkles size={28} className="text-brand" />
            </div>
            <h3 className="text-lg font-bold text-ink mb-2">Assistente Cartográfica IMAP</h3>
            <p className="text-sm text-muted max-w-md text-center mb-5">
              Descreva o mapa que você precisa. A IA vai criar, editar e posicionar cada elemento usando as bases da SEMA/MT.
            </p>
            <div className="flex flex-wrap gap-2 justify-center">
              {DEFAULT_PROMPTS.map(p => (
                <button key={p} onClick={() => { setInput(p); setTimeout(() => document.getElementById('chat-input')?.focus(), 50) }}
                  className="px-3 py-1.5 rounded-lg border border-border text-xs text-muted hover:text-ink hover:border-brand/40 transition-all">
                  {p.length > 60 ? p.slice(0, 60) + '...' : p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg ${msg.role}`}>
            <div className="chat-avatar">
              {msg.role === 'user' ? <UserCircle size={20} /> : <Bot size={20} />}
            </div>
            <div className="chat-bubble-wrap">
              <div className={`chat-bubble ${msg.error ? 'error' : ''}`}>
                {msg.content}
              </div>
              {/* Tool calls card */}
              {msg.tools && msg.tools.length > 0 && (
                <div className="tool-calls-card">
                  <div className="tool-calls-header">
                    <Cpu size={14} /> {msg.tools.length} ferramentas usadas
                  </div>
                  <div className="tool-calls-list">
                    {msg.tools.map((t, j) => (
                      <div key={j} className="tool-call-item" style={{ borderLeftColor: toolColors[t.tool] || '#64748b' }}>
                        <span className="tool-icon">{toolLabels[t.tool]?.split(' ')[0] || '🔧'}</span>
                        <div>
                          <span className="tool-name">{toolLabels[t.tool] || t.tool}</span>
                          {t.args && Object.keys(t.args).length > 0 && (
                            <span className="tool-args">
                              {Object.entries(t.args).filter(([k]) => !['resumo'].includes(k)).slice(0, 2).map(([k, v]) =>
                                `${k}=${typeof v === 'string' ? (v.length > 30 ? v.slice(0, 30) + '…' : v) : JSON.stringify(v).slice(0, 30)}`
                              ).join(', ')}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {/* Result card */}
              {msg.result && (
                <div className="result-card-chat">
                  <div className="flex items-center gap-3 mb-3">
                    <img src={API + '/api/nexomap/file?path=' + encodeURIComponent(msg.result.outputs?.png_validacao || '')}
                      alt="Preview" className="w-full rounded-lg border border-border" />
                  </div>
                  <div className="flex gap-2">
                    {msg.result.outputs?.pdf && (
                      <button onClick={() => jpost('/api/abrir', { alvo: msg.result.outputs.pdf })}
                        className="flex-1 px-3 py-2 rounded-lg bg-brand/10 text-brand text-xs font-semibold hover:bg-brand/20 transition-all">
                        <FileText size={14} className="inline mr-1" /> Abrir PDF
                      </button>
                    )}
                    {msg.result.outputs?.png_validacao && (
                      <button onClick={() => jpost('/api/abrir', { alvo: msg.result.outputs.png_validacao })}
                        className="flex-1 px-3 py-2 rounded-lg bg-cyan/10 text-cyan text-xs font-semibold hover:bg-cyan/20 transition-all">
                        <ImageIcon size={14} className="inline mr-1" /> Ver PNG
                      </button>
                    )}
                    <button onClick={() => jpost('/api/abrir', { alvo: msg.result.job_dir })}
                      className="flex-1 px-3 py-2 rounded-lg bg-panel-strong text-muted text-xs font-semibold hover:bg-border transition-all">
                      <FolderOpen size={14} className="inline mr-1" /> Pasta
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Streaming tool calls */}
        {streamingTools.map((t, j) => (
          <div key={`stream-${j}`} className="chat-msg assistant">
            <div className="chat-avatar"><Loader2 size={18} className="spin text-brand" /></div>
            <div className="chat-bubble-wrap">
              <div className="streaming-tool animate-fadeIn" style={{ borderLeftColor: toolColors[t.tool] || '#64748b' }}>
                <span className="tool-icon animate-pulse">{toolLabels[t.tool]?.split(' ')[0] || '⚙️'}</span>
                <span className="text-sm text-ink">{toolLabels[t.tool] || t.tool}</span>
              </div>
            </div>
          </div>
        ))}

        {running && streamingTools.length === 0 && (
          <div className="chat-msg assistant">
            <div className="chat-avatar"><Loader2 size={18} className="spin text-brand" /></div>
            <div className="chat-bubble-wrap">
              <div className="chat-bubble thinking">
                <span className="animate-pulse">🤔 Pensando no seu mapa...</span>
              </div>
            </div>
          </div>
        )}

        {erro && (
          <div className="chat-msg assistant">
            <div className="chat-avatar"><AlertTriangle size={18} className="text-danger" /></div>
            <div className="chat-bubble-wrap">
              <div className="chat-bubble error">{erro}</div>
            </div>
          </div>
        )}

        <div ref={chatEnd} />
      </div>

      {/* ── Input ── */}
      <div className="chat-input-bar">
        <textarea
          id="chat-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Descreva o mapa que você precisa... Ex: Crie um mapa de CAR com legenda no rodapé e tabela de quantitativos"
          rows={1}
          disabled={running}
          className="chat-textarea"
        />
        <button onClick={sendMessage} disabled={running || !input.trim()}
          className="chat-send-btn">
          {running ? <Loader2 size={18} className="spin" /> : <ChevronRight size={20} />}
        </button>
      </div>
    </div>
  )
}
