import { useEffect, useState } from 'react';
import { LoadingState, ErrorState } from '../../components/common/State.jsx';
import { fmtDate } from '../../lib/formatting/index.jsx';

const API_BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

export default function ApkDownloadPage() {
  const [apkInfo, setApkInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${API_BASE}/apk/latest`);
      if (!res.ok) throw new Error('Gagal memuat info APK');
      const j = await res.json();
      setApkInfo(j);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <LoadingState text="Memuat info APK..." />;
  if (error) return <ErrorState text={error} onRetry={load} />;
  if (!apkInfo) return <ErrorState text="APK belum tersedia" />;

  return <div className="page">
    <div className="page-head"><h1>📱 Download APK</h1><p>Aplikasi Android SPP El Yaomy</p></div>
    <div className="apk-card">
      <div className="apk-info">
        <h2>{apkInfo.app_name || 'SPP El Yaomy'}</h2>
        <p>Versi: <strong>{apkInfo.version || '-'}</strong></p>
        {apkInfo.build_number && <p>Build: {apkInfo.build_number}</p>}
        {apkInfo.updated_at && <p>Update: {fmtDate(apkInfo.updated_at)}</p>}
        {apkInfo.size_bytes && <p>Ukuran: {(apkInfo.size_bytes / 1048576).toFixed(1)} MB</p>}
        {apkInfo.changelog && <div className="apk-changelog"><h3>Perubahan</h3><pre>{apkInfo.changelog}</pre></div>}
      </div>
      {apkInfo.download_url && (
        <a href={apkInfo.download_url} className="apk-download-btn" download>
          ⬇ Download APK
        </a>
      )}
    </div>
  </div>;
}
