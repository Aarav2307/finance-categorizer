import { RefreshCw, Receipt, BarChart3, Repeat, CreditCard } from 'lucide-react'

const TYPE_ICON = {
  subscription:  RefreshCw,
  fixed_bill:    Receipt,
  variable_bill: BarChart3,
  frequent:      Repeat,
}

const TYPE_LABEL = {
  subscription:  'Subscription',
  fixed_bill:    'Fixed bill',
  variable_bill: 'Variable bill',
  frequent:      'Frequent',
}

const FREQ_LABEL = {
  weekly:   'Weekly',
  monthly:  'Monthly',
  annual:   'Annual',
  frequent: 'Irregular',
}

function formatDate(iso) {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return new Date(+y, +m - 1, +d).toLocaleDateString('default', { month: 'short', day: 'numeric' })
}

function RecurringRow({ p }) {
  const Icon = TYPE_ICON[p.type] || CreditCard
  return (
    <div className="recurring-row">
      <span className="recurring-icon" aria-hidden="true"><Icon size={15} /></span>

      <div className="recurring-info">
        <span className="recurring-name">{p.display_name}</span>
        <span className="recurring-meta">
          <span className={`recurring-type-badge ${p.type}`}>{TYPE_LABEL[p.type] || p.type}</span>
          <span className="recurring-freq">{FREQ_LABEL[p.frequency] || p.frequency}</span>
          <span className="recurring-occurrences">{p.occurrences}×</span>
        </span>
      </div>

      <div className="recurring-right">
        <span className={`recurring-amount ${p.typical_amount < 0 ? 'negative' : 'positive'}`}>
          {p.typical_amount.toFixed(2)}
        </span>
        {p.next_expected && (
          <span className="recurring-next">next ~{formatDate(p.next_expected)}</span>
        )}
      </div>
    </div>
  )
}

export default function RecurringCard({ patterns }) {
  if (!patterns || patterns.length === 0) return null

  const regular  = patterns.filter(p => p.frequency !== 'frequent')
  const frequent = patterns.filter(p => p.frequency === 'frequent')

  // Fixed monthly spend: subscriptions + fixed bills, monthly frequency only, no frequent tier
  const fixedMonthly = regular
    .filter(p => p.frequency === 'monthly' && p.type !== 'variable_bill' && p.typical_amount < 0)
    .reduce((sum, p) => sum + Math.abs(p.typical_amount), 0)

  return (
    <div className="recurring-card">
      <div className="recurring-header">
        <h2>Recurring Charges</h2>
        {fixedMonthly > 0 && (
          <span className="recurring-fixed-total">
            Fixed monthly: <strong className="negative">−${fixedMonthly.toFixed(2)}</strong>
          </span>
        )}
      </div>

      {regular.length > 0 && (
        <div className="recurring-list">
          {regular.map(p => <RecurringRow key={p.display_name} p={p} />)}
        </div>
      )}

      {frequent.length > 0 && (
        <>
          <div className="recurring-section-label">Frequent purchases</div>
          <div className="recurring-list">
            {frequent.map(p => <RecurringRow key={p.display_name} p={p} />)}
          </div>
        </>
      )}
    </div>
  )
}
