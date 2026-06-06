import { useState } from 'react'
import { motion } from 'framer-motion'

const TYPE_LABEL = { bank: 'Bank account', credit_card: 'Credit card' }

function ordinal(n) {
  if (n === 1 || n === 21) return `${n}st`
  if (n === 2 || n === 22) return `${n}nd`
  if (n === 3 || n === 23) return `${n}rd`
  return `${n}th`
}

export default function AccountsView({ accounts, onAdd, onDelete, onBack, onUpdateCycle, userBadge }) {
  const [newName, setNewName] = useState('')
  const [newType, setNewType] = useState('bank')
  const [showForm, setShowForm] = useState(false)
  const [editingCycle, setEditingCycle] = useState(null)
  const [cycleValue, setCycleValue] = useState('')

  async function handleAdd(e) {
    e.preventDefault()
    if (!newName.trim()) return
    await onAdd(newName.trim(), newType)
    setNewName('')
    setNewType('bank')
    setShowForm(false)
  }

  function cancelForm() {
    setShowForm(false)
    setNewName('')
    setNewType('bank')
  }

  function startCycleEdit(a) {
    setEditingCycle(a.name)
    setCycleValue(a.cycle_start_day != null ? String(a.cycle_start_day) : '')
  }

  function saveCycle(name) {
    const trimmed = cycleValue.trim()
    if (trimmed === '') {
      onUpdateCycle(name, null)
    } else {
      const val = parseInt(trimmed, 10)
      if (!isNaN(val) && val >= 1 && val <= 28) onUpdateCycle(name, val)
    }
    setEditingCycle(null)
  }

  function handleCycleKeyDown(e, name) {
    if (e.key === 'Enter') saveCycle(name)
    if (e.key === 'Escape') setEditingCycle(null)
  }

  return (
    <div className="accounts-view">
      <div className="accounts-nav">
        <button className="back-btn" onClick={onBack}>← Back</button>
        <span className="history-nav-title">Accounts</span>
        {userBadge}
      </div>

      <motion.div className="accounts-content" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22, ease: 'easeOut' }}>
        <div className="accounts-heading">
          <h1>Accounts</h1>
          <p className="accounts-subtitle">
            Track your bank accounts and credit cards. Marking an upload's account type enables
            automatic credit card payment detection so spending isn't double-counted.
          </p>
        </div>

        <div className="accounts-list">
          {accounts.length === 0 && (
            <p className="accounts-empty">No accounts yet. Add one below.</p>
          )}
          {accounts.map(a => (
            <div key={a.name} className="account-card">
              <div className="account-card-body">
                <div className="account-card-left">
                  <span className="account-card-name">{a.name}</span>
                  <span className={`account-type-tag ${a.type}`}>{TYPE_LABEL[a.type] || a.type}</span>
                </div>
                {a.type === 'credit_card' && (
                  editingCycle === a.name ? (
                    <div className="cycle-edit-row">
                      <span className="cycle-edit-label">Bills on the</span>
                      <input
                        type="number"
                        min="1" max="28"
                        className="cycle-input"
                        value={cycleValue}
                        placeholder="1–28"
                        onChange={e => setCycleValue(e.target.value)}
                        onBlur={() => saveCycle(a.name)}
                        onKeyDown={e => handleCycleKeyDown(e, a.name)}
                        autoFocus
                      />
                      <span className="cycle-edit-label">th of each month</span>
                      <button
                        className="cycle-save-btn"
                        onMouseDown={e => { e.preventDefault(); saveCycle(a.name) }}
                      >Save</button>
                      <button
                        className="cycle-cancel-btn"
                        onMouseDown={e => { e.preventDefault(); setEditingCycle(null) }}
                      >Cancel</button>
                    </div>
                  ) : (
                    <button className="cycle-badge" onClick={() => startCycleEdit(a)}>
                      {a.cycle_start_day != null
                        ? `Bills on the ${ordinal(a.cycle_start_day)} of each month`
                        : 'Billing cycle — not set'
                      }
                      <span className="cycle-pencil">✎</span>
                    </button>
                  )
                )}
              </div>
              <button
                className="account-delete-btn"
                onClick={() => onDelete(a.name)}
                title={`Remove ${a.name}`}
              >✕</button>
            </div>
          ))}
        </div>

        {showForm ? (
          <form className="add-account-form" onSubmit={handleAdd}>
            <input
              className="label-input"
              type="text"
              placeholder="Account name (e.g. Chase Checking)"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              autoFocus
            />
            <div className="account-type-toggle">
              <label className={`acct-type-btn ${newType === 'bank' ? 'active' : ''}`}>
                <input type="radio" name="addAcctType" value="bank" checked={newType === 'bank'} onChange={() => setNewType('bank')} />
                Bank account
              </label>
              <label className={`acct-type-btn ${newType === 'credit_card' ? 'active' : ''}`}>
                <input type="radio" name="addAcctType" value="credit_card" checked={newType === 'credit_card'} onChange={() => setNewType('credit_card')} />
                Credit card
              </label>
            </div>
            <div className="add-account-actions">
              <button type="submit" className="submit-btn" disabled={!newName.trim()}>Add account</button>
              <button type="button" className="cancel-btn" onClick={cancelForm}>Cancel</button>
            </div>
          </form>
        ) : (
          <button className="add-account-btn" onClick={() => setShowForm(true)}>+ Add account</button>
        )}
      </motion.div>
    </div>
  )
}
