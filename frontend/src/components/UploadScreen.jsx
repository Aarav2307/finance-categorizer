import { useRef, useState } from 'react'
import { motion } from 'framer-motion'

function defaultLabel() {
  return new Date().toLocaleString('default', { month: 'long', year: 'numeric' })
}

export default function UploadScreen({ onUpload, onViewHistory, onViewAccounts, onViewDashboard, error, userBadge, accounts = [] }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [pending, setPending] = useState(null)
  const [label, setLabel] = useState(defaultLabel())
  const [selectedAccount, setSelectedAccount] = useState('')  // '' = none, 'NEW' = adding new
  const [newAccountName, setNewAccountName] = useState('')
  const [newAccountType, setNewAccountType] = useState('bank')

  function handleFile(file) {
    if (file && (file.name.endsWith('.csv') || file.name.endsWith('.pdf'))) {
      setPending(file)
    }
  }

  function getAccountName() {
    if (selectedAccount === 'NEW') return newAccountName.trim()
    return selectedAccount
  }

  function getAccountType() {
    if (selectedAccount === 'NEW') return newAccountType
    const acct = accounts.find(a => a.name === selectedAccount)
    return acct?.type || ''
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (!pending) return
    onUpload(pending, label, getAccountName(), getAccountType())
  }

  const canSubmit = pending && (
    selectedAccount === '' ||
    (selectedAccount === 'NEW' && newAccountName.trim()) ||
    (selectedAccount !== 'NEW' && selectedAccount !== '')
  )

  return (
    <div className="upload-screen">
      <div className="upload-glow upload-glow-1" />
      <div className="upload-glow upload-glow-2" />

      <nav className="upload-nav">
        <button className="back-btn" onClick={onViewDashboard}>← Dashboard</button>
        <div className="upload-nav-right">
          <button className="nav-link" onClick={onViewAccounts}>Accounts</button>
          <button className="nav-link" onClick={onViewHistory}>History →</button>
          {userBadge}
        </div>
      </nav>

      <motion.div className="upload-hero" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22, ease: 'easeOut' }}>
        <div className="upload-badge">✦ AI-Powered · Runs Locally</div>

        <h1 className="upload-title">Understand your<br/>money instantly.</h1>

        <p className="upload-subtitle">
          Drop a bank statement and get every transaction categorized,
          charted, and ready to explore.
        </p>

        <div
          className={`drop-zone ${dragging ? 'dragging' : ''} ${pending ? 'has-file' : ''}`}
          onClick={() => inputRef.current.click()}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => {
            e.preventDefault()
            setDragging(false)
            handleFile(e.dataTransfer.files[0])
          }}
        >
          <div className="drop-icon-wrap">
            <span>{pending ? '✓' : '↑'}</span>
          </div>
          <p className="drop-text">
            {pending ? pending.name : 'Drop your CSV or PDF here'}
          </p>
          {!pending && <p className="drop-subtext">or click to browse files</p>}
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.pdf"
            style={{ display: 'none' }}
            onChange={e => handleFile(e.target.files[0])}
          />
        </div>

        {pending && (
          <form className="upload-meta-form" onSubmit={handleSubmit}>
            <div className="upload-meta-row">
              <input
                type="text"
                className="label-input"
                value={label}
                onChange={e => setLabel(e.target.value)}
                placeholder="Label (e.g. UWCU Jan 2026)"
              />
            </div>

            <div className="account-row">
              <select
                className="account-select"
                value={selectedAccount}
                onChange={e => setSelectedAccount(e.target.value)}
              >
                <option value="">No account</option>
                {accounts.map(a => (
                  <option key={a.name} value={a.name}>{a.name} ({a.type === 'bank' ? 'Bank' : 'Credit card'})</option>
                ))}
                <option value="NEW">+ Add new account…</option>
              </select>
            </div>

            {selectedAccount === 'NEW' && (
              <div className="new-account-row">
                <input
                  type="text"
                  className="label-input"
                  placeholder="Account name (e.g. Chase Checking)"
                  value={newAccountName}
                  onChange={e => setNewAccountName(e.target.value)}
                  autoFocus
                />
                <div className="account-type-toggle">
                  <label className={`acct-type-btn ${newAccountType === 'bank' ? 'active' : ''}`}>
                    <input type="radio" name="acctType" value="bank" checked={newAccountType === 'bank'} onChange={() => setNewAccountType('bank')} />
                    Bank account
                  </label>
                  <label className={`acct-type-btn ${newAccountType === 'credit_card' ? 'active' : ''}`}>
                    <input type="radio" name="acctType" value="credit_card" checked={newAccountType === 'credit_card'} onChange={() => setNewAccountType('credit_card')} />
                    Credit card
                  </label>
                </div>
              </div>
            )}

            <div className="upload-meta-row">
              <button type="submit" className="submit-btn" disabled={!canSubmit}>Categorize →</button>
            </div>
          </form>
        )}

        {error && <p className="upload-error">{error}</p>}

        <div className="upload-features">
          <span className="feat">📄 CSV & PDF</span>
          <span className="feat-divider" />
          <span className="feat">🤖 AI categorized</span>
          <span className="feat-divider" />
          <span className="feat">🔒 Runs locally</span>
        </div>
      </motion.div>
    </div>
  )
}
