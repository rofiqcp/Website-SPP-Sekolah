import { useEffect, useState } from 'react';
import { useApi } from '../../lib/api/client.jsx';
import { useAuth } from '../../lib/auth/AuthProvider.jsx';
import { DataTable } from '../../components/table/DataTable.jsx';
import { PageHeader, SearchInput } from '../../components/common/StatCard.jsx';
import { ConfirmDialog } from '../../components/common/Dialogs.jsx';
import { useToast } from '../../components/common/Toast.jsx';

export default function StudentsPage() {
  const api = useApi();
  const { user } = useAuth();
  const toast = useToast();
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ full_name:'', nis:'', guardian_name:'', guardian_phone:'', class_id:'', unit_id: user?.unit_id || '' });
  const [confirmOpen, setConfirmOpen] = useState(false);

  const load = async () => {
    setLoading(true); setError(null);
    try { const j = await api.get('/students'); setList(j.items || []); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [api]);

  const save = async () => {
    try {
      await api.post('/students', form);
      toast.showToast('Siswa berhasil ditambahkan', 'success');
      setShowForm(false); setForm({ full_name:'', nis:'', guardian_name:'', guardian_phone:'', class_id:'', unit_id: user?.unit_id || '' });
      load();
    } catch (e) { toast.showToast(e.message, 'error'); }
  };

  const filtered = search ? list.filter(s => (s.full_name||'').toLowerCase().includes(search.toLowerCase()) || (s.nis||'').includes(search)) : list;

  const columns = [
    { header: 'NIS', field: 'nis' },
    { header: 'Nama', field: 'full_name' },
    { header: 'Kelas', field: 'class_name' },
    { header: 'Wali', field: 'guardian_name' },
    { header: 'Telp Wali', field: 'guardian_phone' },
    { header: 'Status', field: 'enrollment_status', status: true },
  ];

  return <div className="page">
    <PageHeader title="Data Siswa" actions={<>
      <SearchInput value={search} onChange={setSearch} placeholder="Cari nama/NIS..." />
      <button onClick={() => setShowForm(!showForm)}>+ Tambah</button>
    </>} />
    {showForm && <div className="form-card">
      {['full_name','nis','guardian_name','guardian_phone'].map(f =>
        <label key={f}>{f.replace(/_/g,' ').toUpperCase()}<input value={form[f]} onChange={e => setForm({...form,[f]:e.target.value})} /></label>
      )}
      <button onClick={() => setConfirmOpen(true)}>Simpan</button>
    </div>}
    <DataTable data={filtered} columns={columns} loading={loading} error={error} onRetry={load} emptyText="Belum ada data siswa" />
    <ConfirmDialog open={confirmOpen} title="Tambah Siswa" message={`Yakin menambahkan ${form.full_name}?`} onConfirm={() => { save(); setConfirmOpen(false); }} onCancel={() => setConfirmOpen(false)} />
  </div>;
}
