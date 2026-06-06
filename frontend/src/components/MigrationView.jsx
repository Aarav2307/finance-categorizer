import { useState } from 'react'

export default function MigrationView({ orphanedUploads, accounts, onSave, onBack, onAddAccount }) {
  const [selections, setSelections] = useState({})
  const [saving, setSaving] = useState(false)
  const [confirmation, setConfirmation] = useState(null)

  const totalOrphaned = orphanedUploads.reduce((s, u) => s + u.orphaned_count, 0)
  const assignedCount = Object.values(selections).filter(Boolean).length
  const unassignedCount = orphanedUploads.length - assignedCount

  function select(uploadId, value) {
    if (value === '__ADD__') {
      onAddAccount()
      return
    }
    setSelections(prev => ({ ...prev, [uploadId]: value }))
  }

  async function handleSave() {
    setSaving(true)
    const assignments = orphanedUploads
      .filter(u => selections[u.id])
      .map(u => {
        const acct = accounts.find(a => a.name === selections[u.id])
        return {
          upload_id: u.id,
          account_name: selections[u.id],
          account_type: acct?.type || '',
        }
      })
    const result = await onSave(assignments)
    setConfirmation(result.assigned)
    setSaving(false)
  }

  if (confirmation !== null) {
    return (
      <div className="migration-view">
        <div className="migration-success-wrap">
          <div className="migration-success">
            <div className="migration-success-icon">✓</div>
            <h2>{confirmation} transaction{confirmation !== 1 ? 's' : ''} assigned</h2>
            <p>All selected uploads have been linked to their accounts.</p>
            <button className="submit-btn" onClick={onBack}>Done</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="migration-view">
      <div className="migration-nav">
        <button className="back-btn" onClick={onBack}>← Back</button>
      </div>

      <div className="migration-content">
        <div className="migration-heading">
          <h1>Assign Accounts</h1>
          <p className="migration-desc">
            {totalOrphaned} transaction{totalOrphaned !== 1 ? 's' : ''} across{' '}
            {orphanedUploads.length} upload{orphanedUploads.length !== 1 ? 's' : ''} have no
            account assigned. Linking them enables accurate spending totals and
            credit card double-counting prevention.
          </p>
        </div>

        <div className="migration-groups">
          {orphanedUploads.map(u => (
            <div key={u.id} className={`migration-row ${selections[u.id] ? 'assigned' : ''}`}>
              <div className="migration-row-info">
                <span className="migration-upload-label">"{u.label}"</span>
                <span className="migration-txn-count">
                  {u.orphaned_count} transaction{u.orphaned_count !== 1 ? 's' : ''}
                </span>
              </div>
              <select
                className="account-select migration-select"
                value={selections[u.id] || ''}
                onChange={e => select(u.id, e.target.value)}
              >
                <option value="">Assign to account…</option>
                {accounts.map(a => (
                  <option key={a.name} value={a.name}>
                    {a.name} ({a.type === 'bank' ? 'Bank' : 'Credit card'})
                  </option>
                ))}
                <option value="__ADD__">+ Add new account…</option>
              </select>
            </div>
          ))}
        </div>

        <div className="migration-footer">
          <button
            className="submit-btn"
            onClick={handleSave}
            disabled={saving || assignedCount === 0}
          >
            {saving ? 'Saving…' : `Save ${assignedCount} assignment${assignedCount !== 1 ? 's' : ''}`}
          </button>
          {unassignedCount > 0 && assignedCount > 0 && (
            <p className="migration-skip-note">
              {unassignedCount} upload{unassignedCount !== 1 ? 's' : ''} without a selection will be skipped.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
