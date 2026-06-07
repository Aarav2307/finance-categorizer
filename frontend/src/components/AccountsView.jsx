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
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState('')

  const [editingCycle, setEditingCycle] = useState(null)
  const [cycleValue, setCycleValue] = useState('')
  const [savingCycle, setSavingCycle] = useState(null)
  const [cycleError, setCycleError] = useState('')

  const [confirmDeleteName, setConfirmDeleteName] = useState(null)
  const [deletingName, setDeletingName] = useState(null)
  const [deleteError, setDeleteError] = useState('')

  async function handleAdd(e) {
    e.preventDefault()
    const trimmed = newName.trim()
    if (!trimmed || adding) return
    setAdding(true)
    setAddError('')
    try {
      await onAdd(trimmed, newType)
      setNewName('')
      setNewType('bank')
      setShowForm(false)
    } catch (err) {
      setAddError(err.message || 'Could not add account. Try again.')
    } finally {
      setAdding(false)
    }
  }

  function cancelForm() {
    setShowForm(false)
    setNewName('')
    setNewType('bank')
    setAddError('')
  }

  function startCycleEdit(a) {
    setConfirmDeleteName(null)
    setEditingCycle(a.name)
    setCycleValue(a.cycle_start_day != null ? String(a.cycle_start_day) : '')
    setCycleError('')
  }

  function cancelCycleEdit() {
    setEditingCycle(null)
    setCycleError('')
  }

  async function saveCycle(name) {
    const trimmed = cycleValue.trim()
    let day = null
    if (trimmed !== '') {
      day = parseInt(trimmed, 10)
      if (isNaN(day) || day < 1 || day > 28) {
        setCycleError('Enter a day between 1 and 28')
        return
      }
    }
    setSavingCycle(name)
    setCycleError('')
    try {
      await onUpdateCycle(name, day)
      setEditingCycle(null)
    } catch (err) {
      setCycleError(err.message || 'Could not save. Try again.')
    } finally {
      setSavingCycle(null)
    }
  }

  function handleCycleKeyDown(e, name) {
    if (e.key === 'Enter')  saveCycle(name)
    if (e.key === 'Escape') cancelCycleEdit()
  }

  function askDelete(name)  { setEditingCycle(null); setDeleteError(''); setConfirmDeleteName(name) }
  function cancelDelete()   { setConfirmDeleteName(null); setDeleteError('') }

  async function confirmDelete(name) {
    setDeletingName(name)
    setDeleteError('')
    try {
      await onDelete(name)
      setConfirmDeleteName(null)
    } catch (err) {
      setDeleteError(err.message || 'Could not remove. Try again.')
    } finally {
      setDeletingName(null)
    }
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
                        aria-label={`Billing cycle day for ${a.name}, 1 to 28`}
                        onChange={e => { setCycleValue(e.target.value); setCycleError('') }}
                        onKeyDown={e => handleCycleKeyDown(e, a.name)}
                        autoFocus
                      />
                      <span className="cycle-edit-label">th of each month</span>
                      <button className="save-edit-btn" onClick={() => saveCycle(a.name)} disabled={savingCycle === a.name}>
                        {savingCycle === a.name ? 'Saving…' : 'Save'}
                      </button>
                      <button className="cancel-edit-btn" onClick={cancelCycleEdit} disabled={savingCycle === a.name}>Cancel</button>
                      {cycleError && <span className="label-edit-error" role="alert">{cycleError}</span>}
                    </div>
                  ) : (
                    <button className="cycle-badge" onClick={() => startCycleEdit(a)}>
                      {a.cycle_start_day != null
                        ? `Bills on the ${ordinal(a.cycle_start_day)} of each month`
                        : 'Billing cycle — not set'
                      }
                      <span className="cycle-pencil" aria-hidden="true">✎</span>
                    </button>
                  )
                )}
              </div>
              {confirmDeleteName === a.name ? (
                <span className="delete-confirm">
                  <span className="delete-confirm-label">Remove this account?</span>
                  <button className="confirm-delete-btn" onClick={() => confirmDelete(a.name)} disabled={deletingName === a.name}>
                    {deletingName === a.name ? 'Removing…' : 'Remove'}
                  </button>
                  <button className="cancel-edit-btn" onClick={cancelDelete} disabled={deletingName === a.name}>Cancel</button>
                  {deleteError && <span className="label-edit-error" role="alert">{deleteError}</span>}
                </span>
              ) : (
                <button
                  className="account-delete-btn"
                  onClick={() => askDelete(a.name)}
                  aria-label={`Remove account "${a.name}"`}
                >
                  <span aria-hidden="true">✕</span>
                </button>
              )}
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
              onChange={e => { setNewName(e.target.value); setAddError('') }}
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
            {addError && <span className="label-edit-error" role="alert">{addError}</span>}
            <div className="add-account-actions">
              <button type="submit" className="submit-btn" disabled={!newName.trim() || adding}>
                {adding ? 'Adding…' : 'Add account'}
              </button>
              <button type="button" className="cancel-btn" onClick={cancelForm} disabled={adding}>Cancel</button>
            </div>
          </form>
        ) : (
          <button className="add-account-btn" onClick={() => setShowForm(true)}>+ Add account</button>
        )}
      </motion.div>
    </div>
  )
}
