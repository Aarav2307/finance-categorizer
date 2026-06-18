export default function CategorizingSkeleton() {
  return (
    <div className="categorizing-skeleton">
      <p className="categorizing-status">Categorizing your transactions on this device…</p>

      <div className="skel-header">
        <div className="dash-skeleton skel-back" />
        <div className="skel-header-right">
          <div className="dash-skeleton skel-pill" />
          <div className="dash-skeleton skel-pill" />
          <div className="dash-skeleton skel-avatar" />
        </div>
      </div>

      <div className="dash-skeleton skel-title" />

      <div className="skel-stat-row">
        <div className="skel-stat-card"><div className="dash-skeleton skel-stat-inner" /></div>
        <div className="skel-stat-card"><div className="dash-skeleton skel-stat-inner" /></div>
        <div className="skel-stat-card"><div className="dash-skeleton skel-stat-inner" /></div>
      </div>

      <div className="skel-table-wrap">
        <div className="skel-table-header">
          <div className="dash-skeleton skel-table-title" />
          <div className="dash-skeleton skel-search" />
        </div>
        {[68, 52, 80, 60, 75, 55, 70].map((w, i) => (
          <div key={i} className="skel-row">
            <div className="dash-skeleton skel-cell-date" />
            <div className="dash-skeleton skel-cell-desc" style={{ width: `${w}%` }} />
            <div className="dash-skeleton skel-cell-cat" />
            <div className="dash-skeleton skel-cell-amt" />
          </div>
        ))}
      </div>
    </div>
  )
}
