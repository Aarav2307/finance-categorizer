import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { AlertTriangle } from 'lucide-react'
import { apiFetch, getUser, clearAuth } from './api'
import AuthPage from './components/AuthPage'
import UploadScreen from './components/UploadScreen'
import TransactionTable from './components/TransactionTable'
import SummaryPanel from './components/SummaryPanel'
import CacheEditor from './components/CacheEditor'
import HistoryView from './components/HistoryView'
import RecurringCard from './components/RecurringCard'
import AccountsView from './components/AccountsView'
import MigrationView from './components/MigrationView'
import SpendingTrends from './components/SpendingTrends'
import DashboardView from './components/DashboardView'
import CategorizingSkeleton from './components/CategorizingSkeleton'

export default function App() {
  const [user, setUser] = useState(getUser())
  const [view, setView] = useState('dashboard')
  const [accountsBackView, setAccountsBackView] = useState('upload')
  const [transactions, setTransactions] = useState([])
  const [summary, setSummary] = useState([])
  const [cacheEntries, setCacheEntries] = useState([])
  const [historyUploads, setHistoryUploads] = useState([])
  const [uploadId, setUploadId] = useState(null)
  const [uploadLabel, setUploadLabel] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [zelleAliases, setZelleAliases] = useState({})
  const [resultsFrom, setResultsFrom] = useState('upload')
  const [recurring, setRecurring] = useState([])
  const [accounts, setAccounts] = useState([])
  const [orphanedUploads, setOrphanedUploads] = useState([])
  const [chartFilter, setChartFilter] = useState(null)

  const orphanedCount = orphanedUploads.reduce((s, u) => s + u.orphaned_count, 0)

  useEffect(() => {
    if (user) {
      fetchAccounts()
      fetchOrphanedUploads()
    }
  }, [])

  function handleLogout() {
    clearAuth()
    setUser(null)
    setView('dashboard')
    setOrphanedUploads([])
  }

  async function fetchCache() {
    const res = await apiFetch('/cache')
    const data = await res.json()
    setCacheEntries(data.entries)
  }

  async function fetchZelleAliases() {
    const res = await apiFetch('/zelle-aliases')
    const data = await res.json()
    setZelleAliases(data.aliases || {})
  }

  async function fetchAccounts() {
    const res = await apiFetch('/accounts')
    const data = await res.json()
    setAccounts(data.accounts || [])
  }

  async function fetchOrphanedUploads() {
    try {
      const res = await apiFetch('/orphaned-uploads')
      const data = await res.json()
      setOrphanedUploads(data.uploads || [])
    } catch (_) {}
  }

  async function saveAccount(name, type) {
    if (!name) return
    const res = await apiFetch('/accounts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, type }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail)
    }
    const data = await res.json()
    setAccounts(data.accounts || [])
  }

  async function handleDeleteAccount(name) {
    const res = await apiFetch(`/accounts?name=${encodeURIComponent(name)}`, { method: 'DELETE' })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail)
    }
    const data = await res.json()
    setAccounts(data.accounts || [])
  }

  async function handleUpdateCycle(name, day) {
    const res = await apiFetch('/accounts/cycle', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, cycle_start_day: day }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail)
    }
    const data = await res.json()
    setAccounts(data.accounts || [])
  }

  async function handleAssignAccounts(assignments) {
    const res = await apiFetch('/assign-accounts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assignments }),
    })
    const data = await res.json()
    setOrphanedUploads([])  // dismiss banner
    return data             // { assigned: N }
  }

  async function handleSaveZelleAliases(newAliases) {
    await apiFetch('/zelle-aliases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ aliases: newAliases }),
    })
    setZelleAliases(prev => ({ ...prev, ...newAliases }))
  }

  async function fetchHistory() {
    const res = await apiFetch('/history')
    const data = await res.json()
    setHistoryUploads(data.uploads)
  }

  async function handleUpload(file, label, accountName, accountType) {
    setLoading(true)
    setError(null)
    try {
      const body = new FormData()
      body.append('file', file)
      body.append('label', label)
      if (accountName) {
        body.append('account_name', accountName)
        body.append('account_type', accountType)
      }
      const res = await apiFetch('/categorize', { method: 'POST', body })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail)
      }
      const data = await res.json()
      setUploadId(data.upload_id)
      setUploadLabel(label)
      setTransactions(data.transactions)
      setSummary(data.summary)
      setRecurring(data.recurring || [])
      if (accountName) await saveAccount(accountName, accountType)
      await Promise.all([fetchCache(), fetchZelleAliases()])
      setResultsFrom('upload')
      setView('results')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function recomputeSummary(txns) {
    const totals = {}
    for (const t of txns) {
      totals[t.category] = Math.round(((totals[t.category] || 0) + t.amount) * 100) / 100
    }
    return Object.entries(totals)
      .map(([category, total]) => ({ category, total }))
      .sort((a, b) => a.total - b.total)
  }

  async function handleCorrect(description, _oldCategory, newCategory) {
    const res = await apiFetch('/correct', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description, category: newCategory }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail)
    }
    const updated = transactions.map(t =>
      t.description === description
        ? { ...t, category: newCategory, needs_review: false, source: 'cache' }
        : t
    )
    setTransactions(updated)
    setSummary(recomputeSummary(updated))
    await fetchCache()
    if (uploadId) {
      const histRes = await apiFetch(`/history/${uploadId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transactions: updated }),
      })
      if (!histRes.ok) {
        const err = await histRes.json()
        throw new Error(err.detail)
      }
    }
  }

  async function handleDeleteCache(key) {
    await apiFetch(`/cache?key=${encodeURIComponent(key)}`, { method: 'DELETE' })
    setCacheEntries(prev => prev.filter(e => e.key !== key))
  }

  async function handleAddCache(description, category) {
    await apiFetch('/review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description, category }),
    })
    await fetchCache()
  }

  async function handleViewHistory() {
    try {
      await fetchHistory()
    } finally {
      setView('history')
    }
  }

  async function handleViewUpload(id) {
    const res = await apiFetch(`/history/${id}`)
    const data = await res.json()
    setUploadId(id)
    setUploadLabel(data.label || '')
    setTransactions(data.transactions)
    setSummary(data.summary)
    setRecurring(data.recurring || [])
    setChartFilter(null)
    await Promise.all([fetchCache(), fetchZelleAliases()])
    setResultsFrom('history')
    setView('results')
  }

  async function handleViewCombined(uploadIds, yearLabel) {
    setLoading(true)
    setError(null)
    try {
      const results = await Promise.all(
        uploadIds.map(id => apiFetch(`/history/${id}`).then(r => r.json()))
      )
      const allTxns = results.flatMap((data, i) =>
        data.transactions.map(t => ({
          ...t,
          id: `${uploadIds[i]}_${t.id}`,
          upload_label: data.label,
          upload_id: uploadIds[i],
        }))
      )
      const recurringRes = await apiFetch('/recurring', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transactions: allTxns }),
      })
      const recurringData = await recurringRes.json()
      setUploadId(null)
      setUploadLabel(`All ${yearLabel}`)
      setChartFilter(null)
      setTransactions(recurringData.transactions)
      setSummary(recomputeSummary(recurringData.transactions))
      setRecurring(recurringData.recurring || [])
      await Promise.all([fetchCache(), fetchZelleAliases()])
      setResultsFrom('history')
      setView('results')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleDeleteUpload(uploadId) {
    const res = await apiFetch(`/history/${uploadId}`, { method: 'DELETE' })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail)
    }
    setHistoryUploads(prev => prev.filter(u => u.id !== uploadId))
  }

  async function handleRenameLabel(uploadId, newLabel) {
    const res = await apiFetch(`/history/${uploadId}/label`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label: newLabel }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail)
    }
    setHistoryUploads(prev => prev.map(u => u.id === uploadId ? { ...u, label: newLabel } : u))
  }

  function goToAccounts(returnTo = 'upload') {
    setAccountsBackView(returnTo)
    setView('accounts')
  }

  // ── Auth gate ─────────────────────────────────────────────────────────────
  if (!user) {
    return <AuthPage onAuth={u => { setUser(u); setView('dashboard'); fetchAccounts(); fetchOrphanedUploads() }} />
  }

  if (loading) {
    return <CategorizingSkeleton />
  }

  // ── Shared elements ────────────────────────────────────────────────────────
  const userBadge = (
    <div className="user-badge">
      <div className="user-avatar">{user.first_name[0].toUpperCase()}</div>
      <span className="user-name">{user.first_name}</span>
      <button className="logout-btn" onClick={handleLogout}>Logout</button>
    </div>
  )

  const migrationBanner = orphanedCount > 0 && view !== 'migration' && (
    <div className="migration-banner" onClick={() => setView('migration')}>
      <AlertTriangle size={15} aria-hidden="true" className="migration-banner-icon" />
      <span>
        {orphanedCount} transaction{orphanedCount !== 1 ? 's' : ''} have no account assigned.
      </span>
      <span className="migration-banner-cta">Fix this →</span>
    </div>
  )

  // ── Views ──────────────────────────────────────────────────────────────────
  if (view === 'accounts') {
    return (
      <AccountsView
        accounts={accounts}
        onAdd={saveAccount}
        onDelete={handleDeleteAccount}
        onUpdateCycle={handleUpdateCycle}
        onBack={() => setView(accountsBackView)}
        userBadge={userBadge}
      />
    )
  }

  if (view === 'migration') {
    return (
      <MigrationView
        orphanedUploads={orphanedUploads}
        accounts={accounts}
        onSave={handleAssignAccounts}
        onBack={() => setView('upload')}
        onAddAccount={() => goToAccounts('migration')}
      />
    )
  }

  if (view === 'dashboard') {
    return (
      <DashboardView
        onUpload={() => setView('upload')}
        onViewHistory={handleViewHistory}
        onViewAccounts={() => goToAccounts('dashboard')}
        userBadge={userBadge}
        migrationBanner={migrationBanner}
      />
    )
  }

  if (view === 'history') {
    return (
      <>
        {migrationBanner}
        <HistoryView
          uploads={historyUploads}
          onView={handleViewUpload}
          onDelete={handleDeleteUpload}
          onViewDashboard={() => setView('dashboard')}
          onViewCombined={handleViewCombined}
          onRenameLabel={handleRenameLabel}
        />
      </>
    )
  }

  if (view === 'upload') {
    return (
      <>
        {migrationBanner}
        <UploadScreen
          onUpload={handleUpload}
          onViewHistory={handleViewHistory}
          onViewAccounts={() => goToAccounts('upload')}
          onViewDashboard={() => setView('dashboard')}
          error={error}
          userBadge={userBadge}
          accounts={accounts}
        />
      </>
    )
  }

  return (
    <>
      {migrationBanner}
      <div className="results-page">
        <div className="results-nav">
          <button className="back-btn" onClick={() => resultsFrom === 'history' ? handleViewHistory() : setView('upload')}>
            {resultsFrom === 'history' ? '← History' : '← Upload'}
          </button>
          <div className="results-nav-actions">
            <button className="nav-link" onClick={() => goToAccounts('results')}>Accounts</button>
            <button className="nav-link" onClick={handleViewHistory}>History →</button>
            {userBadge}
          </div>
        </div>
        {uploadLabel && <h1 className="upload-label">{uploadLabel}</h1>}
        <motion.div
          key={uploadLabel}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.22, ease: 'easeOut' }}
          className="results-content"
        >
          {uploadId === null && (
            <SpendingTrends
              transactions={transactions}
              onChartFilter={setChartFilter}
              year={uploadLabel?.match(/\b(20\d{2})\b/)?.[1]}
            />
          )}
          <TransactionTable
            transactions={transactions}
            onCorrect={handleCorrect}
            uploadLabel={uploadLabel}
            zelleAliases={zelleAliases}
            onSaveZelleAliases={handleSaveZelleAliases}
            chartFilter={chartFilter}
            accounts={accounts}
            year={uploadLabel?.match(/\b(20\d{2})\b/)?.[1] ?? null}
          />
          <SummaryPanel summary={summary} />
          {recurring.length > 0 && <RecurringCard patterns={recurring} />}
          <CacheEditor entries={cacheEntries} onDelete={handleDeleteCache} onAdd={handleAddCache} />
        </motion.div>
      </div>
    </>
  )
}
