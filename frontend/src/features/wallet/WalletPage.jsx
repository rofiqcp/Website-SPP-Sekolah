import { useEffect, useState } from 'react';
import { useApi } from '../../lib/api/client.jsx';
import { DataTable } from '../../components/table/DataTable.jsx';
import { PageHeader, SearchInput } from '../../components/common/StatCard.jsx';
import { MoneyInput } from '../../components/forms/MoneyInput.jsx';
import { ConfirmDialog } from '../../components/common/Dialogs.jsx';
import { useToast } from '../../components/common/Toast.jsx';
import { StatCard } from '../../components/common/StatCard.jsx';
import { fmt } from '../../lib/formatting/index.jsx';

export default function WalletPage() {
  const api = useApi();
  const toast = useToast();
  const [wallets, setWallets] = useState([]);
  const [ledger, setLedger] = useState([]);
  const [topup, setTopup] = useState({ wallet_id: '', amount: '' });
  const [loading, setLoading] = useState(true);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState('wallets'); // wallets | ledger
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const [wj, lj] = await Promise.all([api.get('/wallets'), api.get('/wallets/ledger?limit=50')]);
      setWallets(wj?.items || []);
      setLedger(lj?.items || []);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [api]);

  const doTopup = async () => {
    if (!topup.wallet_id || !topup.amount) return;
    try {
      await api.post('/wallets/topup', { account_id: topup.wallet_id, amount: parseInt(topup.amount), method: 'Tunai' });
      toast.showToast('Top-up berhasil', 'success');
      setTopup({ wallet_id: '', amount: '' });
      load();
    } catch (e) { toast.showToast(e.message, 'error'); }
  };

  const totalBalance = wallets.reduce((a, w) => a + (w.cached_balance || 0), 0);

  return <div className="page">
    <PageHeader title="Dompet & Tabungan" />
    <div className="stat-grid">
      <StatCard label="Total Saldo" value={fmt(totalBalance)} tone="green" />
      <StatCard label="Jumlah Akun" value={wallets.length} tone="blue" />
    </div>
    <div className="tabs">
      <button className={activeTab === 'wallets' ? 'active' : ''} onClick={() => setActiveTab('wallets')}>Daftar Dompet</button>
      <button className={activeTab === 'ledger' ? 'active' : ''} onClick={() => setActiveTab('ledger')}>Mutasi</button>
      <button className={activeTab === 'topup' ? 'active' : ''} onClick={() => setActiveTab('topup')}>Top-Up</button>
    </div>
    {activeTab === 'wallets' && <DataTable data={wallets} columns={[
      { header: 'Pemilik', field: 'name' },
      { header: 'Tipe', field: 'account_type' },
      { header: 'No Dompet', field: 'account_number' },
      { header: 'Saldo', field: 'cached_balance', render: fmt },
      { header: 'Limit/Hari', field: 'daily_limit', render: fmt },
      { header: 'Status', field: 'status', status: true },
    ]} loading={loading} emptyText="Belum ada akun dompet" />}
    {activeTab === 'ledger' && <DataTable data={ledger} columns={[
      { header: 'Tanggal', field: 'created_at' },
      { header: 'Tipe', field: 'transaction_type', status: true },
      { header: 'Arah', field: 'direction', render: (v) => v === 'credit' ? '↑ Masuk' : '↓ Keluar' },
      { header: 'Jumlah', field: 'amount', render: fmt },
      { header: 'Saldo Setelah', field: 'balance_after', render: fmt },
      { header: 'Keterangan', field: 'description' },
    ]} loading={loading} emptyText="Belum ada transaksi" />}
    {activeTab === 'topup' && <div className="pay-form">
      <label>Dompet<select value={topup.wallet_id} onChange={e => setTopup({...topup, wallet_id: e.target.value})}>
        <option value="">Pilih dompet...</option>
        {wallets.filter(w => w.status === 'active').map(w => <option key={w.id} value={w.id}>{w.owner_name} ({fmt(w.cached_balance)})</option>)}
      </select></label>
      <MoneyInput value={topup.amount} onChange={v => setTopup({...topup, amount: v})} label="Nominal Top-Up" />
      <button onClick={() => setConfirmOpen(true)} disabled={!topup.wallet_id || !topup.amount}>Top Up</button>
    </div>}
    <ConfirmDialog open={confirmOpen} title="Konfirmasi Top-Up" message={`Top-up ${fmt(topup.amount)} ke dompet ${wallets.find(w=>w.id==topup.wallet_id)?.owner_name || ''}?`} onConfirm={() => { doTopup(); setConfirmOpen(false); }} onCancel={() => setConfirmOpen(false)} />
  </div>;
}
