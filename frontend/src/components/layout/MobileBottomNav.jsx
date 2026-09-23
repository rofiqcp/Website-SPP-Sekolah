import { useAuth } from '../../lib/auth/AuthProvider.jsx';
import { can } from '../../lib/permissions/permissions.jsx';

const BOTTOM_NAV_ITEMS = {
  orang_tua: [
    { path: '/dashboard', label: 'Home', icon: '🏠' },
    { path: '/billing', label: 'Tagihan', icon: '📋' },
    { path: '/payments', label: 'Bayar', icon: '💳' },
    { path: '/wallet', label: 'Dompet', icon: '👛' },
    { path: '/reports', label: 'Riwayat', icon: '📊' },
  ],
  siswa: [
    { path: '/dashboard', label: 'Home', icon: '🏠' },
    { path: '/wallet', label: 'Dompet', icon: '👛' },
    { path: '/reports', label: 'Riwayat', icon: '📊' },
  ],
  kasir: [
    { path: '/dashboard', label: 'Home', icon: '🏠' },
    { path: '/payments', label: 'Bayar', icon: '💳' },
    { path: '/wallet', label: 'Topup', icon: '👛' },
    { path: '/reports', label: 'Shift', icon: '📊' },
  ],
  default: [
    { path: '/dashboard', label: 'Home', icon: '🏠' },
    { path: '/billing', label: 'Tagihan', icon: '📋' },
    { path: '/payments', label: 'Bayar', icon: '💳' },
    { path: '/reports', label: 'Laporan', icon: '📊' },
    { path: '/settings', label: 'Menu', icon: '☰' },
  ],
};

export default function MobileBottomNav({ currentPath, onNavigate }) {
  const { user } = useAuth();
  const role = user?.role || 'default';
  const items = BOTTOM_NAV_ITEMS[role] || BOTTOM_NAV_ITEMS.default;

  return <nav className="mobile-bottom-nav">
    {items.map(item => (
      <button key={item.path} className={currentPath === item.path ? 'active' : ''} onClick={() => onNavigate(item.path)}>
        <span className="icon">{item.icon}</span>
        <span className="label">{item.label}</span>
      </button>
    ))}
  </nav>;
}
