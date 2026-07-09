/* ── Chat IA com Tools + Auth + Histórico ── */
import { useEffect, useRef, useState } from 'react'
import {
  AlertTriangle, Bot, ChevronRight, Cpu, FileText, FolderOpen, LogIn, LogOut,
  Image as ImageIcon, Loader2, MessageSquareText, Plus, Save, Sparkles, User,
} from 'lucide-react'

const API = import.meta.env.VITE_API_URL || ''
const STORAGE_KEY = 'nexogeo_auth'

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
  'Crie um mapa de CAR com perimetro, ATP e embargos da SEMA',
  'Mapa de tipologia vegetal com tabela de quantitativos',
  'Mapa de dinamica: AVN vs AUAS com hachuras',
]

// ── Auth helpers ──
function loadAuth() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || null } catch { return null }
}
function saveAuth(auth) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(auth))
}
function clearAuth() {
  localStorage.removeItem(STORAGE_KEY)
}

export function ChatView({ analysisPath, preShape, mapProject, setMapProject, mapResults, setMapResults }) {
  const [auth, setAuth] = useState(loadAuth)
  const [loginEmail, setLoginEmail] = useState('')
  const [loginSenha, setLoginSenha] = useState('')
  const [loginNome, setLoginNome] = useState('')
  const [modoAuth, setModoAuth] = useState('login') // 'login' | 'registrar'
  const [authErro, setAuthErro] = useState('')
  const [authLoading, setAuthLoading] = useState(false)

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [running, setRunning] = useState(false)
  const [erro, setErro] = useState('')
  const [streamingTools, setStreamingTools] = useState([])
  const [chats, setChats] = useState([])
  const [chatId, setChatId] = useState(null)
  const [showSidebar, setShowSidebar] = useState(false)

  const chatEnd = useRef(null)
  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, streamingTools])

  // ── Auth ──
  async function handleLogin() {
    setAuthErro(''); setAuthLoading(true)
    try {
      const ep = modoAuth === 'registrar' ? '/api/auth/registrar' : '/api/auth/login'
      const body = modoAuth === 'registrar'
        ? { email: loginEmail, senha: loginSenha, nome: loginNome }
        : { email: loginEmail, senha: loginSenha }
      const res = await jpost(ep, body)
      if (!res.ok) { setAuthErro(res.erro); return }
      saveAuth(res); setAuth(res)
      await loadChats(res.email, res.token)
    } catch (e) { setAuthErro(cleanError(e)) }
    finally { setAuthLoading(false) }
  }

  function handleLogout() { clearAuth(); setAuth(null); setMessages([]); setChats([]); setChatId(null) }

  async function loadChats(email, token) {
    try {
      const res = await jpost('/api/chats/listar', { email: email || auth?.email, token: token || auth?.token, titulo: '' })
      setChats(res.chats || [])
    } catch {}
  }

  async function novoChat() {
    try {
      const res = await jpost('/api/chats/criar', { email: auth.email, token: auth.token, titulo: 'Novo mapa' })
      setChatId(res.chat_id)
      setMessages([])
      await loadChats()
    } catch (e) { setErro(cleanError(e)) }
  }

  async function abrirChat(cid) {
    try {
      const res = await jpost('/api/chats/carregar', { email: auth.email, token: auth.token, titulo: cid })
      setChatId(cid)
      // Restaura mensagens do historico
      const msgs = (res.mensagens || []).map(m => ({
        role: m.role,
        content: m.content,
        ts: m.ts,
        tools: m.tool_calls,
        result: m.role === 'assistant' && m.tool_calls ? { resumo: m.content } : null,
      }))
      setMessages(msgs)
    } catch (e) { setErro(cleanError(e)) }
  }

  // ── Chat send ──
  async function sendMessage() {
    const text = input.trim()
    if (!text || running || !auth) return
    setInput(''); setErro(''); setStreamingTools([]); setRunning(true)

    let cid = chatId
    if (!cid) {
      try {
        const res = await jpost('/api/chats/criar', { email: auth.email, token: auth.token, titulo: text.slice(0, 40) })
        cid = res.chat_id; setChatId(cid)
      } catch (e) { setErro(cleanError(e)); setRunning(false); return }
    }

    setMessages(prev => [...prev, { role: 'user', content: text, ts: Date.now() }])

    try {
      const response = await fetch(API + '/api/chats/mensagem', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: auth.email, token: auth.token, chat_id: cid, prompt: text, max_steps: 12 }),
      })
      if (!response.ok || !response.body) throw new Error(await response.text())
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''
      const tools = []
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const chunks = buffer.split('\n\n'); buffer = chunks.pop() || ''
        for (const chunk of chunks) {
          const line = chunk.split('\n').find(e => e.startsWith('data: '))
          if (!line) continue
          const ev = JSON.parse(line.slice(6))
          if (ev.status === 'tool') { tools.push(ev); setStreamingTools(prev => [...prev, ev]) }
          else if (ev.status === 'done') {
            setStreamingTools([])
            setMessages(prev => [...prev, { role: 'assistant', content: ev.result?.resumo || '✅ Mapa gerado!', ts: Date.now(), result: ev.result, tools: [...tools] }])
            await loadChats()
          } else if (ev.status === 'error') { setErro(ev.erro) }
        }
      }
    } catch (error) { setErro(cleanError(error)) }
    finally { setRunning(false); setStreamingTools([]) }
  }

  const handleKeyDown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }

  // ── Labels + colors ──
  const toolLabels = {
    estado_atual: '🔍 Estado atual', listar_camadas: '📋 Camadas', criar_mapa: '🗺️ Criar mapa',
    definir_titulo: '✏️ Título', adicionar_camada: '➕ Camada', remover_camada: '➖ Camada',
    editar_camada: '🎨 Estilo', editar_legenda: '📚 Legenda', criar_tabela: '📊 Tabela',
    mover_elemento: '📍 Mover', alternar_elemento: '👁️ Visibilidade', editar_estilo_elemento: '🎨 Ajuste',
    definir_metadados_imagem: '🖼️ Metadados', definir_raster_fundo: '🛰️ Fundo',
    definir_escala: '📐 Escala', sugerir_opcoes: '❓ Pergunta', finalizar: '✅ Finalizar',
  }
  const toolColors = {
    criar_mapa: '#35d08a', adicionar_camada: '#48d8c8', editar_camada: '#f2b84b',
    editar_legenda: '#a78bfa', criar_tabela: '#60a5fa', mover_elemento: '#fb923c',
    finalizar: '#35d08a', sugerir_opcoes: '#f472b6',
  }

  // ── Login screen ──
  if (!auth) {
    return (
      <div className="auth-screen">
        <div className="auth-card">
          <div className="w-14 h-14 rounded-2xl bg-brand/15 flex items-center justify-center mb-4 mx-auto">
            <Bot size={28} className="text-brand" />
          </div>
          <h2 className="text-xl font-bold text-ink text-center mb-1">NexoGeo Mapas IA</h2>
          <p className="text-sm text-muted text-center mb-6">Entre ou crie sua conta para começar</p>

          <div className="flex gap-2 mb-4">
            <button onClick={() => setModoAuth('login')} className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all ${modoAuth === 'login' ? 'bg-brand text-black' : 'bg-panel-strong text-muted'}`}>Entrar</button>
            <button onClick={() => setModoAuth('registrar')} className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all ${modoAuth === 'registrar' ? 'bg-brand text-black' : 'bg-panel-strong text-muted'}`}>Criar conta</button>
          </div>

          {modoAuth === 'registrar' && (
            <input type="text" value={loginNome} onChange={e => setLoginNome(e.target.value)}
              placeholder="Seu nome" className="auth-input" />
          )}
          <input type="email" value={loginEmail} onChange={e => setLoginEmail(e.target.value)}
            placeholder="Email" className="auth-input" />
          <input type="password" value={loginSenha} onChange={e => setLoginSenha(e.target.value)}
            placeholder="Senha" className="auth-input" onKeyDown={e => e.key === 'Enter' && handleLogin()} />

          {authErro && <p className="text-danger text-sm mt-2">{authErro}</p>}

          <button onClick={handleLogin} disabled={authLoading || !loginEmail || !loginSenha}
            className="w-full mt-4 py-2.5 rounded-xl bg-brand hover:bg-brand-strong text-black font-semibold transition-all disabled:opacity-50">
            {authLoading ? <Loader2 size={18} className="spin inline" /> : <LogIn size={18} className="inline mr-1" />}
            {modoAuth === 'registrar' ? 'Criar conta' : 'Entrar'}
          </button>
        </div>
      </div>
    )
  }

  // ── Chat UI ──
  return (
    <div className="chat-shell">
      {/* Header */}
      <div className="chat-header">
        <div className="flex items-center gap-3">
          <button onClick={() => setShowSidebar(!showSidebar)} className="w-9 h-9 rounded-xl bg-panel-strong flex items-center justify-center hover:bg-border transition-all">
            <MessageSquareText size={18} className="text-muted" />
          </button>
          <div>
            <h2 className="text-base font-bold text-ink">Helô Cartógrafa</h2>
            <p className="text-xs text-muted">{running ? 'Trabalhando...' : `${chats.length} chats • ${auth.nome}`}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={novoChat} className="px-3 py-1.5 rounded-lg bg-brand/10 text-brand text-xs font-semibold hover:bg-brand/20 transition-all">
            <Plus size={14} className="inline mr-1" /> Novo
          </button>
          <button onClick={handleLogout} className="px-3 py-1.5 rounded-lg bg-panel-strong text-muted text-xs hover:text-ink transition-all">
            <LogOut size={14} className="inline mr-1" /> Sair
          </button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        {showSidebar && (
          <div className="chat-sidebar">
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wide px-3 py-2">Seus chats</h3>
            {chats.map(c => (
              <button key={c.id} onClick={() => abrirChat(c.id)}
                className={`w-full text-left px-3 py-2.5 text-sm hover:bg-panel-strong transition-all border-l-2 ${c.id === chatId ? 'border-brand bg-brand/5 text-ink' : 'border-transparent text-muted'}`}>
                <div className="truncate font-medium">{c.titulo}</div>
                <div className="text-xs text-muted/60">{c.mensagens} msg • {c.atualizado_em?.slice(0, 10)}</div>
              </button>
            ))}
            {chats.length === 0 && (
              <p className="text-xs text-muted px-3 py-4">Nenhum chat ainda. Clique em Novo.</p>
            )}
          </div>
        )}

        {/* Messages */}
        <div className="chat-messages flex-1">
          {messages.length === 0 && !running && (
            <div className="chat-welcome">
              <div className="w-14 h-14 rounded-2xl bg-brand/10 flex items-center justify-center mb-4">
                <Sparkles size={28} className="text-brand" />
              </div>
              <h3 className="text-lg font-bold text-ink mb-2">Assistente Cartográfica IMAP</h3>
              <p className="text-sm text-muted max-w-md text-center mb-5">
                Descreva o mapa que você precisa. A IA vai criar, editar e posicionar cada elemento.
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                {DEFAULT_PROMPTS.map(p => (
                  <button key={p} onClick={() => { setInput(p); setTimeout(() => document.getElementById('chat-input')?.focus(), 50) }}
                    className="px-3 py-1.5 rounded-lg border border-border text-xs text-muted hover:text-ink hover:border-brand/40 transition-all">
                    {p.slice(0, 60)}{p.length > 60 ? '...' : ''}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`chat-msg ${msg.role}`}>
              <div className="chat-avatar">{msg.role === 'user' ? <User size={18} /> : <Bot size={18} />}</div>
              <div className="chat-bubble-wrap">
                <div className={`chat-bubble ${msg.error ? 'error' : ''}`}>{msg.content}</div>
                {/* Options */}
                {msg.tools && msg.tools.find(t => t.tool === 'sugerir_opcoes') && (() => {
                  const opt = msg.tools.find(t => t.tool === 'sugerir_opcoes')
                  const m = (opt.resultado || '').match(/\[OPCOES\] (.+?) \| (.+)/)
                  if (!m) return null
                  const labels = m[2].split(' | ')
                  return (
                    <div className="options-card">
                      <p className="text-sm text-ink font-semibold mb-2">{m[1]}</p>
                      <div className="flex flex-wrap gap-2">
                        {labels.map((l, j) => (
                          <button key={j} onClick={() => { setInput(l.trim()); document.getElementById('chat-input')?.focus() }}
                            className="px-3 py-1.5 rounded-lg border border-brand/40 bg-brand/10 text-brand hover:bg-brand/20 text-xs font-medium transition-all">
                            {l.trim()}
                          </button>
                        ))}
                      </div>
                    </div>
                  )
                })()}
                {/* Tools */}
                {msg.tools && msg.tools.length > 0 && msg.tools.filter(t => t.tool !== 'sugerir_opcoes').length > 0 && (
                  <div className="tool-calls-card">
                    <div className="tool-calls-header"><Cpu size={12} /> {msg.tools.length} ferramentas</div>
                    <div className="tool-calls-list">
                      {msg.tools.filter(t => t.tool !== 'sugerir_opcoes').map((t, j) => (
                        <div key={j} className="tool-call-item" style={{ borderLeftColor: toolColors[t.tool] || '#64748b' }}>
                          <span className="text-xs">{toolLabels[t.tool]?.split(' ')[0] || '⚙️'}</span>
                          <span className="tool-name">{toolLabels[t.tool] || t.tool}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {/* Result */}
                {msg.result?.outputs?.png_validacao && (
                  <div className="result-card-chat">
                    <img src={API + '/api/nexomap/file?path=' + encodeURIComponent(msg.result.outputs.png_validacao)} alt="Mapa" className="w-full rounded-lg border border-border mb-2" />
                    <div className="flex gap-2">
                      {msg.result.outputs?.pdf && (
                        <button onClick={() => jpost('/api/abrir', { alvo: msg.result.outputs.pdf })}
                          className="flex-1 px-2 py-1.5 rounded-lg bg-brand/10 text-brand text-xs font-semibold hover:bg-brand/20 transition-all">
                          <FileText size={12} className="inline mr-1" /> PDF
                        </button>
                      )}
                      <button onClick={() => jpost('/api/abrir', { alvo: msg.result.job_dir })}
                        className="flex-1 px-2 py-1.5 rounded-lg bg-panel-strong text-muted text-xs hover:text-ink transition-all">
                        <FolderOpen size={12} className="inline mr-1" /> Pasta
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Streaming */}
          {streamingTools.map((t, j) => (
            <div key={`s-${j}`} className="chat-msg assistant">
              <div className="chat-avatar"><Loader2 size={16} className="spin text-brand" /></div>
              <div className="streaming-tool animate-fadeIn" style={{ borderLeftColor: toolColors[t.tool] || '#64748b' }}>
                <span className="animate-pulse text-xs">{toolLabels[t.tool]?.split(' ')[0] || '⚙️'}</span>
                <span className="text-sm">{toolLabels[t.tool] || t.tool}</span>
              </div>
            </div>
          ))}
          {running && streamingTools.length === 0 && (
            <div className="chat-msg assistant">
              <div className="chat-avatar"><Loader2 size={16} className="spin text-brand" /></div>
              <div className="chat-bubble thinking">🤔 Pensando...</div>
            </div>
          )}
          {erro && <div className="chat-msg assistant"><div className="chat-bubble error">{erro}</div></div>}
          <div ref={chatEnd} />
        </div>
      </div>

      {/* Input */}
      <div className="chat-input-bar">
        <textarea id="chat-input" value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown} rows={1} disabled={running}
          placeholder="Descreva o mapa... Ex: Mapa de CAR com hachura quadriculada no desmatamento"
          className="chat-textarea" />
        <button onClick={sendMessage} disabled={running || !input.trim()} className="chat-send-btn">
          {running ? <Loader2 size={18} className="spin" /> : <ChevronRight size={20} />}
        </button>
      </div>
    </div>
  )
}
