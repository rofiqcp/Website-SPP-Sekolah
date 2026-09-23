import React from 'react';
import { useAuth } from '../../lib/auth/AuthProvider.jsx';

export default function SettingsPage() {
  const { user } = useAuth();
  const hasPerm = (perm) => {
    const perms = user?.permissions || [];
    return perms.includes(perm);
  };

  return (
    <div className="page">
      <div className="page-head">
        <h1>Pengaturan</h1>
        <p>Konfigurasi sistem dan akun.</p>
      </div>
      <div className="panel">
        <h3>Profil Saya</h3>
        <div className="form-card">
          <label>Nama</label>
          <input type="text" defaultValue={user?.name || ''} disabled />
          <label>Email</label>
          <input type="email" defaultValue={user?.email || ''} disabled />
          <label>Role</label>
          <input type="text" defaultValue={user?.role || ''} disabled />
        </div>
      </div>
      {hasPerm('users.manage') && (
        <div className="panel" style={{ marginTop: '24px' }}>
          <h3>Manajemen User (Admin)</h3>
          <p className="label">Halaman ini memerlukan hak akses admin.</p>
        </div>
      )}
      {hasPerm('mfa.manage') && (
        <div className="panel" style={{ marginTop: '24px' }}>
          <h3>Pengaturan Sistem (Super Admin)</h3>
          <p className="label">Konfigurasi fondasi, unit, permission, RFID, payment gateway.</p>
        </div>
      )}
    </div>
  );
}