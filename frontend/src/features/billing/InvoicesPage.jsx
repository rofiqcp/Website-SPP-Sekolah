import { useEffect, useState } from 'react';
import { useApi } from '../../lib/api/client.jsx';
import { DataTable } from '../../components/table/DataTable.jsx';
import { PageHeader, SearchInput, FilterPanel } from '../../components/common/StatCard.jsx';
import { ConfirmDialog } from '../../components/common/Dialogs.jsx';
import { useToast } from '../../components/common/Toast.jsx';
import { fmt } from '../../lib/formatting/index.jsx';

export default function InvoicesPage() {
  const api = useApi();
  const toast = useToast();
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(null);

  const load = async () => {
    setLoading(true); setError(null);
    try { const j = await api.get('/invoices'); setList(j.items || []); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [api]);

  const generate = async () => {
    try {
      await api.post('/billing/generate', { unit_id: 1 }, { idempotent: true });
      toast.showToast('Invoice berhasil dibuat', 'success');
      load();
    } catch (e) { toast.showToast(e.message, 'error'); }
  };

  let filtered = list;
  if (search) filtered = filtered.filter(i => (i.student_name||'').toLowerCase().includes(search.toLowerCase()) || (i.invoice_number||'').includes(search));
  if (statusFilter) filtered = filtered.filter(i => i.status === statusFilter);

  const columns = [
    { header: 'No Invoice', field: 'invoice_number' },
    { header: 'Siswa', field: 'student_name' },
    { header: 'Periode', field: 'period_month', render: (v, row) => v ? `${v}/${row.period_year}` : '-' },
    { header: 'Tagihan', field: 'total_amount', render: fmt },
    { header: 'Terbayar', field: 'paid_amount', render: fmt },
    { header: 'Sisa', field: 'outstanding_amount', render: fmt },
    { header: 'Status', field: 'status', status: true },
  ];

  const actions = [
    { label: 'Bayar', class: 'pay-btn', handler: (i) => toast.showToast('Navigasi ke pembayaran...', 'info') },
    { label: 'Detail', class: 'view-btn', handler: (i) => toast.showToast('Detail invoice: ' + i.invoice_number, 'info') },
  ];

  return <div className="page">
    <PageHeader title="Tagihan Siswa" actions={<>
      <SearchInput value={search} onChange={setSearch} placeholder="Cari siswa/no invoice..." />
      <button onClick={() => setConfirmOpen('generate')}>Generate Invoice</button>
    </>} />
    <FilterPanel onReset={() => setStatusFilter('')}>
      <label>Status<select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
        <option value="">Semua</option>
        <option value="published">Published</option>
        <option value="partially_paid">Partial</option>
        <option value="paid">Paid</option>
        <option value="overdue">Overdue</option>
      </select></label>
    </FilterPanel>
    <DataTable data={filtered} columns={columns} actions={actions} loading={loading} error={error} onRetry={load} emptyText="Belum ada tagihan" />
    <ConfirmDialog open={confirmOpen === 'generate'} title="Generate Invoice" message="Buat invoice baru untuk unit ini?" confirmLabel="Generate" onConfirm={() => { generate(); setConfirmOpen(null); }} onCancel={() => setConfirmOpen(null)} />
  </div>;
}
