import { useState } from 'react'
import { setAuth } from '../api'

const BASE = 'http://localhost:8000'

export default function AuthPage({ onAuth }) {
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ firstName: '', lastName: '', email: '', phone: '', password: '', confirmPassword: '' })
  const [error, setError] = useState(null)
  const [shakeKey, setShakeKey] = useState(0)
  const [loading, setLoading] = useState(false)

  function update(field, value) {
    setError(null)
    setForm(prev => ({ ...prev, [field]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (mode === 'register' && form.password !== form.confirmPassword) {
      setError('Passwords do not match')
      setShakeKey(k => k + 1)
      return
    }
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
            disabled={loading}
          >
            Login
          </button>
          <button
            className={mode === 'register' ? 'auth-tab active' : 'auth-tab'}
            onClick={() => { setMode('register'); setError(null) }}
            disabled={loading}
          >
            Register
          </button>
        </div>

        <form key={shakeKey} className={`auth-form${error ? ' auth-form-error' : ''}`} onSubmit={handleSubmit}>
          {mode === 'register' && (
            <>
              <div className="form-row">
                <div className="auth-field">
                  <label htmlFor="firstName" className="auth-field-label">First name</label>
                  <input
                    id="firstName"
                    autoComplete="given-name"
                    value={form.firstName}
                    onChange={e => update('firstName', e.target.value)}
                    required
                  />
                </div>
                <div className="auth-field">
                  <label htmlFor="lastName" className="auth-field-label">Last name</label>
                  <input
                    id="lastName"
                    autoComplete="family-name"
                    value={form.lastName}
                    onChange={e => update('lastName', e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="auth-field">
                <label htmlFor="phone" className="auth-field-label">Phone number <span className="auth-field-optional">(optional)</span></label>
                <input
                  id="phone"
                  type="tel"
                  autoComplete="tel"
                  placeholder="(555) 123-4567"
                  value={form.phone}
                  onChange={e => update('phone', e.target.value)}
                />
                <p className="auth-field-hint">Used only for account recovery. Never shared, never leaves this device.</p>
              </div>
            </>
          )}

          <div className="auth-field">
            <label htmlFor="email" className="auth-field-label">Email</label>
            <input
              id="email"
              type="email"
              className={error ? 'input-error' : ''}
              autoComplete="email"
              placeholder="you@example.com"
              value={form.email}
              onChange={e => update('email', e.target.value)}
              aria-describedby={error ? 'auth-error' : undefined}
              aria-invalid={error ? 'true' : 'false'}
              required
            />
          </div>

          <div className="auth-field">
            <label htmlFor="password" className="auth-field-label">Password</label>
            <input
              id="password"
              type="password"
              className={error ? 'input-error' : ''}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              value={form.password}
              onChange={e => update('password', e.target.value)}
              aria-describedby={mode === 'register' ? 'password-hint' : (error ? 'auth-error' : undefined)}
              aria-invalid={error ? 'true' : 'false'}
              required
              minLength={6}
            />
            {mode === 'register' && <p id="password-hint" className="auth-field-hint">At least 6 characters.</p>}
          </div>

          {mode === 'register' && (
            <div className="auth-field">
              <label htmlFor="confirmPassword" className="auth-field-label">Confirm password</label>
              <input
                id="confirmPassword"
                type="password"
                className={error ? 'input-error' : ''}
                autoComplete="new-password"
                value={form.confirmPassword}
                onChange={e => update('confirmPassword', e.target.value)}
                aria-describedby={error ? 'auth-error' : undefined}
                aria-invalid={error ? 'true' : 'false'}
                required
                minLength={6}
              />
            </div>
          )}

          {error && <p id="auth-error" className="error" role="alert">{error}</p>}

          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? (mode === 'login' ? 'Signing in…' : 'Creating your account…') : mode === 'login' ? 'Login' : 'Create Account'}
          </button>
        </form>
      </div>
    </div>
  )
}
