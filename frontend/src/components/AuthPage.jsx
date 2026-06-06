import { useState } from 'react'
import { setAuth } from '../api'

const BASE = 'http://localhost:8000'

export default function AuthPage({ onAuth }) {
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ firstName: '', lastName: '', email: '', phone: '', password: '' })
  const [error, setError] = useState(null)
  const [shakeKey, setShakeKey] = useState(0)
  const [loading, setLoading] = useState(false)

  function update(field, value) {
    setError(null)
    setForm(prev => ({ ...prev, [field]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const endpoint = mode === 'register' ? '/register' : '/login'
      const body = mode === 'register'
        ? { first_name: form.firstName, last_name: form.lastName, email: form.email, phone: form.phone, password: form.password }
        : { email: form.email, password: form.password }

      const res = await fetch(`${BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail)

      setAuth(data.token, data.user)
      onAuth(data.user)
    } catch (e) {
      setError(e.message)
      setShakeKey(k => k + 1)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-title">Finance Categorizer</h1>
        <p className="auth-subtitle">Your personal spending tracker — 100% local</p>

        <div className="auth-tabs">
          <button
            className={mode === 'login' ? 'auth-tab active' : 'auth-tab'}
            onClick={() => { setMode('login'); setError(null) }}
          >
            Login
          </button>
          <button
            className={mode === 'register' ? 'auth-tab active' : 'auth-tab'}
            onClick={() => { setMode('register'); setError(null) }}
          >
            Register
          </button>
        </div>

        <form key={shakeKey} className={`auth-form${error ? ' auth-form-error' : ''}`} onSubmit={handleSubmit}>
          {mode === 'register' && (
            <>
              <div className="form-row">
                <input
                  placeholder="First Name"
                  value={form.firstName}
                  onChange={e => update('firstName', e.target.value)}
                  required
                />
                <input
                  placeholder="Last Name"
                  value={form.lastName}
                  onChange={e => update('lastName', e.target.value)}
                  required
                />
              </div>
              <input
                type="tel"
                placeholder="Phone Number (optional)"
                value={form.phone}
                onChange={e => update('phone', e.target.value)}
              />
            </>
          )}

          <input
            type="email"
            className={error ? 'input-error' : ''}
            placeholder="Email"
            value={form.email}
            onChange={e => update('email', e.target.value)}
            required
          />
          <input
            type="password"
            className={error ? 'input-error' : ''}
            placeholder="Password"
            value={form.password}
            onChange={e => update('password', e.target.value)}
            required
            minLength={6}
          />

          {error && <p className="error">{error}</p>}

          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? 'Please wait…' : mode === 'login' ? 'Login' : 'Create Account'}
          </button>
        </form>
      </div>
    </div>
  )
}
