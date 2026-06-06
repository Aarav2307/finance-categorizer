const BASE = 'http://localhost:8000'

export function getToken()   { return localStorage.getItem('token') }
export function getUser()    { return JSON.parse(localStorage.getItem('user') || 'null') }
export function setAuth(token, user) {
  localStorage.setItem('token', token)
  localStorage.setItem('user', JSON.stringify(user))
}
export function clearAuth() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
}

// All API calls go through here — adds auth header automatically
// If the server returns 401 (expired token), clears auth and reloads
export async function apiFetch(path, options = {}) {
  const token = getToken()
  const headers = { ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...options, headers })

  if (res.status === 401) {
    clearAuth()
    window.location.reload()
  }

  return res
}
