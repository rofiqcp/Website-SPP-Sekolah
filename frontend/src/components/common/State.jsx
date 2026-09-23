export function LoadingState({ text = 'Memuat...' }) {
  return <div className="state-box loading"><span className="spinner" />{text}</div>;
}

export function ErrorState({ text = 'Terjadi kesalahan saat memuat data.', onRetry }) {
  return <div className="state-box error"><span>⚠</span>{text}{onRetry && <button className="retry-btn" onClick={onRetry}>Coba Lagi</button>}</div>;
}

export function EmptyState({ text = 'Tidak ada data', action }) {
  return <div className="state-box empty"><span>📭</span>{text}{action && <div className="empty-action">{action}</div>}</div>;
}

export function Skeleton({ count = 3 }) {
  return <div className="skeleton-list">{Array.from({length: count}).map((_,i) => <div key={i} className="skeleton-item" />)}</div>;
}
