import { LoadingState, ErrorState, EmptyState } from '../common/State.jsx';
import { StatusBadge } from '../common/StatusBadge.jsx';
import { fmt } from '../../lib/formatting/index.jsx';

export function DataTable({ data, columns, actions, loading, error, onRetry, emptyText = 'Tidak ada data', isMobile: forceMobile }) {
  const isMobile = forceMobile !== undefined ? forceMobile : (typeof window !== 'undefined' && window.innerWidth < 768);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState text={error} onRetry={onRetry} />;
  if (!data || data.length === 0) return <EmptyState text={emptyText} />;

  if (isMobile) {
    return <div className="table-mobile">
      {data.map((item, i) => (
        <div key={item.id ?? i} className="card-mobile">
          <div className="card-header">
          <strong>{item[columns[0].field] || '-'}</strong>
          {(() => { const sc = columns.find(c => c.status); return sc && <StatusBadge status={item[sc.field]} />; })()}
          </div>
          <div className="card-body">
            {columns.slice(1).map((c, j) => item[c.field] !== undefined && (
              <div key={j} className="card-row">
                <span className="card-label">{c.header}</span>
                <span className="card-value">{c.render ? c.render(item[c.field], item) : typeof item[c.field] === 'number' ? fmt(item[c.field]) : item[c.field]}</span>
              </div>
            ))}
          </div>
          {actions && actions.length > 0 && (
            <div className="card-actions">
              {actions.map((a, j) => <button key={j} className={a.class || 'ghost'} onClick={() => a.handler(item)}>{a.label}</button>)}
            </div>
          )}
        </div>
      ))}
    </div>;
  }

  return <div className="table-wrap">
    <table>
      <thead>
        <tr>{columns.map(c => <th key={c.field}>{c.header}</th>)}{actions && <th>Aksi</th>}</tr>
      </thead>
      <tbody>
        {data.map((item, i) => (
          <tr key={item.id || i}>
            {columns.map(c => (
              <td key={c.field}>
                {c.status ? <StatusBadge status={item[c.field]} />
                : c.render ? c.render(item[c.field], item)
                : typeof item[c.field] === 'number' ? fmt(item[c.field])
                : item[c.field] || '-'}
              </td>
            ))}
            {actions && <td className="action-cell">{actions.map((a, j) => <button key={j} className={a.class || 'ghost'} onClick={() => a.handler(item)}>{a.label}</button>)}</td>}
          </tr>
        ))}
      </tbody>
    </table>
  </div>;
}
