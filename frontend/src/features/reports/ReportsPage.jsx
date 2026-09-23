import React from 'react';
import { useAuth } from '../../lib/auth/AuthProvider.jsx';

export default function ReportsPage() {
  const { user } = useAuth();
  const hasPerm = (perm) => {
    const perms = user?.permissions || [];
    return perms.includes(perm);
  };

  return (
    <div className="page">
      <div className="page-head">
        <h1>Laporan</h1>
        <p>Modul laporan sedang dalam pengembangan.</p>
      </div>
      <div className="panel">
        <h3>Jenis Laporan</h3>
        <div className="stat-grid">
          {hasPerm('reports.view') && (
            <>
              <div className="stat">
                <strong>Keuangan</strong>
                <div className="label">Neraca, arus kas, laba rugi</div>
              </div>
              <div className="stat">
                <strong>Siswa</strong>
                <div className="label">Tagihan, pembayaran, tunggakan</div>
              </div>
              <div className="stat">
                <strong>Inventaris</strong>
                <div className="label">Stok, mutasi, aset</div>
              </div>
            </>
          )}
        </div>
        <div className="form-card" style={{ marginTop: '24px' }}>
          <label>Periode</label>
          <div style={{ display: 'flex', gap: '12px' }}>
            <input type="date" placeholder="Dari" />
            <input type="date" placeholder="Sampai" />
          </div>
          <button type="button" disabled>
            Tampilkan Laporan
          </button>
        </div>
      </div>
    </div>
  );
}