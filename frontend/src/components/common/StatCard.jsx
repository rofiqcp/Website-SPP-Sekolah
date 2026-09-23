export function StatCard({ label, value, tone = '', icon }) {
  return <div className={`stat ${tone}`}>
    {icon && <span className="stat-icon">{icon}</span>}
    <span>{label}</span>
    <strong>{value}</strong>
  </div>;
}

export function FilterPanel({ children, onApply, onReset }) {
  return <div className="filter-panel">
    {children}
    <div className="filter-actions">
      {onReset && <button className="ghost" onClick={onReset}>Reset</button>}
      {onApply && <button onClick={onApply}>Terapkan</button>}
    </div>
  </div>;
}

export function SearchInput({ value, onChange, placeholder = 'Cari...' }) {
  return <input className="search-input" type="text" value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} />;
}

export function PageHeader({ title, subtitle, actions }) {
  return <div className="page-head">
    <div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>
    {actions && <div className="page-actions">{actions}</div>}
  </div>;
}
