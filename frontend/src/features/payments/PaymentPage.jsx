import { useState, useEffect } from 'react';
import { useAuth } from '../../lib/auth/AuthProvider.jsx';
import { useApi } from '../../lib/api/client.jsx';
import { fmt } from '../../lib/formatting/index.jsx';
import { MoneyInput } from '../../components/forms/MoneyInput.jsx';
import ConfirmDialog from '../../components/feedback/ConfirmDialog.jsx';
import { StatusBadge } from '../../components/common/StatusBadge.jsx';

export default function PaymentPage({ api: propApi }) {
  const api = propApi || useApi();
  const { hasPerm, user } = useAuth();
  const [invs, setInvs] = useState([]);
  const [sel, setSel] = useState([]);
  const [amount, setAmount] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [studentSearch, setStudentSearch] = useState('');
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const j = await api.get('/invoices');
      setInvs(j?.items || []);
    } catch (e) { /* handled by table below if needed */ }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [api]);

  const filtered = studentSearch ? invs.filter(i => i.student_name?.toLowerCase().includes(studentSearch.toLowerCase())) : invs;

  const toggle = (id) => setSel(p => p.includes(id) ? p.filter(x=>x!==id) : [...p,id]);
  const totalSel = sel.reduce((a,id) => a + (invs.find(x=>x.id===id)?.outstanding_amount || 0), 0);

  const pay = async () => {
    if (!sel.length || !amount) return;
    setSubmitting(true);
    try {
      await api.post('/payments', { invoice_ids: sel, amount: parseInt(amount), method: 'Tunai' });
      setSel([]); setAmount('');
      load();
    } catch (e) { setError?.(e.message); }
    finally { setSubmitting(false); setConfirmOpen(false); }
  };

  const isParent = user?.role === 'orang_tua';
  const isCashier = hasPerm('payments.create');

  return (
    <div className="page">
      <div className="page-head"><h1>Pembayaran</h1></div>
      {isCashier && (
        <div className="pay-form">
          <label>Pencarian Siswa<input type="text" value={studentSearch} onChange={e=>setStudentSearch(e.target.value)} placeholder="Cari siswa..." /></label>
          <MoneyInput value={amount} onChange={setAmount} label="Nominal" />
          <button onClick={()=>setConfirmOpen(true)} disabled={!sel.length||!amount||submitting}>{submitting?'Memproses...':'Bayar'}</button>
        </div>
      )}
      {isParent && (
        <div className="form-card" style={{marginBottom:16}}>
          <p style={{color:'var(--muted)',fontSize:14}}>Pilih tagihan yang ingin dibayar.</p>
        </div>
      )}
      <div className="table-wrap">
        <table>
          <thead><tr><th>{isCashier?'Pilih':'Invoice'}</th><th>Siswa</th><th>Periode</th><th>Sisa</th><th>Status</th></tr></thead>
          <tbody>
            {filtered.map(i => (
              <tr key={i.id}>
                <td>{isCashier ? <input type="checkbox" checked={sel.includes(i.id)} onChange={()=>toggle(i.id)} /> : <code>{i.id}</code>}</td>
                <td>{i.student_name}</td>
                <td>{i.period_month ? `${i.period_month}/${i.period_year}` : '-'}</td>
                <td>{fmt(i.outstanding_amount||0)}</td>
                <td><StatusBadge status={i.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ConfirmDialog open={confirmOpen} title="Konfirmasi Pembayaran" message={`Bayar total ${fmt(totalSel)}?`} onConfirm={pay} onCancel={()=>setConfirmOpen(false)} />
    </div>
  );
}
