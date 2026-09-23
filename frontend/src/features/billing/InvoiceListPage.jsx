import { useState, useEffect } from 'react';
import { useAuth } from '../../lib/auth/AuthProvider.jsx';
import { useApi } from '../../lib/api/client.jsx';
import { fmt } from '../../lib/formatting/index.jsx';
import { StatusBadge } from '../../components/common/StatusBadge.jsx';
import ConfirmDialog from '../../components/feedback/ConfirmDialog.jsx';
import { useToast } from '../../components/common/Toast.jsx';

export default function InvoiceListPage() {
  const api = useApi();
  const { hasPerm, user } = useAuth();
  const { showToast } = useToast();
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [view, setView] = useState('table');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [selId, setSelId] = useState(null);

  const load = async () => {
    setLoading(true); setError(null);
    try {
      const j = await api.get('/invoices');
      setList(j?.items || []);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [api]);

  const pay = async (id) => { setSelId(id); setConfirmOpen(true); };
  const doPay = async () => {
    if (!selId) return;
    try {
      await api.post('/payments', { invoice_ids: [selId], amount: 0, method: 'Tunai' });
      showToast?.('Pembayaran diproses', 'success');
      load();
    } catch (e) { setError(e.message); }
    setConfirmOpen(false);
  };

  const canPay = hasPerm('payments.create');

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Tagihan</h1><p>Daftar invoice</p></div>
        <div style={{display:'flex',gap:8}}>
          <button className="ghost" onClick={() => setView(v => v==='table'?'cards':'table')}>Toggle {view==='table'?'Kartu':'Tabel'}</button>
          {hasPerm('billing.manage') && <button onClick={async()=>{await api.post('/billing/generate',{unit_id:user?.unit_id});load();}}>Generate</button>}
        </div>
      </div>

      {loading ? <div className="loading-container"><div className="loading-spinner"></div></div> : error ? <div className="error-state"><strong>Error</strong>{error}</div> : (
        view === 'table' ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Siswa</th><th>Periode</th><th>Total</th><th>Terbayar</th><th>Status</th>{canPay && <th>Aksi</th>}</tr></thead>
              <tbody>
                {list.map(i => (
                  <tr key={i.id}>
                    <td>{i.student_name}</td>
                    <td>{i.period_month ? `${i.period_month}/${i.period_year}` : '-'}</td>
                    <td>{fmt(i.total_amount)}</td>
                    <td>{fmt(i.paid_amount)}</td>
                    <td><StatusBadge status={i.status} /></td>
                    {canPay && <td><button className="pay-btn" onClick={()=>pay(i.id)}>Bayar</button></td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="table-mobile">
            {list.map(i => (
              <div key={i.id} className="card-mobile">
                <div className="card-header"><strong>{i.student_name}</strong><StatusBadge status={i.status} /></div>
                <div className="card-body">
                  <div className="card-row"><span className="card-label">Periode</span><span className="card-value">{i.period_month ? `${i.period_month}/${i.period_year}` : '-'}</span></div>
                  <div className="card-row"><span className="card-label">Total</span><span className="card-value">{fmt(i.total_amount)}</span></div>
                  <div className="card-row"><span className="card-label">Terbayar</span><span className="card-value">{fmt(i.paid_amount)}</span></div>
                </div>
                {canPay && <div className="card-actions"><button className="pay-btn" onClick={()=>pay(i.id)}>Bayar</button></div>}
              </div>
            ))}
          </div>
        )
      )}

      <ConfirmDialog open={confirmOpen} title="Konfirmasi Pembayaran" message="Proses pembayaran tagihan ini?" onConfirm={doPay} onCancel={()=>setConfirmOpen(false)} />
    </div>
  );
}
