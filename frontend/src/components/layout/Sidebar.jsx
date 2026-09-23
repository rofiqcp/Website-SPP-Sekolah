import { useState } from 'react';
import { useAuth } from '../../lib/auth/AuthProvider.jsx';
import { can } from '../../lib/permissions/permissions.jsx';

const MENU = [
  { path: '/dashboard', label: 'Dashboard', icon: '🏠', perm: 'dashboard.view' },
  { path: '/students', label: 'Siswa', icon: '👨‍🎓', perm: 'students.view' },
  { path: '/billing', label: 'Tagihan', icon: '📋', perm: 'billing.manage' },
  { path: '/payments', label: 'Pembayaran', icon: '💳', perm: 'payments.create' },
  { path: '/wallet', label: 'Dompet', icon: '👛', perm: 'wallet.topup' },
  { path: '/canteen', label: 'E-Kantin', icon: '🍱', perm: 'canteen.manage' },
  { path: '/canteen/pos', label: 'POS Kantin', icon: '🛒', perm: 'canteen.checkout' },
  { path: '/inventory', label: 'Inventaris', icon: '📦', perm: 'inventory.manage' },
  { path: '/assets', label: 'Aset', icon: '🏗', perm: 'assets.manage' },
  { path: '/journal', label: 'Jurnal', icon: '📒', perm: 'accounting.journal' },
  { path: '/neraca', label: 'Neraca', icon: '⚖', perm: 'accounting.view' },
  { path: '/budget', label: 'RAB', icon: '💰', perm: 'budget.manage' },
  { path: '/reports', label: 'Laporan', icon: '📈', perm: 'reports.view' },
  { path: '/rfid', label: 'RFID', icon: '📟', perm: 'rfid.manage' },
  { path: '/audit', label: 'Audit', icon: '🔍', perm: 'audit.view' },
  { path: '/settings', label: 'Pengaturan', icon: '⚙', perm: 'users.manage' },
];

export default function Sidebar({ open, onClose, currentPath, onNavigate, isMobile }) {
  const { user } = useAuth();
  const items = MENU.filter(m => can(user, m.perm));
  const [collapsed, setCollapsed] = useState(false);

  const isActive = (path) => currentPath === path || currentPath.startsWith(path + '/');

  return (
    <aside className={`sidebar ${open ? 'open' : ''} ${isMobile ? 'mobile' : 'desktop'} ${collapsed && !isMobile ? 'collapsed' : ''}`}>
      {isMobile && <button className="sidebar-close" onClick={onClose} aria-label="Tutup">✕</button>}
      <div className="sidebar-head">
        <strong className="sidebar-title">{collapsed && !isMobile ? '' : 'Menu'}</strong>
        {!isMobile && (
          <button className="ghost sidebar-collapse-btn" onClick={() => setCollapsed(c => !c)} aria-label={collapsed ? 'Lebarkan' : 'Persempit'}>
            {collapsed ? '▶' : '◀'}
          </button>
        )}
      </div>
      <nav className="sidebar-nav">
        {items.map(item => (
          <button
            key={item.path}
            className={`sidebar-item ${isActive(item.path) ? 'active' : ''}`}
            onClick={() => { onNavigate(item.path); onClose?.(); }}
            title={item.label}
          >
            <span className="sidebar-icon" aria-hidden="true">{item.icon}</span>
            {(!isMobile && !collapsed) && <span className="sidebar-label">{item.label}</span>}
          </button>
        ))}
      </nav>
    </aside>
  );
}
