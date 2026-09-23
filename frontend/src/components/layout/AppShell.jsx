import { useEffect, useState } from 'react';
import { useAuth } from '../../lib/auth/AuthProvider.jsx';
import Sidebar from './Sidebar.jsx';
import Topbar from './Topbar.jsx';

export default function AppShell({ children, currentPath, onNavigate }) {
  const { user } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  return <div className="app-shell">
    <Topbar user={user} onMenuClick={() => setSidebarOpen(!sidebarOpen)} />
    <div className="app-body">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} currentPath={currentPath} onNavigate={onNavigate} isMobile={isMobile} />
      <main className="main-content">
        {children}
      </main>
    </div>
  </div>;
}
