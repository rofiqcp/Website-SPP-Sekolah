import { useAuth } from '../../lib/auth/AuthProvider.jsx';

export default function Topbar({ user, onMenuClick }) {
  const { doLogout } = useAuth();
  return <header className="topbar">
    <button className="menu-toggle" onClick={onMenuClick} aria-label="Menu">☰</button>
    <div className="topbar-brand">
      <img src="/logo%20yaomy.jpg" alt="El Yaomy" />
      <div><b>El Yaomy</b><small>Sistem Keuangan</small></div>
    </div>
    <div className="topbar-user">
      {user && <>
        <span>{user.name}</span>
        <span className="badge">{user.role?.replace(/_/g,' ')}</span>
        <button onClick={doLogout}>Keluar</button>
      </>}
    </div>
  </header>;
}
