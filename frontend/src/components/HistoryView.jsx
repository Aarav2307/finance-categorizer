import { Fragment, useState } from 'react'
import { motion } from 'framer-motion'
import { fmtAmt } from '../format'

const pageTransition = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.22, ease: 'easeOut' },
}

const cardVariants = {
  hidden:  { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.28, ease: 'easeOut' } },
}

export default function HistoryView({ uploads, onView, onDelete, onViewDashboard, onViewCombined, onRenameLabel }) {
  const [editingId, setEditingId] = useState(null)
  const [editValue, setEditValue]   = useState('')
  const [editError, setEditError]   = useState('')
  const [savingId, setSavingId]     = useState(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState(null)
  const [deletingId, setDeletingId] = useState(null)
  const [deleteError, setDeleteError] = useState('')

  function startEdit(u)  { setConfirmDeleteId(null); setEditingId(u.id); setEditValue(u.label); setEditError('') }
  function cancelEdit()  { setEditingId(null);  setEditValue('');      setEditError('') }

  async function saveEdit(id) {
    const trimmed = editValue.trim()
    if (!trimmed)           { setEditError('Label cannot be empty');               return }
    if (trimmed.length > 50){ setEditError('Label must be 50 characters or fewer'); return }
    setSavingId(id)
    try {
      await onRenameLabel(id, trimmed)
      cancelEdit()
    } catch (e) {
      setEditError(e.message || 'Could not save. Try again.')
    } finally {
      setSavingId(null)
    }
  }

  function handleKeyDown(e, id) {
    if (e.key === 'Enter')  saveEdit(id)
    if (e.key === 'Escape') cancelEdit()
  }

  function askDelete(id)  { setEditingId(null); setDeleteError(''); setConfirmDeleteId(id) }
  function cancelDelete() { setConfirmDeleteId(null); setDeleteError('') }

  async function confirmDelete(id) {
    setDeletingId(id)
    setDeleteError('')
    try {
      await onDelete(id)
      setConfirmDeleteId(null)
    } catch (e) {
      setDeleteError(e.message || 'Could not delete. Try again.')
    } finally {
      setDeletingId(null)
    }
  }

  // ── Nav ────────────────────────────────────────────────────────────────────
  const nav = (
    <div className="history-nav">
      <button className="back-btn" onClick={onViewDashboard} aria-label="Back to dashboard">← Dashboard</button>
      <span className="history-nav-title">History</span>
      <div />
    </div>
  )

  if (uploads.length === 0) {
    return (
      <div className="history-page">
        {nav}
        <motion.div className="history-body" {...pageTransition}>
          <div className="history-empty">
            <p>No uploads yet. Categorize a statement and it will appear here.</p>
          </div>
        </motion.div>
      </div>
    )
  }

  // ── Group by year ──────────────────────────────────────────────────────────
  function labelYear(u) {
    if (u.max_txn_date) return u.max_txn_date.slice(0, 4)
    const m = u.label.match(/\b(20\d{2})\b/)
    return m ? m[1] : u.uploaded_at.slice(0, 4)
  }

  const byYear = {}
  for (const u of uploads) {
    const y = labelYear(u)
    if (!byYear[y]) byYear[y] = []
    byYear[y].push(u)
  }

  function groupTotals(group) {
    let spending = 0, income = 0
    for (const u of group) {
      for (const s of u.summary) {
        if (s.total < 0) spending += s.total
        else income += s.total
      }
    }
    return { spending, income, net: spending + income }
  }

  const years = Object.keys(byYear).sort((a, b) => b - a)

  return (
    <div className="history-page">
      {nav}
      <motion.div className="history-body" {...pageTransition}>
        {years.map((year, yi) => {
          const sorted = [...byYear[year]].sort((a, b) => {
            const da = a.max_txn_date || a.uploaded_at
            const db = b.max_txn_date || b.uploaded_at
            return db.localeCompare(da)
          })

          const accountGroups = {}
          for (const u of sorted) {
            const acct = u.account_name || ''
            if (!accountGroups[acct]) accountGroups[acct] = []
            accountGroups[acct].push(u)
          }
          const accountNames = Object.keys(accountGroups).sort((a, b) => {
            if (!a && !b) return 0
            if (!a) return 1
            if (!b) return -1
            return a.localeCompare(b)
          })
          const multipleAccounts = accountNames.filter(Boolean).length > 1
          const firstLabeledIdx  = multipleAccounts ? accountNames.findIndex(a => a) : -1
          const { spending, income, net } = groupTotals(byYear[year])

          return (
            <Fragment key={year}>
              {yi > 0 && <div className="year-divider" />}
              <motion.div
                className="year-block"
                variants={cardVariants}
                initial="hidden"
                animate="visible"
                transition={{ delay: yi * 0.07 }}
              >
                {/* Year heading */}
                <div className="year-heading">
                  <h2 className="year-label">{year}</h2>
                  <div className="year-stats">
                    <span className="year-stat">
                      <span className="year-stat-label">Spent</span>
                      <span className="negative">${fmtAmt(Math.abs(spending), 0)}</span>
                    </span>
                    <span className="year-stat-sep">·</span>
                    <span className="year-stat">
                      <span className="year-stat-label">Income</span>
                      <span className="positive">${fmtAmt(income, 0)}</span>
                    </span>
                    <span className="year-stat-sep">·</span>
                    <span className="year-stat">
                      <span className="year-stat-label">Net</span>
                      <span className={net >= 0 ? 'positive' : 'negative'}>
                        {net >= 0 ? '+' : '−'}${fmtAmt(Math.abs(net), 0)}
                      </span>
                    </span>
                    {sorted.length > 1 && (
                      <button className="view-all-btn" onClick={() => onViewCombined(sorted.map(u => u.id), year)}>
                        View All {year}
                      </button>
                    )}
                  </div>
                </div>

                {/* Statement rows */}
                <div className="history-rows">
                  {accountNames.map((acct, ai) => (
                    <Fragment key={acct || '__no_account__'}>
                      {multipleAccounts && acct && (
                        <div className={`account-group-header${ai === firstLabeledIdx ? ' account-group-header--first' : ''}`}>
                          <span>{acct}</span>
                          <div className="account-group-rule" />
                        </div>
                      )}
                      {accountGroups[acct].map(u => (
                        <div key={u.id} className="history-row">
                          <div className="history-row-label">
                            {editingId === u.id ? (
                              <span className="label-edit-wrap">
                                <input
                                  className="label-input"
                                  value={editValue}
                                  maxLength={50}
                                  autoFocus
                                  onChange={e => { setEditValue(e.target.value); setEditError('') }}
                                  onKeyDown={e => handleKeyDown(e, u.id)}
                                />
                                <span className="label-edit-actions">
                                  <button className="save-edit-btn" onClick={() => saveEdit(u.id)} disabled={savingId === u.id}>
                                    {savingId === u.id ? 'Saving…' : 'Save'}
                                  </button>
                                  <button className="cancel-edit-btn" onClick={cancelEdit} disabled={savingId === u.id}>Cancel</button>
                                </span>
                                {editError && <span className="label-edit-error" role="alert">{editError}</span>}
                              </span>
                            ) : (
                              <button
                                type="button"
                                className="label-display"
                                onClick={() => startEdit(u)}
                                aria-label={`Rename statement "${u.label}"`}
                              >
                                <span className="history-label-text">{u.label}</span>
                                <span className="label-pencil" aria-hidden="true">✎</span>
                              </button>
                            )}
                          </div>
                          <div className="history-row-meta">
                            <span className="history-row-date">
                              {new Date(u.uploaded_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                            </span>
                            <span className="history-row-count">{u.transaction_count} txns</span>
                          </div>
                          <div className="history-row-actions">
                            {confirmDeleteId === u.id ? (
                              <span className="delete-confirm">
                                <span className="delete-confirm-label">Delete this statement?</span>
                                <button className="confirm-delete-btn" onClick={() => confirmDelete(u.id)} disabled={deletingId === u.id}>
                                  {deletingId === u.id ? 'Deleting…' : 'Delete'}
                                </button>
                                <button className="cancel-edit-btn" onClick={cancelDelete} disabled={deletingId === u.id}>Cancel</button>
                                {deleteError && <span className="label-edit-error" role="alert">{deleteError}</span>}
                              </span>
                            ) : (
                              <>
                                <button className="history-view-btn" onClick={() => onView(u.id)}>View →</button>
                                <button
                                  className="history-delete-btn"
                                  onClick={() => askDelete(u.id)}
                                  aria-label={`Delete statement "${u.label}"`}
                                >
                                  <span aria-hidden="true">✕</span>
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      ))}
                    </Fragment>
                  ))}
                </div>
              </motion.div>
            </Fragment>
          )
        })}
      </motion.div>
    </div>
  )
}
