import { useState, useEffect } from 'react';
import { useAuth } from '../../lib/auth/AuthProvider.jsx';
import { useToast } from '../../components/common/Toast.jsx';
import { ConfirmDialog } from '../../components/common/Dialogs.jsx';
import { fmt } from '../../lib/formatting/index.jsx';
import { StatCard } from '../../components/common/StatCard.jsx';
import { StatusBadge } from '../../components/common/StatusBadge.jsx';

export default function DashboardPage({ api }) {
  const { user, hasPerm } = useAuth();
  const { showToast } = useToast();
  const [stats, setStats] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const j = await api.get('/dashboard');
        setStats(j?.stats || []);
      } catch (e) {
        showToast('Gagal memuat dashboard', 'error');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [api, showToast]);

  const actions = [];
  if (hasPerm('billing.manage')) {
    actions.push({ label: 'Generate Invoice', onClick: async () => {
      try {
        await api.post('/billing/generate', { unit_id: user?.unit_id });
        showToast('Invoice dibuat', 'success');
      } catch (e) { showToast(e.message, 'error'); }
    }});
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <p>Ringkasan {user?.role?.replace(/_/g, ' ')}</p>
        </div>
        <div className="page-actions">{actions.map((a, i) => <button key={i} onClick={a.onClick}>{a.label}</button>)}</div>
      </div>
      {loading ? <div className="loading-container"><div className="loading-spinner"></div><p>Memuat...</p></div> : (
        <div className="stat-grid">
          {stats.map((s, i) => <StatCard key={i} label={s.label} value={s.value} tone={s.tone} />)}
        </div>
      )}
    </div>
  );
}
