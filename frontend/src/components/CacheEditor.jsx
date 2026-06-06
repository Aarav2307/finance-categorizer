import { useState } from 'react'

const CATEGORIES = [
  'Credit Card Bill', 'Dining', 'Education', 'Entertainment', 'Groceries', 'Health', 'Housing',
  'Income', 'Other', 'Shopping', 'Subscriptions', 'Transfers', 'Transport', 'Utilities', 'Zelle',
]

export default function CacheEditor({ entries, onDelete, onAdd }) {
  const [open, setOpen] = useState(false)
  const [desc, setDesc] = useState('')
  const [category, setCategory] = useState('Groceries')

  function handleSubmit(e) {
    e.preventDefault()               // stop the browser from reloading the page
    if (!desc.trim()) return
    onAdd(desc.trim(), category)
    setDesc('')                      // clear the input after saving
    setCategory('Groceries')
  }

  return (
    <div className="cache-editor">
      <button className="toggle-btn" onClick={() => setOpen(o => !o)}>
        {open ? '▲' : '▼'} Saved merchant rules ({entries.length})
      </button>

      {open && (
        <>
          {/* Add rule form */}
          <form className="add-rule-form" onSubmit={handleSubmit}>
            <input
              type="text"
              placeholder="Merchant name as it appears in your bank statement"
              value={desc}
              onChange={e => setDesc(e.target.value)}
            />
            <select value={category} onChange={e => setCategory(e.target.value)}>
              {CATEGORIES.map(c => <option key={c}>{c}</option>)}
            </select>
            <button type="submit" className="export-btn">Add rule</button>
          </form>

          {/* Existing rules table */}
          {entries.length === 0 ? (
            <p className="empty">No saved rules yet.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Merchant key</th>
                  <th>Category</th>
                  <th>Source</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {entries.map(e => (
                  <tr key={e.key}>
                    <td className="mono">{e.key}</td>
                    <td>{e.category}</td>
                    <td>
                      {e.source === 'user_correction' && (
                        <span className="source-badge">✎ corrected</span>
                      )}
                    </td>
                    <td>
                      <button className="delete-btn" onClick={() => onDelete(e.key)}>
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  )
}
