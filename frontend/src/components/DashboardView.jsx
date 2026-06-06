import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { apiFetch } from '../api'
import { CATEGORY_COLORS } from '../constants'
import { fmtAmt } from '../format'

// ── Count-up hook ─────────────────────────────────────────────────────────────

function useCountUp(target, duration = 720) {
  const [val, setVal] = useState(0)
  useEffect(() => {
    if (!target) { setVal(0); return }
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
  }, [target, duration])
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

function StatCard({ label, value, delta, lastLabel, type, delay = 0 }) {
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

  const glowStyle = type === 'net' ? {
    borderLeft: `3px solid ${value >= 0 ? 'var(--green)' : 'var(--red)'}`,
    boxShadow: value >= 0
      ? '0 0 24px rgba(52,211,153,0.08)'
      : '0 0 24px rgba(248,113,113,0.08)',
  } : {}

  return (
    <motion.div
      className="dash-stat-card"
      style={glowStyle}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.25, 0.1, 0.25, 1], delay }}
    >
      <div className="dash-stat-label">{label}</div>
      <div className={`dash-stat-value ${valueClass}`}>{displayValue}</div>
      {hasDelta && <div className={`dash-stat-delta ${deltaClass}`}>{arrow} {deltaDesc}</div>}
    </motion.div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function DashboardView({ onUpload, onViewHistory, onViewAccounts, userBadge, migrationBanner }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)

  const monthParam = (() => {
    const n = new Date()
    return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}`
  })()

  useEffect(() => {
    apiFetch(`/dashboard?month=${monthParam}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

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

      {loading ? (
        <DashboardSkeleton />
      ) : !data ? (
        <p className="dash-load-error">Could not load dashboard data.</p>
      ) : (
        <DashboardBody data={data} onViewHistory={onViewHistory} />
      )}
    </div>
  )
}

// ── Skeleton layout ───────────────────────────────────────────────────────────

function DashboardSkeleton() {
  return (
    <div className="dashboard-body">
      <Skel h="2rem" w="160px" style={{ margin: '1.75rem 0 1.25rem' }} />
      <div className="dash-stat-row">
        {[0, 1, 2].map(i => (
          <div key={i} className="dash-stat-card">
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

// ── Populated body ────────────────────────────────────────────────────────────

function DashboardBody({ data, onViewHistory }) {
  const { current_month: cm, top_categories, upcoming_recurring, recent_transactions } = data
  const vm = cm.vs_last_month

  // Trigger bar animations after first paint
  const [barsReady, setBarsReady] = useState(false)
  useEffect(() => {
    const id = requestAnimationFrame(() => setBarsReady(true))
    return () => cancelAnimationFrame(id)
  }, [])

  return (
    <motion.div
      className="dashboard-body"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: 'easeOut' }}
    >
      <h1 className="dash-month-label">{cm.label}</h1>

      {/* Stat row — each card staggers 60ms after the previous */}
      <div className="dash-stat-row">
        <StatCard label="Total Spent" value={cm.spending} delta={vm.spending_delta} lastLabel={vm.label} type="spending" delay={0.05} />
        <StatCard label="Income"      value={cm.income}   delta={vm.income_delta}   lastLabel={vm.label} type="income"   delay={0.11} />
        <StatCard label="Net"         value={cm.net}      delta={vm.net_delta}      lastLabel={vm.label} type="net"      delay={0.17} />
      </div>

      {/* Middle row */}
      <div className="dash-middle-row">

        {/* Top spending categories */}
        <motion.div
          className="dash-card"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: 'easeOut', delay: 0.23 }}
        >
          <h3 className="dash-card-title">Top Spending</h3>
          {top_categories.length === 0
            ? <p className="dash-empty"><span className="dash-empty-icon">📊</span>No spending data for {cm.label}</p>
            : (
              <ul className="dash-cat-list">
                {top_categories.map((c, i) => (
                  <li key={c.category} className="dash-cat-item">
                    <span className="dash-cat-dot" style={{ background: CATEGORY_COLORS[c.category] ?? '#aeaeb2' }} />
                    <span className="dash-cat-name">{c.category}</span>
                    <span className="dash-cat-amount">${fmtAmt(c.amount)}</span>
                    <span className="dash-cat-pct">{c.pct.toFixed(0)}%</span>
                    <div className="dash-cat-bar-wrap">
                      <div
                        className="dash-cat-bar-fill"
                        style={{
                          width: barsReady ? `${c.pct}%` : '0%',
                          background: CATEGORY_COLORS[c.category] ?? 'rgba(255,255,255,0.25)',
                          transition: `width 0.55s cubic-bezier(0.25,0.1,0.25,1) ${i * 55}ms`,
                        }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            )
          }
        </motion.div>

        {/* Upcoming recurring */}
        <motion.div
          className="dash-card"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: 'easeOut', delay: 0.29 }}
        >
          <h3 className="dash-card-title">Upcoming Charges</h3>
          {upcoming_recurring.length === 0
            ? <p className="dash-empty"><span className="dash-empty-icon">✓</span>No upcoming charges</p>
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
                          {r.days_until === 0 ? '📅 today' : `📅 in ${r.days_until} day${r.days_until === 1 ? '' : 's'}`}
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
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28, ease: 'easeOut', delay: 0.35 }}
      >
        <div className="dash-card-header">
          <h3 className="dash-card-title">Recent Transactions</h3>
          <button className="nav-link" style={{ fontSize: '0.85rem' }} onClick={onViewHistory}>View all →</button>
        </div>
        {recent_transactions.length === 0
          ? <p className="dash-empty"><span className="dash-empty-icon">↑</span>Upload a statement to see transactions</p>
          : (
            <table className="dash-recent-table">
              <tbody>
                {recent_transactions.map((t, i) => (
                  <motion.tr
                    key={i}
                    className="dash-recent-row"
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.2, ease: 'easeOut', delay: 0.38 + i * 0.04 }}
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
      </motion.div>
    </motion.div>
  )
}
