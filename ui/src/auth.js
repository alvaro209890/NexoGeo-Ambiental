/* Auth compartilhado do NexoGeo (login/cadastro). Persistido em localStorage. */
import { useState } from 'react'

export const API = import.meta.env.VITE_API_URL || ''
const STORAGE_KEY = 'nexogeo_auth'

export function loadAuth() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || null } catch { return null }
}
export function saveAuth(auth) { localStorage.setItem(STORAGE_KEY, JSON.stringify(auth)) }
export function clearAuth() { localStorage.removeItem(STORAGE_KEY) }

export function authError(e) {
  const raw = e?.message || String(e)
  if (/load failed|failed to fetch|networkerror/i.test(raw)) {
    return 'Nao foi possivel falar com o servidor. Verifique a conexao e tente de novo.'
  }
  try { return JSON.parse(raw).detail || raw } catch { return raw }
}
