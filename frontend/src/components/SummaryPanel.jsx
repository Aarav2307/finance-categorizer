import { useState } from 'react'
import {
  PieChart, Pie, Tooltip, ResponsiveContainer, Cell, Legend,
} from 'recharts'
import { CATEGORY_COLORS } from '../constants'
import { fmtAmt } from '../format'

// Convert a full-brightness hex color to a muted pill style
function mutedPillStyle(hex) {
  if (!hex || hex.length < 7) return {}
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return {
    background: `rgba(${r},${g},${b},0.15)`,
    color: hex,
    border: `1px solid rgba(${r},${g},${b},0.3)`,
  }
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const { category, amount } = payload[0].payload
  const total = payload[0].payload._total
  const pct = total ? ((amount / total) * 100).toFixed(1) : null
  return (
    <div className="chart-tooltip">
      <strong>{category}</strong>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1.5rem' }}>
        <span style={{ color: 'var(--text-muted)' }}>Amount</span>
        <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
          ${fmtAmt(amount)}{pct ? <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}> · {pct}%</span> : ''}
        </span>
      </div>
    </div>
  )
}

export default function SummaryPanel({ summary }) {
  const allCategories = summary.map(s => s.category)
  const [hidden, setHidden] = useState(() => new Set())

  function toggle(cat) {
    setHidden(prev => {
      const next = new Set(prev)
      next.has(cat) ? next.delete(cat) : next.add(cat)
      return next
    })
  }

  const visible = summary.filter(s => !hidden.has(s.category))
  const visibleNonTransfers = visible.filter(s => s.category !== 'Transfers')
  const hasTransfers = summary.some(s => s.category === 'Transfers')

  const spending = visibleNonTransfers.filter(s => s.total < 0).reduce((a, s) => a + s.total, 0)
  const income   = visibleNonTransfers.filter(s => s.total > 0).reduce((a, s) => a + s.total, 0)

  const rawChart = visibleNonTransfers
    .map(s => ({ category: s.category, amount: Math.abs(s.total) }))
    .sort((a, b) => b.amount - a.amount)
  const chartTotal = rawChart.reduce((s, d) => s + d.amount, 0)
  const chartData = rawChart.map(d => ({ ...d, _total: chartTotal }))

  return (
    <div className="summary">
      <div className="summary-header">
        <h2>Spending by Category</h2>
        <div className="category-filters">
          {allCategories.map(cat => (
            <button
              key={cat}
              className={`filter-pill ${hidden.has(cat) ? 'hidden' : ''}`}
              style={hidden.has(cat) ? {} : mutedPillStyle(CATEGORY_COLORS[cat] ?? '#aeaeb2')}
              onClick={() => toggle(cat)}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {chartData.length > 0 ? (
        <ResponsiveContainer width="100%" height={320}>
          <PieChart>
            <Pie
              data={chartData}
              dataKey="amount"
              nameKey="category"
              cx="50%"
              cy="46%"
              outerRadius={118}
              innerRadius={62}
              paddingAngle={2}
              stroke="transparent"
            >
              {chartData.map(entry => (
                <Cell key={entry.category} fill={CATEGORY_COLORS[entry.category] ?? '#aeaeb2'} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ paddingTop: 10 }}
              formatter={v => (
                <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>{v}</span>
              )}
            />
            {/* Center total */}
            <text x="50%" y="40%" textAnchor="middle" dominantBaseline="middle">
              <tspan
                x="50%"
                fontSize="20"
                fontWeight="800"
                fill="var(--text-primary)"
                letterSpacing="-0.5"
              >
                ${fmtAmt(chartTotal, 0)}
              </tspan>
              <tspan
                x="50%"
                dy="18"
                fontSize="9"
                fill="var(--text-muted)"
                letterSpacing="1"
              >
                TOTAL
              </tspan>
            </text>
          </PieChart>
        </ResponsiveContainer>
      ) : (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', margin: '1.5rem 0' }}>
          No categories visible.
        </p>
      )}

      <table>
        <thead>
          <tr><th>Category</th><th style={{ textAlign: 'right' }}>Total</th></tr>
        </thead>
        <tbody>
          {visible.map(s => (
            <tr key={s.category}>
              <td>{s.category}</td>
              <td className={s.total < 0 ? 'negative' : 'positive'} style={{ textAlign: 'right' }}>
                {s.total < 0 ? '−' : '+'}{fmtAmt(Math.abs(s.total))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="totals">
        <div>
          <span>Total spending</span>
          <span className="negative">−{fmtAmt(Math.abs(spending))}</span>
        </div>
        <div>
          <span>Income</span>
          <span className="positive">+{fmtAmt(income)}</span>
        </div>
        <div className="net">
          <span>Net</span>
          <span className={(spending + income) >= 0 ? 'positive' : 'negative'}>
            {(spending + income) >= 0 ? '+' : '−'}{fmtAmt(Math.abs(spending + income))}
          </span>
        </div>
      </div>
      {hasTransfers && (
        <p className="transfers-excluded-note">Credit card payments excluded to avoid double-counting.</p>
      )}
    </div>
  )
}
