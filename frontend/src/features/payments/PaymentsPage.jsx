import { useEffect, useState } from 'react';
import { useApi } from '../../lib/api/client.jsx';
import { useAuth } from '../../lib/auth/AuthProvider.jsx';
import { DataTable } from '../../components/table/DataTable.jsx';
import { PageHeader, SearchInput } from '../../components/common/StatCard.jsx';
import { MoneyInput } from '../../components/forms/MoneyInput.jsx';
import { ConfirmDialog, ReauthDialog } from '../../components/common/Dialogs.jsx';
import { useToast } from '../../components/common/Toast.jsx';
import { fmt } from '../../lib/formatting/index.jsx';

export default function PaymentsPage() {
  const api = useApi();
  const { user } = useAuth();
  const toast = useToast();
  const [invs, setInvs] = useState([]);
  const [sel, setSel] = useState([]);
  const [amount, setAmount] = useState('');
  const [method, setMethod] = useState('Tunai');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [reauthOpen, setReauthOpen] = useState(false);
  const [search, setSearch] = useState('');

  const load = async () => {
    setLoading(true); setError(null);
    try { const j = await api.get('/invoices'); setInvs(j.items || []); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [api]);

  const pay = async () => {
    if (!sel.length || !amount || submitting) return;
    setSubmitting(true);
    try {
      const studentId = invs.find(i => i.id === sel[0])?.student_id;
      await api.post('/payments', { unit_id: user?.unit_id, student_id: studentId, invoice_ids: sel, amount: parseInt(amount), method }, { idempotent: true });
      toast.showToast('Pembayaran berhasil!', 'success');
      setSel([]); setAmount(''); load();
    } catch (e) { toast.showToast(e.message, 'error'); }
    finally { setSubmitting(false); }
  };

  const toggle = (id) => setSel(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id]);
  const unpaid = invs.filter(i => i.status !== 'paid' && i.status !== 'cancelled');
  const filtered = search ? unpaid.filter(i => (i.student_name||'').toLowerCase().includes(search.toLowerCase())) : unpaid;
  const totalSel = sel.reduce((a,id) => a + (unpaid.find(x => x.id === id)?.outstanding_amount || 0), 0);

  const columns = [
    { header: '✓', field: 'select', render: (_, item) => <input type="checkbox" checked={sel.includes(item.id)} onChange={() => toggle(item.id)} /> },
    { header: 'Siswa', field: 'student_name' },
    { header: 'No Invoice', field: 'invoice_number' },
    { header: 'Sisa', field: 'outstanding_amount', render: fmt },
    { header: 'Status', field: 'status', status: true },
  ];

  return <div className="page">
    <PageHeader title="Pembayaran" actions={<SearchInput value={search} onChange={setSearch} />} />
    <div className="pay-form">
      <label>Metode<select value={method} onChange={e => setMethod(e.target.value)}>
        <option value="Tunai">Tunai</option><option value="Transfer">Transfer</option><option value="QRIS">QRIS</option><option value="VA">Virtual Account</option><option value="E-Wallet">E-Wallet</option><option value="Wallet">Potong Dompet</option>
      </select></label>
      <MoneyInput value={amount} onChange={setAmount} label="Nominal" disabled={submitting} />
      {totalSel > 0 && <p className="info">Total tagihan dipilih: {fmt(totalSel)}</p>}
      <button onClick={() => setConfirmOpen(true)} disabled={!sel.length || !amount || submitting}>{submitting ? 'Memproses...' : 'Bayar'}</button>
    </div>
    <DataTable data={filtered} columns={columns} loading={loading} error={error} onRetry={load} emptyText="Tidak ada tagihan untuk dibayar" />
    <ConfirmDialog open={confirmOpen} title="Konfirmasi Pembayaran" message={`Bayar ${sel.length} tagihan, total ${fmt(totalSel)}, metode ${method}?`} onConfirm={() => { setConfirmOpen(false); setReauthOpen(true); }} onCancel={() => setConfirmOpen(false)} />
    <ReauthDialog open={reauthOpen} title="Konfirmasi Password" message="Masukkan password untuk memproses pembayaran" onSubmit={(pw) => { setReauthOpen(false); pay(); }} onCancel={() => setReauthOpen(false)} />
  </div>;
}
