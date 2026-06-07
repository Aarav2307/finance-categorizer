import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { fmtAmt } from '../format'

const CATEGORIES = [
  'Credit Card Bill', 'Dining', 'Education', 'Entertainment', 'Groceries', 'Health', 'Housing',
  'Income', 'Other', 'Shopping', 'Subscriptions', 'Transfers', 'Transport', 'Utilities', 'Zelle',
]

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function exportCSV(transactions) {
  const hasSt = transactions.some(t => t.upload_label)
  const header = [...(hasSt ? ['statement'] : []), 'date', 'description', 'amount', 'category']
  const rows = transactions.map(t => [
    ...(hasSt ? [`"${(t.upload_label || '').replace(/"/g, '""')}"`] : []),
    t.date || '',
    `"${t.description.replace(/"/g, '""')}"`,
    t.amount,
    t.category,
  ])
  const csv = [header, ...rows].map(r => r.join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'transactions.csv'
  a.click()
  URL.revokeObjectURL(url)
}

async function exportPDF(label) {
  const { default: jsPDF } = await import('jspdf')
  const { default: html2canvas } = await import('html2canvas')

  const BG = '#080c18'
  const PADDING = 40  // px on each side at scale 2 (effective 80px)
  const PDF_W = 900   // logical px width for PDF pages

  // Elements to hide during capture
  const hideEls = [
    ...document.querySelectorAll('.results-nav'),
    ...document.querySelectorAll('.filter-bar'),
    ...document.querySelectorAll('.export-dropdown-wrap'),
    ...document.querySelectorAll('.table-header input.filter-input'),
  ]
  const prevDisplay = hideEls.map(el => el.style.display)
  hideEls.forEach(el => { el.style.display = 'none' })

  // Inject a centered title above the table
  const titleEl = document.createElement('div')
  titleEl.style.cssText = `
    text-align:center; color:#fff; font-size:28px; font-weight:700;
    padding: 24px 0 12px; letter-spacing:0.02em;
  `
  titleEl.textContent = label || 'Transactions'
  const tableWrap = document.querySelector('.table-wrap')
  tableWrap?.parentElement?.insertBefore(titleEl, tableWrap)

  const scrollY = window.scrollY
  window.scrollTo(0, 0)

  // Capture each section separately for clean page breaks
  const sectionSelectors = ['.table-wrap', '.summary', '.cache-editor']
  const sectionCanvases = []

  for (const sel of sectionSelectors) {
    const el = document.querySelector(sel)
    if (!el) continue
    const c = await html2canvas(el, {
      scale: 2,
      backgroundColor: BG,
      useCORS: true,
      scrollY: 0,
      windowWidth: document.body.scrollWidth,
    })
    sectionCanvases.push(c)
  }

  window.scrollTo(0, scrollY)
  hideEls.forEach((el, i) => { el.style.display = prevDisplay[i] })
  titleEl.remove()

  if (sectionCanvases.length === 0) return

  // Build PDF: each section gets its own page(s)
  // Use the width of the first canvas as reference; scale all sections to match
  const refW = sectionCanvases[0].width
  const pageH = Math.floor(refW * 297 / 210)

  const pdf = new jsPDF({ orientation: 'portrait', unit: 'px', format: [refW / 2, pageH / 2] })
  let firstPage = true

  for (const canvas of sectionCanvases) {
    // Scale this canvas to refW if it differs
    const scaleX = refW / canvas.width
    const scaledH = Math.round(canvas.height * scaleX)

    const totalSubPages = Math.ceil(scaledH / pageH)

    for (let i = 0; i < totalSubPages; i++) {
      if (!firstPage) pdf.addPage()
      firstPage = false

      const sliceCanvas = document.createElement('canvas')
      sliceCanvas.width = refW
      sliceCanvas.height = pageH
      const ctx = sliceCanvas.getContext('2d')
      ctx.fillStyle = BG
      ctx.fillRect(0, 0, refW, pageH)
      // Draw scaled section slice
      ctx.drawImage(
        canvas,
        0, Math.round((i * pageH) / scaleX),   // source y
        canvas.width, Math.round(pageH / scaleX), // source h
        0, 0,                                    // dest x, y
        refW, pageH,                             // dest w, h
      )
      pdf.addImage(sliceCanvas.toDataURL('image/png'), 'PNG', 0, 0, refW / 2, pageH / 2)
    }
  }

  pdf.save(`${label || 'transactions'}.pdf`)
}

function toTitleCase(s) {
  return s.toLowerCase().replace(/\b\w/g, c => c.toUpperCase())
}

function categorySlug(cat) {
  return cat.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')
}

function isJunkWord(word) {
  if (/\d/.test(word)) return true
  if (word.length <= 2) return true
  if (word.length >= 8 && (word.match(/[aeiouAEIOU]/g) || []).length / word.length < 0.3) return true
  return false
}

function extractZellePerson(desc) {
  // Find "Zelle" anywhere — handles "Web Branch:Zelle NAME", "Zelle transfer to NAME", etc.
  const zelleIdx = desc.search(/zelle/i)
  if (zelleIdx === -1) return toTitleCase(desc)

  let rest = desc.slice(zelleIdx + 5).trim()
  // Strip "transfer to/from", "payment to/from" boilerplate
  rest = rest.replace(/^(?:transfer\s+)?(?:to|from|payment\s+(?:to|from))\s+/i, '')

  const parts = rest.replace(/\s+\d{6,}$/, '').trim().split(/\s+/)
  while (parts.length > 1 && isJunkWord(parts[parts.length - 1])) parts.pop()

  // Last word ≤ 4 chars means the name was truncated — use first name only
  if (parts.length > 1 && parts[parts.length - 1].length <= 4) {
    return toTitleCase(parts[0])
  }
  return toTitleCase(parts.join(' '))
}

function extractMonth(dateStr) {
  if (!dateStr) return null
  const mm = dateStr.includes('-') ? dateStr.slice(5, 7) : dateStr.slice(0, 2)
  const n = parseInt(mm, 10)
  return n >= 1 && n <= 12 ? mm : null
}

// ── Billing cycle helpers ────────────────────────────────────────────────────

function parseTxnDate(str) {
  if (!str) return null
  if (/^\d{4}-\d{2}-\d{2}$/.test(str)) {
    const [y, m, d] = str.split('-').map(Number)
    return new Date(y, m - 1, d)
  }
  if (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(str)) {
    const [m, d, y] = str.split('/').map(Number)
    return new Date(y, m - 1, d)
  }
  if (/^\d{1,2}\/\d{1,2}\/\d{2}$/.test(str)) {
    const [m, d, y] = str.split('/').map(Number)
    return new Date(2000 + y, m - 1, d)
  }
  return null
}

function getStatementPeriod(yr, mo, cycleDay) {
  if (cycleDay === 1) {
    return { start: new Date(yr, mo - 1, 1), end: new Date(yr, mo, 0) }
  }
  const prevMo = mo === 1 ? 12 : mo - 1
  const prevYr = mo === 1 ? yr - 1 : yr
  const lastDayPrev = new Date(prevYr, prevMo, 0).getDate()
  const startDay = Math.min(cycleDay, lastDayPrev)
  return {
    start: new Date(prevYr, prevMo - 1, startDay),
    end: new Date(yr, mo - 1, cycleDay - 1),
  }
}

function extractLabelMonth(label) {
  if (!label) return null
  const lower = label.toLowerCase()
  const full = ['january','february','march','april','may','june','july','august','september','october','november','december']
  for (let i = 0; i < full.length; i++) {
    const short = full[i].slice(0, 3)
    if (lower.includes(full[i]) || new RegExp(`\\b${short}\\b`).test(lower)) return i + 1
  }
  return null
}

export default function TransactionTable({ transactions, onCorrect, uploadLabel, zelleAliases = {}, onSaveZelleAliases, chartFilter, accounts = [], year = null }) {
  const [editingId, setEditingId] = useState(null)
  const [editValue, setEditValue] = useState('')
  const [savingId, setSavingId] = useState(null)
  const [saveError, setSaveError] = useState('')
  const [flashIds, setFlashIds] = useState(new Set())
  const [correctionNote, setCorrectionNote] = useState('')
  const [showExport, setShowExport] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')
  const [filter, setFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [monthFilter, setMonthFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [zellePersonFilter, setZellePersonFilter] = useState('')
  const [statementFilter, setStatementFilter] = useState(new Set())
  const [showStatementMenu, setShowStatementMenu] = useState(false)
  const [accountFilter, setAccountFilter] = useState('')
  const [billingMode, setBillingMode] = useState('calendar')
  const dropdownRef = useRef(null)
  const statementDropdownRef = useRef(null)

  // Close dropdowns on outside click
  useEffect(() => {
    function handler(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) setShowExport(false)
      if (statementDropdownRef.current && !statementDropdownRef.current.contains(e.target)) setShowStatementMenu(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Sync filters when a chart bar is clicked
  useEffect(() => {
    if (!chartFilter) return
    setMonthFilter(chartFilter.month || '')
    setCategoryFilter(chartFilter.category || '')
  }, [chartFilter])

  const availableAccounts = [...new Set(transactions.map(t => t.account_name).filter(Boolean))].sort()
  const hasAccounts = availableAccounts.length > 1

  // Billing cycle helpers
  const isCombinedView = Boolean(uploadLabel?.startsWith('All '))
  const selectedAccountObj = accounts.find(a => a.name === accountFilter) ?? null
  const autoAccountObj = (
    !accountFilter && availableAccounts.length === 1
      ? accounts.find(a => a.name === availableAccounts[0]) ?? null
      : null
  )
  const effectiveAccountObj = selectedAccountObj ?? autoAccountObj
  const showBillingToggle = Boolean(
    effectiveAccountObj?.type === 'credit_card' &&
    effectiveAccountObj?.cycle_start_day != null &&
    effectiveAccountObj.cycle_start_day > 1
  )

  // Reset to calendar mode when the toggle becomes hidden
  useEffect(() => {
    if (!showBillingToggle) setBillingMode('calendar')
  }, [showBillingToggle])

  // In Statement mode on an individual statement, clear month filter (all txns shown)
  useEffect(() => {
    if (billingMode === 'statement' && !isCombinedView) setMonthFilter('')
  }, [billingMode])

  function getYearForMonth(mm) {
    if (year) return parseInt(year, 10)
    for (const t of transactions) {
      if (extractMonth(t.date) !== mm) continue
      const d = t.date
      if (!d) continue
      const m1 = d.match(/^(\d{4})-\d{2}-\d{2}$/)
      if (m1) return parseInt(m1[1], 10)
      const m2 = d.match(/^\d{1,2}\/\d{1,2}\/(\d{4})$/)
      if (m2) return parseInt(m2[1], 10)
    }
    return new Date().getFullYear()
  }

  let billingPeriodHint = null
  if (showBillingToggle && billingMode === 'statement') {
    const fmt = d => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    if (!isCombinedView) {
      const labelMo = extractLabelMonth(uploadLabel)
      if (labelMo) {
        const yr = year ? parseInt(year, 10) : getYearForMonth(String(labelMo).padStart(2, '0'))
        const { start, end } = getStatementPeriod(yr, labelMo, effectiveAccountObj.cycle_start_day)
        billingPeriodHint = `${fmt(start)} – ${fmt(end)}`
      }
    } else if (monthFilter) {
      const yr = getYearForMonth(monthFilter)
      const { start, end } = getStatementPeriod(yr, parseInt(monthFilter, 10), effectiveAccountObj.cycle_start_day)
      billingPeriodHint = `${fmt(start)} – ${fmt(end)}`
    }
  }

  async function handlePDF() {
    setShowExport(false)
    setExporting(true)
    setExportError('')
    try {
      await exportPDF(uploadLabel)
    } catch (err) {
      setExportError(err.message || 'Could not export PDF. Try again.')
    } finally {
      setExporting(false)
    }
  }

  function startEdit(t) {
    setEditingId(t.id)
    setEditValue(t.category)
    setSaveError('')
  }

  function cancelEdit() {
    setEditingId(null)
    setEditValue('')
    setSaveError('')
  }

  async function handleSave(t) {
    if (editValue === t.category) { cancelEdit(); return }
    setSavingId(t.id)
    setSaveError('')
    try {
      await onCorrect(t.description, t.category, editValue)
      const matchIds = new Set(transactions.filter(x => x.description === t.description).map(x => x.id))
      setFlashIds(matchIds)
      if (matchIds.size > 1) {
        setCorrectionNote(`Updated ${matchIds.size} matching transactions`)
        setTimeout(() => setCorrectionNote(''), 2800)
      }
      setTimeout(() => setFlashIds(new Set()), 1400)
      cancelEdit()
    } catch (err) {
      setSaveError(err.message || 'Could not save category. Try again.')
    } finally {
      setSavingId(null)
    }
  }

  const availableMonths = [...new Set(
    transactions.map(t => extractMonth(t.date)).filter(Boolean)
  )].sort()

  const hasDateData = transactions.some(t => t.date)

  // Normalize stored alias keys to title case for cross-account compatibility
  const normalizedAliases = Object.fromEntries(
    Object.entries(zelleAliases).map(([k, v]) => [toTitleCase(k), v])
  )

  const zelleTransactions = transactions.filter(t => t.category === 'Zelle')
  const rawZelleNames = [...new Set(zelleTransactions.map(t => extractZellePerson(t.description)))].sort()

  // Names without a stored alias get resolved algorithmically
  const needsAlgo = rawZelleNames.filter(n => !normalizedAliases[n])

  // Pass 1: prefix dedup — "Kritin" → "Kritin Kaushik"
  const afterPrefix = Object.fromEntries(
    needsAlgo.map(name => {
      const longer = needsAlgo.find(
        n => n !== name && n.toLowerCase().startsWith(name.toLowerCase() + ' ')
      )
      return [name, longer || name]
    })
  )

  // Pass 2: first+last dedup — "Manan A Patel" + "Manan Patel" → "Manan Patel"
  const prefixResolved = [...new Set(Object.values(afterPrefix))]
  function firstLastKey(name) {
    const p = name.trim().split(/\s+/)
    return p.length >= 2 ? `${p[0]} ${p[p.length - 1]}`.toLowerCase() : p[0].toLowerCase()
  }
  const flGroups = {}
  for (const name of prefixResolved) {
    const key = firstLastKey(name)
    ;(flGroups[key] = flGroups[key] || []).push(name)
  }
  const flCanonical = {}
  for (const names of Object.values(flGroups)) {
    const best = names.sort((a, b) => a.split(' ').length - b.split(' ').length || a.length - b.length)[0]
    for (const n of names) flCanonical[n] = best
  }

  // Compose: stored aliases take priority, algorithmic fills the rest
  const zelleCanonicalMap = Object.fromEntries(
    rawZelleNames.map(name => [
      name,
      normalizedAliases[name] || flCanonical[afterPrefix[name]] || afterPrefix[name] || name,
    ])
  )
  const zellePeople = [...new Set(Object.values(zelleCanonicalMap))].sort()

  // Persist any newly discovered aliases so future uploads reuse them
  const zelleCanonicalMapRef = useRef({})
  zelleCanonicalMapRef.current = zelleCanonicalMap
  useEffect(() => {
    if (!onSaveZelleAliases) return
    const newAliases = {}
    for (const [raw, canonical] of Object.entries(zelleCanonicalMapRef.current)) {
      if (raw !== canonical && !normalizedAliases[raw]) newAliases[raw] = canonical
    }
    if (Object.keys(newAliases).length > 0) onSaveZelleAliases(newAliases)
  }, [transactions.length])
  const showZelleFilter = zellePeople.length > 1

  const hasStatements = transactions.some(t => t.upload_label)
  const availableStatements = hasStatements
    ? [...new Set(transactions.map(t => t.upload_label).filter(Boolean))]
    : []

  const hasCCPayments = transactions.some(t => t.auto_transfer)

  // Derive category list from ALL transactions (not filtered) so the dropdown
  // doesn't shrink as other filters narrow the view.
  const availableCategories = [...new Set(transactions.map(t => t.category).filter(Boolean))].sort()

  const filtered = transactions.filter(t => {
    if (filter.trim() && !t.description.toLowerCase().includes(filter.toLowerCase())) return false
    if (typeFilter === 'expenses' && t.amount >= 0) return false
    if (typeFilter === 'income' && t.amount <= 0) return false
    if (monthFilter) {
      if (billingMode === 'statement' && showBillingToggle && isCombinedView) {
        const yr = getYearForMonth(monthFilter)
        const { start, end } = getStatementPeriod(yr, parseInt(monthFilter, 10), effectiveAccountObj.cycle_start_day)
        const txDate = parseTxnDate(t.date)
        if (!txDate || txDate < start || txDate > end) return false
      } else {
        if (extractMonth(t.date) !== monthFilter) return false
      }
    }
    if (categoryFilter && t.category !== categoryFilter) return false
    if (zellePersonFilter && (t.category !== 'Zelle' || (normalizedAliases[extractZellePerson(t.description)] || zelleCanonicalMap[extractZellePerson(t.description)]) !== zellePersonFilter)) return false
    if (statementFilter.size > 0 && !statementFilter.has(t.upload_label)) return false
    if (accountFilter && t.account_name !== accountFilter) return false
    return true
  })

  const isFiltering = filter.trim() || typeFilter !== 'all' || monthFilter || categoryFilter || zellePersonFilter || statementFilter.size > 0 || accountFilter

  return (
    <div className="table-wrap">
      <div className="table-header">
        <h2>Transactions</h2>
        {correctionNote && <span className="correction-note" role="status">{correctionNote}</span>}

        <input
          className="filter-input"
          type="text"
          placeholder="Filter by merchant…"
          value={filter}
          onChange={e => setFilter(e.target.value)}
        />

        <div className="export-dropdown-wrap" ref={dropdownRef}>
          <button
            className="export-trigger"
            onClick={() => setShowExport(v => !v)}
            disabled={exporting}
          >
            {exporting ? 'Exporting…' : 'Export'}
          </button>
          {showExport && (
            <div className="export-menu">
              <button onClick={() => { exportCSV(transactions); setShowExport(false) }}>
                Export as CSV
              </button>
              <button onClick={handlePDF}>
                Export as PDF
              </button>
            </div>
          )}
          {exportError && <span className="export-error" role="alert">{exportError}</span>}
        </div>
      </div>

      <div className="filter-bar">
        <div className="type-filter">
          {['all', 'expenses', 'income'].map(type => (
            <button
              key={type}
              className={`type-pill ${typeFilter === type ? 'active' : ''}`}
              onClick={() => setTypeFilter(type)}
            >
              {type === 'all' ? 'All' : type === 'expenses' ? 'Expenses' : 'Income'}
            </button>
          ))}
        </div>

        {hasDateData && (
          billingMode === 'statement' && showBillingToggle && !isCombinedView ? (
            billingPeriodHint && (
              <span className="statement-period-badge">{billingPeriodHint}</span>
            )
          ) : (
            availableMonths.length > 0 && (
              <select
                className="month-select"
                value={monthFilter}
                onChange={e => setMonthFilter(e.target.value)}
              >
                <option value="">All months</option>
                {availableMonths.map(mm => (
                  <option key={mm} value={mm}>
                    {MONTH_NAMES[parseInt(mm, 10) - 1]}
                  </option>
                ))}
              </select>
            )
          )
        )}

        {showBillingToggle && (
          <div className="billing-toggle">
            <button
              className={`billing-toggle-btn ${billingMode === 'calendar' ? 'active' : ''}`}
              onClick={() => setBillingMode('calendar')}
            >Calendar</button>
            <button
              className={`billing-toggle-btn ${billingMode === 'statement' ? 'active' : ''}`}
              onClick={() => setBillingMode('statement')}
            >Statement</button>
          </div>
        )}

        {availableCategories.length > 1 && (
          <select
            className="month-select"
            value={categoryFilter}
            onChange={e => setCategoryFilter(e.target.value)}
          >
            <option value="">All categories</option>
            {availableCategories.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        )}

        {showZelleFilter && (
          <select
            className="month-select"
            value={zellePersonFilter}
            onChange={e => setZellePersonFilter(e.target.value)}
          >
            <option value="">All Zelle</option>
            {zellePeople.map(p => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        )}

        {hasAccounts && availableAccounts.length > 1 && (
          <select
            className="month-select"
            value={accountFilter}
            onChange={e => setAccountFilter(e.target.value)}
          >
            <option value="">All accounts</option>
            {availableAccounts.map(a => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        )}

        {hasStatements && availableStatements.length > 1 && (
          <div className="statement-dropdown-wrap" ref={statementDropdownRef}>
            <button
              className="statement-trigger"
              onClick={() => setShowStatementMenu(v => !v)}
              aria-expanded={showStatementMenu}
              aria-haspopup="true"
            >
              <span>
                {statementFilter.size === 0
                  ? 'All statements'
                  : `${statementFilter.size} statement${statementFilter.size !== 1 ? 's' : ''}`}
              </span>
              <span className="statement-trigger-caret" aria-hidden="true" />
            </button>
            {showStatementMenu && (
              <div className="statement-menu">
                <label className="statement-option statement-all">
                  <input
                    type="checkbox"
                    ref={el => { if (el) el.indeterminate = statementFilter.size > 0 && statementFilter.size < availableStatements.length }}
                    checked={statementFilter.size === 0}
                    onChange={() => setStatementFilter(new Set())}
                  />
                  All statements
                </label>
                <div className="statement-divider" />
                {availableStatements.map(s => (
                  <label key={s} className="statement-option">
                    <input
                      type="checkbox"
                      checked={statementFilter.has(s)}
                      onChange={() => setStatementFilter(prev => {
                        const next = new Set(prev)
                        next.has(s) ? next.delete(s) : next.add(s)
                        return next
                      })}
                    />
                    {s}
                  </label>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {billingPeriodHint && isCombinedView && (
        <p className="billing-period-hint">{billingPeriodHint}</p>
      )}

      <div className="table-scroll">
      <table>
        <caption className="sr-only">{uploadLabel ? `Transactions for ${uploadLabel}` : 'Transactions'}</caption>
        <thead>
          <tr>
            {hasStatements && <th scope="col">Statement</th>}
            {hasAccounts && <th scope="col">Account</th>}
            {hasDateData && <th scope="col">Date</th>}
            <th scope="col">Description</th>
            <th scope="col">Amount</th>
            <th scope="col">Category</th>
          </tr>
        </thead>
        <tbody key={uploadLabel}>
          {filtered.length === 0 ? (
            <tr>
              <td
                colSpan={[hasStatements, hasAccounts, hasDateData, true, true, true].filter(Boolean).length}
                className="empty-category-state"
              >
                {categoryFilter
                  ? `No ${categoryFilter} transactions for this period`
                  : isFiltering
                    ? 'No transactions match these filters'
                    : 'No transactions to show'}
              </td>
            </tr>
          ) : (
            filtered.map((t, i) => (
              <motion.tr
                key={t.id}
                className={[t.needs_review ? 'needs-review' : '', flashIds.has(t.id) ? 'correction-flash' : ''].filter(Boolean).join(' ')}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.16, ease: 'easeOut', delay: Math.min(i * 0.022, 0.55) }}
              >
                {hasStatements && <td className="date-cell">{t.upload_label || '—'}</td>}
                {hasAccounts && <td className="date-cell account-cell">{t.account_name || '—'}</td>}
                {hasDateData && <td className="date-cell">{t.date || '—'}</td>}
                <td title={t.display_name && t.display_name !== t.description ? t.description : undefined}>
                  {t.display_name || t.description}
                </td>
                <td className={t.amount < 0 ? 'negative' : 'positive'}>
                  {t.amount < 0 ? '−' : '+'}{fmtAmt(Math.abs(t.amount))}
                </td>
                <td className={`category-td${editingId === t.id ? ' editing' : ''}`}>
                  {editingId === t.id ? (
                    <div className="category-edit">
                      <select value={editValue} onChange={e => setEditValue(e.target.value)} autoFocus onClick={e => e.stopPropagation()}>
                        {CATEGORIES.map(c => <option key={c}>{c}</option>)}
                      </select>
                      <button className="save-edit-btn" onClick={e => { e.stopPropagation(); handleSave(t) }} disabled={savingId === t.id}>
                        {savingId === t.id ? 'Saving…' : 'Save'}
                      </button>
                      <button className="cancel-edit-btn" onClick={e => { e.stopPropagation(); cancelEdit() }} disabled={savingId === t.id}>Cancel</button>
                      {saveError && <span className="label-edit-error" role="alert">{saveError}</span>}
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="category-cell"
                      onClick={() => startEdit(t)}
                      aria-label={`Change category for ${t.display_name || t.description}, currently ${t.category}`}
                    >
                      <span className={`cat-pill cat-pill--${categorySlug(t.category)}`}>{t.category}</span>
                      {t.recurring_frequency && (
                        <span className="recurring-badge"><span className="recurring-icon-pulse" aria-hidden="true" /> {t.recurring_frequency}</span>
                      )}
                      <span className="edit-hint" aria-hidden="true">Edit</span>
                    </button>
                  )}
                </td>
              </motion.tr>
            ))
          )}
        </tbody>
      </table>
      </div>

      {hasCCPayments && (
        <div className="cc-exclusion-note">
          Credit card payments automatically excluded from spending totals to avoid double-counting.
        </div>
      )}

      {filtered.length > 0 && (() => {
        // Exclude Transfers unless the user is explicitly viewing that category
        const forTotals = categoryFilter === 'Transfers'
          ? filtered
          : filtered.filter(t => t.category !== 'Transfers')
        const transfersExcluded = filtered.length - forTotals.length

        const spent  = forTotals.filter(t => t.amount < 0).reduce((s, t) => s + t.amount, 0)
        const income = forTotals.filter(t => t.amount > 0).reduce((s, t) => s + t.amount, 0)

        let amountEl
        if (categoryFilter) {
          const total = forTotals.reduce((s, t) => s + t.amount, 0)
          amountEl = (
            <span className={total < 0 ? 'negative' : 'positive'}>
              Total {categoryFilter}: {total < 0 ? '−' : '+'}{fmtAmt(Math.abs(total))}
            </span>
          )
        } else if (typeFilter === 'expenses') {
          amountEl = <span className="negative">Total spent: −{fmtAmt(Math.abs(spent))}</span>
        } else if (typeFilter === 'income') {
          amountEl = <span className="positive">Total income: +{fmtAmt(income)}</span>
        } else {
          amountEl = (
            <span className="totals-both">
              <span className="negative">Spent: −{fmtAmt(Math.abs(spent))}</span>
              <span className="totals-dot">·</span>
              <span className="positive">Income: +{fmtAmt(income)}</span>
            </span>
          )
        }

        return (
          <div className="filter-total">
            <span className="totals-count">
              Showing {filtered.length} transaction{filtered.length !== 1 ? 's' : ''}
              {transfersExcluded > 0 && (
                <span className="totals-transfers-note"> ({transfersExcluded} transfer{transfersExcluded !== 1 ? 's' : ''} excluded)</span>
              )}
            </span>
            {amountEl}
          </div>
        )
      })()}
    </div>
  )
}
