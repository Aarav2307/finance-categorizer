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

  function startEdit(u)  { setEditingId(u.id); setEditValue(u.label); setEditError('') }
  function cancelEdit()  { setEditingId(null);  setEditValue('');      setEditError('') }

  async function saveEdit(id) {
    const trimmed = editValue.trim()
    if (!trimmed)           { setEditError('Label cannot be empty');               return }
    if (trimmed.length > 50){ setEditError('Label must be 50 characters or fewer'); return }
    await onRenameLabel(id, trimmed)
    cancelEdit()
  }

  function handleKeyDown(e, id) {
    if (e.key === 'Enter')  saveEdit(id)
    if (e.key === 'Escape') cancelEdit()
  }

  // ── Nav ────────────────────────────────────────────────────────────────────
  const nav = (
    <div className="history-nav">
      <button className="back-btn" onClick={onViewDashboard}>← Dashboard</button>
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
            <div className="history-empty-icon">🗂</div>
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
                                  <button className="save-edit-btn" onClick={() => saveEdit(u.id)}>Save</button>
                                  <button className="cancel-edit-btn" onClick={cancelEdit}>Cancel</button>
                                </span>
                                {editError && <span className="label-edit-error">{editError}</span>}
                              </span>
                            ) : (
                              <span className="label-display" onClick={() => startEdit(u)}>
                                <span className="history-label-text">{u.label}</span>
                                <span className="label-pencil" title="Rename">✎</span>
                              </span>
                            )}
                          </div>
                          <div className="history-row-meta">
                            <span className="history-row-date">
                              {new Date(u.uploaded_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                            </span>
                            <span className="history-row-count">{u.transaction_count} txns</span>
                          </div>
                          <div className="history-row-actions">
                            <button className="history-view-btn" onClick={() => onView(u.id)}>View →</button>
                            <button className="history-delete-btn" onClick={() => onDelete(u.id)}>✕</button>
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
