import { useEffect, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { apiFetch } from '../api'
import { CATEGORY_COLORS } from '../constants'
import { fmtAmt } from '../format'

// ── Month helpers ─────────────────────────────────────────────────────────────

function monthDate(offset) {
  const n = new Date()
  n.setDate(1) // avoid day-of-month overflow when shifting months (e.g. May 31 -> July 1)
  n.setMonth(n.getMonth() + offset)
  return n
}

function monthParam(offset) {
  const d = monthDate(offset)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function monthLabel(offset) {
  return monthDate(offset).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
}

// Convert an `<input type="month">` value ("YYYY-MM") into an offset from the current month
function offsetFromMonthValue(value) {
  const [y, m] = value.split('-').map(Number)
  const now = monthDate(0)
  return (y - now.getFullYear()) * 12 + (m - 1 - now.getMonth())
}

// ── Count-up hook ─────────────────────────────────────────────────────────────

function useCountUp(target, duration = 720) {
  const reduceMotion = useReducedMotion()
  const [val, setVal] = useState(0)
  useEffect(() => {
    if (!target) { setVal(0); return }
    if (reduceMotion) { setVal(target); return }
    const start = performance.now()
    let raf
    const tick = (now) => {
      const t = Math.min((now - start) / duration, 1)
      const ease = 1 - Math.pow(1 - t, 3) // cubic ease-out
      setVal(target * ease)
      if (t < 1) raf = requestAnimationFrame(tick)
      else setVal(target)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, duration, reduceMotion])
  return val
}

// ── Skeleton primitives ───────────────────────────────────────────────────────

function Skel({ h = '0.85rem', w = '100%', r = 6, style }) {
  return <div className="dash-skeleton" style={{ height: h, width: w, borderRadius: r, ...style }} />
}

function SkelLines({ n = 4 }) {
  const ws = ['72%', '88%', '60%', '80%', '66%', '78%', '55%', '82%']
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
      {Array.from({ length: n }, (_, i) => <Skel key={i} w={ws[i % ws.length]} />)}
    </div>
  )
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, delta, lastLabel, type, delay = 0, selected = false, onSelect }) {
  const reduceMotion = useReducedMotion()
  const absVal   = Math.abs(value)
  const counted  = useCountUp(absVal)
  const absDelta = Math.abs(delta ?? 0)
  const hasDelta = delta !== null && delta !== undefined && delta !== 0

  let arrow = '', deltaDesc = '', deltaClass = 'dash-delta-neutral'
  if (hasDelta) {
    if (type === 'spending') {
      if (delta < 0) { arrow = '↑'; deltaDesc = `$${fmtAmt(absDelta)} more than ${lastLabel}`;   deltaClass = 'dash-delta-worse'  }
      else           { arrow = '↓'; deltaDesc = `$${fmtAmt(absDelta)} less than ${lastLabel}`;    deltaClass = 'dash-delta-better' }
    } else if (type === 'income') {
      if (delta > 0) { arrow = '↑'; deltaDesc = `$${fmtAmt(absDelta)} more than ${lastLabel}`;   deltaClass = 'dash-delta-better' }
      else           { arrow = '↓'; deltaDesc = `$${fmtAmt(absDelta)} less than ${lastLabel}`;    deltaClass = 'dash-delta-worse'  }
    } else {
      if (delta > 0) { arrow = '↑'; deltaDesc = `$${fmtAmt(absDelta)} better than ${lastLabel}`; deltaClass = 'dash-delta-better' }
      else           { arrow = '↓'; deltaDesc = `$${fmtAmt(absDelta)} worse than ${lastLabel}`;   deltaClass = 'dash-delta-worse'  }
    }
  }

  const valueClass = type === 'spending'
    ? 'color-negative'
    : type === 'income'
      ? 'color-positive'
      : value >= 0 ? 'color-positive' : 'color-negative'

  const displayValue = type === 'net'
    ? `${value >= 0 ? '+' : '−'}$${fmtAmt(counted)}`
    : `$${fmtAmt(counted)}`

  // Stable final value for screen readers — the count-up animation shouldn't be narrated mid-flight
  const finalValue = type === 'net'
    ? `${value >= 0 ? 'plus' : 'minus'} $${fmtAmt(absVal)}`
    : `$${fmtAmt(absVal)}`

  return (
    <motion.button
      type="button"
      className={`dash-stat-card${selected ? ' active' : ''}`}
      aria-pressed={selected}
      aria-label={`${label}: ${finalValue}. ${hasDelta ? deltaDesc + '. ' : ''}Show ${label.toLowerCase()} transactions for this month`}
      onClick={onSelect}
      initial={reduceMotion ? false : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.25, 0.1, 0.25, 1], delay: reduceMotion ? 0 : delay }}
    >
      <div className="dash-stat-label-row">
        <span className="dash-stat-label">{label}</span>
        <span className="dash-stat-chevron" aria-hidden="true">›</span>
      </div>
      <div className={`dash-stat-value ${valueClass}`}>{displayValue}</div>
      {hasDelta && <div className={`dash-stat-delta ${deltaClass}`}>{arrow} {deltaDesc}</div>}
    </motion.button>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function DashboardView({ onUpload, onViewHistory, onViewAccounts, userBadge, migrationBanner }) {
  const [monthOffset, setMonthOffset] = useState(0)
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadFailed, setLoadFailed] = useState(false)

  const param = monthParam(monthOffset)
  const label = monthLabel(monthOffset)
  const atCurrentMonth = monthOffset >= 0

  const [reloadToken, setReloadToken] = useState(0)
  const retry = () => setReloadToken(n => n + 1)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadFailed(false)
    apiFetch(`/dashboard?month=${param}`)
      .then(r => {
        if (!r.ok) throw new Error(`status ${r.status}`)
        return r.json()
      })
      .then(d => { if (!cancelled) { setData(d); setLoading(false) } })
      .catch(() => { if (!cancelled) { setData(null); setLoadFailed(true); setLoading(false) } })
    return () => { cancelled = true }
  }, [param, reloadToken])

  return (
    <div className="dashboard-page">
      <div className="dashboard-nav">
        <span className="dashboard-title">Finance</span>
        <div className="dashboard-nav-right">
          <button className="nav-link" onClick={onViewAccounts}>Accounts</button>
          <button className="nav-link" onClick={onViewHistory}>History →</button>
          <button className="nav-link" onClick={onUpload}>↑ Upload</button>
          {userBadge}
        </div>
      </div>

      {migrationBanner}

      <div className="dashboard-month-bar">
        <nav className="dash-month-nav" aria-label="Month navigation">
          <button
            type="button"
            className="dash-month-step"
            onClick={() => setMonthOffset(o => o - 1)}
            aria-label={`View ${monthLabel(monthOffset - 1)}`}
          >
            ‹
          </button>
          <h1 className="dash-month-label" aria-live="polite">{label}</h1>
          <button
            type="button"
            className="dash-month-step"
            onClick={() => setMonthOffset(o => o + 1)}
            disabled={atCurrentMonth}
            aria-label={atCurrentMonth ? 'Already viewing the current month' : `View ${monthLabel(monthOffset + 1)}`}
          >
            ›
          </button>
          <label className="dash-month-jump">
            <span className="sr-only">Jump to a specific month</span>
            <input
              type="month"
              className="dash-month-input"
              value={param}
              max={monthParam(0)}
              onChange={e => {
                if (!e.target.value) return
                setMonthOffset(Math.min(offsetFromMonthValue(e.target.value), 0))
              }}
            />
          </label>
        </nav>
      </div>

      {loading ? (
        <DashboardSkeleton />
      ) : loadFailed ? (
        <div className="dash-load-error" role="alert">
          <p className="dash-load-error-text">
            <strong>Could not load dashboard data.</strong> The server may be unreachable, or this account may not have any statements yet.
          </p>
          <button type="button" className="dash-retry-btn" onClick={retry}>Try again</button>
        </div>
      ) : (
        <DashboardBody data={data} monthParam={param} monthLabel={label} onViewHistory={onViewHistory} />
      )}
    </div>
  )
}

// ── Skeleton layout ───────────────────────────────────────────────────────────

function DashboardSkeleton() {
  return (
    <div className="dashboard-body" style={{ paddingTop: '1.25rem' }}>
      <div className="dash-stat-row">
        {[0, 1, 2].map(i => (
          <div key={i} className="dash-stat-card" style={{ cursor: 'default' }}>
            <Skel h="0.7rem" w="70px" style={{ marginBottom: '0.65rem' }} />
            <Skel h="1.75rem" w="110px" />
          </div>
        ))}
      </div>
      <div className="dash-middle-row">
        <div className="dash-card"><SkelLines n={5} /></div>
        <div className="dash-card"><SkelLines n={4} /></div>
      </div>
      <div className="dash-card dash-recent-card"><SkelLines n={8} /></div>
    </div>
  )
}

// ── Transaction table (shared by Recent Transactions and drill-down) ─────────

function TransactionTable({ rows, caption, reduceMotion, baseDelay = 0 }) {
  return (
    <table className="dash-recent-table">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr>
          <th scope="col" className="sr-only">Date</th>
          <th scope="col" className="sr-only">Description</th>
          <th scope="col" className="sr-only">Account</th>
          <th scope="col" className="sr-only">Amount</th>
          <th scope="col" className="sr-only">Category</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((t, i) => (
          <motion.tr
            key={i}
            className="dash-recent-row"
            initial={reduceMotion ? false : { opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.2, ease: 'easeOut', delay: baseDelay + i * 0.04 }}
          >
            <td className="dash-txn-date">{t.date || '—'}</td>
            <td className="dash-txn-name">{t.display_name || t.description}</td>
            <td className="dash-txn-account">{t.account_name || ''}</td>
            <td className={`dash-txn-amount ${t.amount < 0 ? 'negative' : 'positive'}`}>
              {t.amount < 0 ? '−' : '+'}${fmtAmt(Math.abs(t.amount))}
            </td>
            <td className="dash-txn-cat">
              <span className="dash-cat-dot" style={{ background: CATEGORY_COLORS[t.category] ?? '#aeaeb2' }} />
              {t.category}
            </td>
          </motion.tr>
        ))}
      </tbody>
    </table>
  )
}

// ── Populated body ────────────────────────────────────────────────────────────

function DashboardBody({ data, monthParam, monthLabel, onViewHistory }) {
  const { current_month: cm, top_categories, category_count, upcoming_recurring, recent_transactions } = data
  const vm = cm.vs_last_month
  const reduceMotion = useReducedMotion()

  // Trigger bar animations after first paint
  const [barsReady, setBarsReady] = useState(false)
  useEffect(() => {
    if (reduceMotion) { setBarsReady(true); return }
    const id = requestAnimationFrame(() => setBarsReady(true))
    return () => cancelAnimationFrame(id)
  }, [reduceMotion])

  // Drill-down: pick a stat or a category to see the transactions behind it
  const [drill, setDrill]         = useState(null) // { key, label, kind, category }
  const [drillTxns, setDrillTxns] = useState(null)
  const [drillLoading, setDrillLoading] = useState(false)
  const [drillFailed, setDrillFailed]   = useState(false)

  function toggleDrill(next) {
    setDrill(prev => (prev && prev.key === next.key) ? null : next)
  }

  function retryDrill() {
    setDrill(prev => prev && { ...prev }) // new reference re-triggers the fetch effect
  }

  useEffect(() => {
    if (!drill) { setDrillTxns(null); setDrillFailed(false); return }
    let cancelled = false
    setDrillLoading(true)
    setDrillFailed(false)
    const params = new URLSearchParams({ month: monthParam })
    if (drill.kind)     params.set('kind', drill.kind)
    if (drill.category) params.set('category', drill.category)
    apiFetch(`/dashboard/transactions?${params}`)
      .then(r => {
        if (!r.ok) throw new Error(`status ${r.status}`)
        return r.json()
      })
      .then(d => { if (!cancelled) { setDrillTxns(d.transactions); setDrillLoading(false) } })
      .catch(() => { if (!cancelled) { setDrillTxns(null); setDrillFailed(true); setDrillLoading(false) } })
    return () => { cancelled = true }
  }, [drill, monthParam])

  const introInitial = reduceMotion ? false : { opacity: 0, y: 14 }

  return (
    <motion.div
      className="dashboard-body"
      initial={reduceMotion ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: 'easeOut' }}
    >
      {/* Stat row — each card staggers 60ms after the previous; click any to see what's behind it */}
      <div className="dash-stat-row">
        <StatCard label="Total Spent" value={cm.spending} delta={vm.spending_delta} lastLabel={vm.label} type="spending" delay={0.05}
          selected={drill?.key === 'spending'} onSelect={() => toggleDrill({ key: 'spending', label: 'Total Spent', kind: 'spending' })} />
        <StatCard label="Income"      value={cm.income}   delta={vm.income_delta}   lastLabel={vm.label} type="income"   delay={0.11}
          selected={drill?.key === 'income'} onSelect={() => toggleDrill({ key: 'income', label: 'Income', kind: 'income' })} />
        <StatCard label="Net"         value={cm.net}      delta={vm.net_delta}      lastLabel={vm.label} type="net"      delay={0.17}
          selected={drill?.key === 'net'} onSelect={() => toggleDrill({ key: 'net', label: 'Net', kind: null })} />
      </div>

      {/* Drill-down panel — appears beneath the stat row when a stat or category is selected */}
      {drill && (
        <motion.div
          className="dash-card dash-drilldown"
          initial={reduceMotion ? false : { opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, ease: 'easeOut' }}
        >
          <div className="dash-drilldown-header">
            <p className="dash-drilldown-title">
              <strong>{drill.label}</strong> · {monthLabel}
              {!drillLoading && drillTxns && (
                <span className="dash-drilldown-count"> · {drillTxns.length} transaction{drillTxns.length === 1 ? '' : 's'}</span>
              )}
            </p>
            <button type="button" className="dash-drilldown-clear" onClick={() => setDrill(null)}>Clear filter</button>
          </div>
          <div aria-live="polite">
            {drillLoading
              ? <SkelLines n={3} />
              : drillFailed
                ? (
                  <div className="dash-drilldown-error" role="alert">
                    <p className="dash-drilldown-error-text">
                      Could not load these transactions. The server may be unreachable.
                    </p>
                    <button type="button" className="dash-retry-btn" onClick={retryDrill}>Try again</button>
                  </div>
                )
                : !drillTxns || drillTxns.length === 0
                  ? <p className="dash-drilldown-empty">No matching transactions in {monthLabel}.</p>
                  : <TransactionTable rows={drillTxns} caption={`${drill.label} transactions for ${monthLabel}`} reduceMotion={reduceMotion} />
            }
          </div>
        </motion.div>
      )}

      {/* Middle row */}
      <div className="dash-middle-row">

        {/* Top spending categories */}
        <motion.div
          className="dash-card"
          initial={introInitial}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: 'easeOut', delay: reduceMotion ? 0 : 0.23 }}
        >
          <h3 className="dash-card-title">Top Spending</h3>
          {top_categories.length === 0
            ? <p className="dash-empty">No spending data for {cm.label}</p>
            : (
              <>
                <ul className="dash-cat-list">
                  {top_categories.map((c, i) => {
                    const key = `cat:${c.category}`
                    const selected = drill?.key === key
                    return (
                      <li key={c.category}>
                        <button
                          type="button"
                          className={`dash-cat-item${selected ? ' active' : ''}`}
                          aria-pressed={selected}
                          aria-label={`${c.category}: $${fmtAmt(c.amount)}, ${c.pct.toFixed(0)} percent of spending. Show ${c.category} transactions for this month`}
                          onClick={() => toggleDrill({ key, label: c.category, category: c.category })}
                        >
                          <span className="dash-cat-dot" style={{ background: CATEGORY_COLORS[c.category] ?? '#aeaeb2' }} />
                          <span className="dash-cat-name">{c.category}</span>
                          <span className="dash-cat-amount">${fmtAmt(c.amount)}</span>
                          <span className="dash-cat-pct">{c.pct.toFixed(0)}%</span>
                          <span className="dash-cat-chevron" aria-hidden="true">›</span>
                          <span className="dash-cat-bar-wrap">
                            <span
                              className="dash-cat-bar-fill"
                              style={{
                                transform: barsReady ? `scaleX(${c.pct / 100})` : 'scaleX(0)',
                                background: CATEGORY_COLORS[c.category] ?? 'rgba(255,255,255,0.25)',
                                transitionDelay: `${i * 55}ms`,
                              }}
                            />
                          </span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
                {category_count > top_categories.length && (
                  <p className="dash-cat-more">
                    +{category_count - top_categories.length} more categor{category_count - top_categories.length === 1 ? 'y' : 'ies'} not shown
                  </p>
                )}
              </>
            )
          }
        </motion.div>

        {/* Upcoming recurring */}
        <motion.div
          className="dash-card"
          initial={introInitial}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: 'easeOut', delay: reduceMotion ? 0 : 0.29 }}
        >
          <h3 className="dash-card-title">Upcoming Charges</h3>
          {upcoming_recurring.length === 0
            ? <p className="dash-empty">No upcoming charges</p>
            : (
              <ul className="dash-recurring-list">
                {upcoming_recurring.map((r, i) => {
                  const urgency = r.days_until <= 3 ? 'urgent-red' : r.days_until <= 7 ? 'urgent-yellow' : ''
                  return (
                    <li key={i} className={`dash-recurring-item ${urgency}`}>
                      <div className="dash-recurring-main">
                        <span className="dash-recurring-name">{r.display_name}</span>
                        <span className="dash-recurring-amount">${fmtAmt(Math.abs(r.typical_amount))}</span>
                      </div>
                      <div className="dash-recurring-meta">
                        <span className="dash-type-badge">{r.type.replace('_', ' ')}</span>
                        <span className={`dash-days-until ${urgency}`}>
                          {r.days_until === 0 ? 'today' : `in ${r.days_until} day${r.days_until === 1 ? '' : 's'}`}
                        </span>
                      </div>
                    </li>
                  )
                })}
              </ul>
            )
          }
        </motion.div>
      </div>

      {/* Recent transactions */}
      <motion.div
        className="dash-card dash-recent-card"
        initial={introInitial}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28, ease: 'easeOut', delay: reduceMotion ? 0 : 0.35 }}
      >
        <div className="dash-card-header">
          <h3 className="dash-card-title">Recent Transactions</h3>
          <button className="nav-link" style={{ fontSize: '0.85rem' }} onClick={onViewHistory}>View all →</button>
        </div>
        {recent_transactions.length === 0
          ? <p className="dash-empty">Upload a statement to see transactions</p>
          : <TransactionTable rows={recent_transactions} caption="Most recent transactions across all accounts"
              reduceMotion={reduceMotion} baseDelay={reduceMotion ? 0 : 0.38} />
        }
      </motion.div>
    </motion.div>
  )
}
