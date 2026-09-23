import React, { useState, useEffect } from 'react';
import { ToastProvider, useToast } from './components/common/Toast.jsx';
import { ConfirmDialog, ReauthDialog } from './components/common/Dialogs.jsx';
import { ApiProvider, useApi, AuthError } from './lib/api/client.jsx';
import { AuthProvider, useAuth } from './lib/auth/AuthProvider.jsx';
import Sidebar from './components/layout/Sidebar.jsx';
import Topbar from './components/layout/Topbar.jsx';

import MobileShell from './components/layout/MobileShell.jsx';
import LoginPage from './features/auth/LoginPage.jsx';
import LandingPage from './features/landing/LandingPage.jsx';
import ApkDownloadPage from './features/apk/ApkDownloadPage.jsx';
import DashboardPage from './features/dashboard/DashboardPage.jsx';
import StudentsPage from './features/students/StudentsPage.jsx';
import InvoiceListPage from './features/billing/InvoiceListPage.jsx';
import PaymentPage from './features/payments/PaymentPage.jsx';
import WalletsPage from './features/wallet/WalletPage.jsx';
import CanteenPage from './features/canteen/CanteenPage.jsx';
import CanteenPOSPage from './features/canteen/CanteenPOSPage.jsx';
import ReportsPage from './features/reports/ReportsPage.jsx';
import SettingsPage from './features/settings/SettingsPage.jsx';
import ReceiptModal from './components/print/ReceiptModal.jsx';

function AppContent() {
  const api = useApi();
  const { user, doLogin, doLogout, loading } = useAuth();
  const { showToast } = useToast();
  const [currentPath, setCurrentPath] = useState('/');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [receipt, setReceipt] = useState(null);
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [reAuthOpen, setReAuthOpen] = useState(false);
  const [reAuthCb, setReAuthCb] = useState(null);
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  // Periodic session check — every 5 minutes
  useEffect(() => {
    if (!user) return;
    const interval = setInterval(async () => {
      try {
        await api.get('/auth/me');
      } catch {
        setSessionExpired(true);
        clearInterval(interval);
      }
    }, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [user, api]);

  const navigate = (path) => {
    setCurrentPath(path);
    window.scrollTo(0, 0);
  };

  const triggerReAuth = (cb) => {
    setReAuthCb(() => cb);
    setReAuthOpen(true);
  };

  const onReAuthSuccess = async (pw) => {
    try {
      await reAuthCb?.(pw);
      showToast('Otorisasi berhasil', 'success');
    } catch (e) {
      showToast(e.message || 'Otorisasi gagal', 'error');
    }
    setReAuthOpen(false);
  };

  const handlePrint = () => {
    window.print();
  };

  // Loading state saat checkSession
  if (loading) {
    return (
      <div className="app-root">
        <div className="loading-container">
          <div className="loading-spinner" />
          <p>Memuat...</p>
        </div>
      </div>
    );
  }

  // Belum login: landing page atau login page
  if (!user) {
    if (currentPath === '/') {
      return <LandingPage onNavigate={navigate} />;
    }
    return (
      <>
        <header className="topbar">
          <a className="logo" onClick={() => navigate('/')}>
            <img src="/logo%20yaomy.jpg" alt="El Yaomy" />
            <div><b>El Yaomy Klaten</b><small>SPP & Keuangan</small></div>
          </a>
        </header>
        <LoginPage onNavigate={navigate} />
      </>
    );
  }

  // Sudah login: app shell
  return (
    <div className="app-root">
      {isMobile ? (
        <div>
          <MobileShell currentPath={currentPath} onNavigate={navigate}>
            {currentPath === '/apk' && <ApkDownloadPage />}
            {currentPath === '/dashboard' && <DashboardPage api={api} />}
            {currentPath === '/students' && <StudentsPage api={api} />}
            {currentPath === '/billing' && <InvoiceListPage />}
            {currentPath === '/payments' && <PaymentPage api={api} />}
            {currentPath === '/wallet' && <WalletsPage api={api} />}
            {currentPath === '/canteen' && <CanteenPage api={api} />}
            {currentPath === '/canteen/pos' && <CanteenPOSPage api={api} />}
            {currentPath === '/reports' && <ReportsPage />}
            {currentPath === '/settings' && <SettingsPage />}
          </MobileShell>
          </div>
      ) : (
        <>
          <Topbar user={user} onLogout={doLogout} />
          <div className="shell">
            <Sidebar
              open={sidebarOpen}
              onClose={() => setSidebarOpen(false)}
              currentPath={currentPath}
              onNavigate={navigate}
              isMobile={isMobile}
            />
            <section className="content">
              {currentPath === '/dashboard' && <DashboardPage api={api} />}
              {currentPath === '/students' && <StudentsPage api={api} />}
              {currentPath === '/billing' && <InvoiceListPage />}
              {currentPath === '/payments' && <PaymentPage api={api} />}
              {currentPath === '/wallet' && <WalletsPage api={api} />}
              {currentPath === '/canteen' && <CanteenPage api={api} />}
              {currentPath === '/canteen/pos' && <CanteenPOSPage api={api} />}
              {currentPath === '/reports' && <ReportsPage />}
              {currentPath === '/settings' && <SettingsPage />}
              {currentPath === '/apk' && <ApkDownloadPage />}
            </section>
          </div>
        </>
      )}
      <ReceiptModal open={receiptOpen} receipt={receipt} onClose={() => setReceiptOpen(false)} onPrint={handlePrint} />
      <ReauthDialog open={reAuthOpen} message="Masukkan password untuk konfirmasi" onConfirm={onReAuthSuccess} onCancel={() => setReAuthOpen(false)} />
      {sessionExpired && (
        <div className="dialog-overlay" style={{zIndex: 2000}}>
          <div className="dialog" role="alertdialog" aria-labelledby="session-expired-title" style={{maxWidth: 360}}>
            <h3 id="session-expired-title">Sesi Berakhir</h3>
            <p>Sesi Anda berakhir, silakan masuk kembali.</p>
            <div className="dialog-actions" style={{justifyContent: 'flex-end'}}>
              <button className="btn-primary" onClick={() => { doLogout(); setSessionExpired(false); setCurrentPath('/login'); }}>OK</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function App() {
  return (
    <ApiProvider>
      <AuthProvider>
        <ToastProvider>
          <AppContent />
        </ToastProvider>
      </AuthProvider>
    </ApiProvider>
  );
}
