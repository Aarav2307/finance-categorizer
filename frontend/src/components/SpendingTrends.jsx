import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  BarChart, Bar, ComposedChart, Line,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { CATEGORY_COLORS } from '../constants'

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function extractMonth(dateStr) {
  if (!dateStr) return null
  const mm = dateStr.includes('-') ? dateStr.slice(5, 7) : dateStr.slice(0, 2)
  const n = parseInt(mm, 10)
  return n >= 1 && n <= 12 ? mm : null
}

function extractYear(dateStr) {
  if (!dateStr) return null
  if (/^\d{4}-\d{2}-\d{2}/.test(dateStr)) return dateStr.slice(0, 4)
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) return dateStr.slice(6, 10)
  if (/^\d{2}\/\d{2}\/\d{2}$/.test(dateStr)) {
    const yy = parseInt(dateStr.slice(6, 8), 10)
    return String(yy < 50 ? 2000 + yy : 1900 + yy)
  }
  return null
}

function fmt(v) { return `$${Math.abs(v).toFixed(2)}` }

function gradId(cat) {
  return `grad-${cat.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')}`
}

// ── Tooltips ──────────────────────────────────────────────────────────────────

function Chart1Tooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const entries = payload.filter(p => p.value > 0).slice().reverse()
  const monthTotal = entries.reduce((s, p) => s + p.value, 0)
  return (
    <div className="chart-tooltip">
      <strong>{label}</strong>
      {entries.map(p => (
        <div key={p.dataKey} style={{ color: CATEGORY_COLORS[p.dataKey] ?? p.fill, display: 'flex', justifyContent: 'space-between', gap: '1.5rem' }}>
          <span>{p.dataKey}</span>
          <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
            {fmt(p.value)} <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>· {((p.value / monthTotal) * 100).toFixed(0)}%</span>
          </span>
        </div>
      ))}
      <div className="chart-tooltip-total">Total: {fmt(monthTotal)}</div>
    </div>
  )
}

function Chart2Tooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const get = key => payload.find(p => p.dataKey === key)?.value ?? 0
  const net = get('net')
  return (
    <div className="chart-tooltip">
      <strong>{label}</strong>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1.5rem' }}>
        <span style={{ color: 'var(--text-muted)' }}>Spending</span>
        <span style={{ color: 'var(--red)', fontWeight: 600 }}>{fmt(get('spending'))}</span>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1.5rem' }}>
        <span style={{ color: 'var(--text-muted)' }}>Income</span>
        <span style={{ color: 'var(--green)', fontWeight: 600 }}>{fmt(get('income'))}</span>
      </div>
      <div className="chart-tooltip-divider" />
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1.5rem' }}>
        <span style={{ color: 'var(--text-muted)' }}>Net</span>
        <span style={{ color: net >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 700 }}>
          {net >= 0 ? '+' : ''}{net.toFixed(2)}
        </span>
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function SpendingTrends({ transactions, onChartFilter, year }) {
  const [acctFilter, setAcctFilter] = useState('')

  const accounts = [...new Set(transactions.map(t => t.account_name).filter(Boolean))].sort()
  const showAccountFilter = accounts.length > 1

  const base = acctFilter ? transactions.filter(t => t.account_name === acctFilter) : transactions
  const EXCLUDED = new Set(['Transfers', 'Credit Card Bill'])
  const nonTransfer = base.filter(t => {
    if (EXCLUDED.has(t.category)) return false
    if (year) {
      const txYear = extractYear(t.date)
      if (txYear && txYear !== year) return false
    }
    return true
  })

  const hasData = nonTransfer.some(t => extractMonth(t.date))
  if (!hasData) return null

  const ALL_MONTHS = ['01','02','03','04','05','06','07','08','09','10','11','12']
  const spendingCats = [...new Set(nonTransfer.filter(t => t.amount < 0).map(t => t.category))].sort()

  const chart1Data = ALL_MONTHS.map(mm => {
    const row = { month: MONTH_NAMES[parseInt(mm, 10) - 1], mm }
    for (const cat of spendingCats) {
      const total = nonTransfer
        .filter(t => extractMonth(t.date) === mm && t.category === cat && t.amount < 0)
        .reduce((s, t) => s + Math.abs(t.amount), 0)
      if (total > 0.005) row[cat] = Math.round(total * 100) / 100
    }
    return row
  })

  const chart2Data = ALL_MONTHS.map(mm => {
    const monthTxns = nonTransfer.filter(t => extractMonth(t.date) === mm)
    const spending = monthTxns.filter(t => t.amount < 0).reduce((s, t) => s + Math.abs(t.amount), 0)
    const income   = monthTxns.filter(t => t.amount > 0).reduce((s, t) => s + t.amount, 0)
    return {
      month: MONTH_NAMES[parseInt(mm, 10) - 1],
      mm,
      spending: Math.round(spending * 100) / 100,
      income:   Math.round(income   * 100) / 100,
      net:      Math.round((income - spending) * 100) / 100,
    }
  })

  const axisProps = {
    tick: { fill: '#55556a', fontSize: 11 },
    axisLine: false,
    tickLine: false,
  }

  const cardVariants = {
    hidden:  { opacity: 0, y: 16 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' } },
  }

  return (
    <div className="spending-trends">

      {/* Chart 1 — stacked spending by category */}
      <motion.div
        className="trends-card"
        variants={cardVariants}
        initial="hidden"
        animate="visible"
      >
        <div className="trends-header">
          <h2>Monthly Spending by Category</h2>
          {showAccountFilter && (
            <select className="month-select" value={acctFilter} onChange={e => setAcctFilter(e.target.value)}>
              <option value="">All Accounts</option>
              {accounts.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          )}
        </div>

        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={chart1Data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <defs>
              {spendingCats.map(cat => {
                const color = CATEGORY_COLORS[cat] ?? '#aeaeb2'
                return (
                  <linearGradient key={cat} id={gradId(cat)} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stopColor={color} stopOpacity={0.95} />
                    <stop offset="100%" stopColor={color} stopOpacity={0.45} />
                  </linearGradient>
                )
              })}
            </defs>
            <XAxis dataKey="month" {...axisProps} />
            <YAxis tickFormatter={v => `$${v}`} {...axisProps} width={60} />
            <Tooltip
              content={<Chart1Tooltip />}
              cursor={{ fill: 'rgba(255,255,255,0.03)', radius: 4 }}
            />
            <Legend
              wrapperStyle={{ paddingTop: 14 }}
              formatter={v => (
                <span style={{ color: '#8888aa', fontSize: '0.77rem' }}>{v}</span>
              )}
            />
            {spendingCats.map((cat, i) => (
              <Bar
                key={cat}
                dataKey={cat}
                stackId="a"
                fill={`url(#${gradId(cat)})`}
                radius={i === spendingCats.length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]}
                animationBegin={i * 60}
                animationDuration={550}
                animationEasing="ease-out"
                onClick={data => onChartFilter({ month: data.mm, category: cat })}
                style={{ cursor: 'pointer' }}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
        <p className="trends-hint">Click any bar segment to filter the table below</p>
      </motion.div>

      {/* Chart 2 — income vs spending + net line */}
      <motion.div
        className="trends-card"
        variants={cardVariants}
        initial="hidden"
        animate="visible"
        transition={{ delay: 0.1 }}
      >
        <div className="trends-header">
          <h2>Income vs Spending</h2>
        </div>

        <ResponsiveContainer width="100%" height={260}>
          <ComposedChart data={chart2Data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="spendingBarGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="#f87171" stopOpacity={0.85} />
                <stop offset="100%" stopColor="#f87171" stopOpacity={0.25} />
              </linearGradient>
              <linearGradient id="incomeBarGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="#34d399" stopOpacity={0.85} />
                <stop offset="100%" stopColor="#34d399" stopOpacity={0.25} />
              </linearGradient>
            </defs>
            <XAxis dataKey="month" {...axisProps} />
            <YAxis tickFormatter={v => `$${v}`} {...axisProps} width={60} />
            <Tooltip
              content={<Chart2Tooltip />}
              cursor={{ fill: 'rgba(255,255,255,0.03)', radius: 4 }}
            />
            <Legend
              wrapperStyle={{ paddingTop: 14 }}
              formatter={v => (
                <span style={{ color: '#8888aa', fontSize: '0.77rem' }}>
                  {v.charAt(0).toUpperCase() + v.slice(1)}
                </span>
              )}
            />
            <Bar dataKey="spending" fill="url(#spendingBarGrad)" radius={[3,3,0,0]} animationDuration={550} animationEasing="ease-out" />
            <Bar dataKey="income"   fill="url(#incomeBarGrad)"   radius={[3,3,0,0]} animationDuration={550} animationEasing="ease-out" animationBegin={80} />
            {/* Glow layer — wide dim stroke */}
            <Line
              type="monotone"
              dataKey="net"
              stroke="rgba(255,255,255,0.1)"
              strokeWidth={7}
              dot={false}
              activeDot={false}
              legendType="none"
              isAnimationActive={false}
            />
            {/* Sharp net line on top */}
            <Line
              type="monotone"
              dataKey="net"
              stroke="rgba(255,255,255,0.72)"
              strokeWidth={1.5}
              dot={{ fill: 'rgba(255,255,255,0.7)', r: 3, strokeWidth: 0 }}
              activeDot={{ r: 5, fill: '#fff' }}
              animationDuration={700}
              animationEasing="ease-out"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </motion.div>
    </div>
  )
}
