import { useAuth } from '../../lib/auth/AuthProvider.jsx';
import { can } from '../../lib/permissions/permissions.jsx';

const NAV_BY_ROLE = {
  orang_tua: [
    { path: '/dashboard', label: 'Home', icon: '🏠' },
    { path: '/billing', label: 'Tagihan', icon: '📋' },
    { path: '/payments', label: 'Bayar', icon: '💳' },
    { path: '/wallet', label: 'Dompet', icon: '👛' },
    { path: '/reports', label: 'Riwayat', icon: '📊' },
  ],
  kasir: [
    { path: '/dashboard', label: 'Home', icon: '🏠' },
    { path: '/payments', label: 'Bayar', icon: '💳' },
    { path: '/canteen/pos', label: 'POS', icon: '🛒' },
    { path: '/wallet', label: 'Topup', icon: '👛' },
    { path: '/reports', label: 'Shift', icon: '📊' },
  ],
  siswa: [
    { path: '/dashboard', label: 'Home', icon: '🏠' },
    { path: '/wallet', label: 'Dompet', icon: '👛' },
    { path: '/reports', label: 'Riwayat', icon: '📊' },
  ],
  default: [
    { path: '/dashboard', label: 'Home', icon: '🏠' },
    { path: '/billing', label: 'Tagihan', icon: '📋' },
    { path: '/payments', label: 'Bayar', icon: '💳' },
    { path: '/wallet', label: 'Dompet', icon: '👛' },
    { path: '/reports', label: 'Laporan', icon: '📊' },
  ],
};

export default function MobileShell({ currentPath, onNavigate, children }) {
  const { user } = useAuth();
  const role = user?.role || 'default';
  const navItems = (NAV_BY_ROLE[role] || NAV_BY_ROLE.default).slice(0, 5);

  const showBack = currentPath !== '/dashboard';
  const goBack = () => {
    if (typeof history !== 'undefined' && history.length > 1) history.back();
    else onNavigate('/dashboard');
  };

  const isActive = (path) => currentPath === path || currentPath.startsWith(path + '/');

  return (
    <div className="mobile-shell">
      <header className="mobile-header">
        {showBack && (
          <button className="mobile-back-btn" onClick={goBack} aria-label="Kembali">‹</button>
        )}
        <div className="mobile-header-info">
          <strong>{user?.name || 'El Yaomy'}</strong>
          <small className="mobile-role-badge">{role.replace(/_/g, ' ')}</small>
        </div>
      </header>
      <main className="mobile-content">
        {children}
      </main>
      <nav className="mobile-bottom-nav" style={{ paddingBottom: 'calc(8px + env(safe-area-inset-bottom, 0px))' }}>
        {navItems.map(item => (
          <button
            key={item.path}
            className={isActive(item.path) ? 'active' : ''}
            onClick={() => onNavigate(item.path)}
            aria-label={item.label}
          >
            <span className="icon" aria-hidden="true">{item.icon}</span>
            <span className="label">{item.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
