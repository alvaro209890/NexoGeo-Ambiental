/* Tela de cadastro/login — vem ANTES dos mapas. */
import { useState } from 'react'
import { Globe2, Loader2, LogIn, UserPlus } from 'lucide-react'
import { API, authError, saveAuth } from './auth.js'

export function AuthScreen({ onAuth }) {
  const [modo, setModo] = useState('login') // 'login' | 'registrar'
  const [nome, setNome] = useState('')
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit() {
    if (!email.trim() || !senha || (modo === 'registrar' && !nome.trim())) return
    setErro(''); setLoading(true)
    try {
      const ep = modo === 'registrar' ? '/api/auth/registrar' : '/api/auth/login'
      const body = modo === 'registrar'
        ? { email: email.trim(), senha, nome: nome.trim() }
        : { email: email.trim(), senha }
      const r = await fetch(API + ep, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!r.ok) throw new Error(await r.text())
      const res = await r.json()
      if (!res.ok) { setErro(res.erro || 'Falha na autenticacao'); return }
      saveAuth(res)
      onAuth(res)
    } catch (e) {
      setErro(authError(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-wrap">
      <Estilos />
      <div className="auth-box">
        <div className="auth-logo"><Globe2 size={30} /></div>
        <h1>NexoGeo Ambiental</h1>
        <p className="auth-sub">Entre ou crie sua conta para gerar mapas por CAR.</p>

        <div className="auth-tabs">
          <button className={modo === 'login' ? 'on' : ''} onClick={() => { setModo('login'); setErro('') }}>Entrar</button>
          <button className={modo === 'registrar' ? 'on' : ''} onClick={() => { setModo('registrar'); setErro('') }}>Criar conta</button>
        </div>

        {modo === 'registrar' ? (
          <input className="auth-field" placeholder="Seu nome" value={nome} onChange={(e) => setNome(e.target.value)} />
        ) : null}
        <input className="auth-field" type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="auth-field" type="password" placeholder="Senha" value={senha}
          onChange={(e) => setSenha(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') submit() }} />

        {erro ? <div className="auth-erro">{erro}</div> : null}

        <button className="auth-go" onClick={submit} disabled={loading || !email.trim() || !senha}>
          {loading ? <Loader2 size={18} className="spin" /> : (modo === 'registrar' ? <UserPlus size={18} /> : <LogIn size={18} />)}
          {modo === 'registrar' ? 'Criar conta' : 'Entrar'}
        </button>
      </div>
    </div>
  )
}

function Estilos() {
  return (
    <style>{`
    .auth-wrap { min-height: 100vh; display:grid; place-items:center; padding:24px;
      background: radial-gradient(1200px 600px at 50% -10%, #14324a 0%, #0b0f16 60%); }
    .auth-box { width:100%; max-width:380px; background:#131a24; border:1px solid #253143;
      border-radius:20px; padding:28px 24px; box-shadow:0 20px 60px rgba(0,0,0,.35); text-align:center; }
    .auth-logo { width:56px; height:56px; margin:0 auto 12px; border-radius:16px; display:grid; place-items:center;
      background:linear-gradient(135deg,#2563eb,#0ea5e9); color:#fff; }
    .auth-box h1 { font-size:1.35rem; margin:0 0 2px; color:#e8edf4; }
    .auth-sub { font-size:.86rem; color:#93a1b5; margin:0 0 18px; }
    .auth-tabs { display:flex; gap:8px; margin-bottom:14px; }
    .auth-tabs button { flex:1; padding:9px; border-radius:10px; border:1px solid #253143; background:#0e141d;
      color:#93a1b5; font-weight:600; font-size:.85rem; cursor:pointer; }
    .auth-tabs button.on { background:#2563eb; border-color:#2563eb; color:#fff; }
    .auth-field { width:100%; padding:11px 13px; margin-bottom:10px; border-radius:11px; border:1px solid #253143;
      background:#0e141d; color:#e8edf4; outline:none; font-size:.92rem; }
    .auth-field:focus { border-color:#2563eb; }
    .auth-erro { background:rgba(248,113,113,.12); color:#f87171; border-radius:9px; padding:8px 10px;
      font-size:.82rem; margin-bottom:10px; text-align:left; }
    .auth-go { width:100%; display:inline-flex; align-items:center; justify-content:center; gap:8px; margin-top:4px;
      padding:12px; border:0; border-radius:12px; background:#2563eb; color:#fff; font-weight:700; cursor:pointer; }
    .auth-go:disabled { opacity:.55; cursor:not-allowed; }
    .spin { animation: spin 1s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
    `}</style>
  )
}
