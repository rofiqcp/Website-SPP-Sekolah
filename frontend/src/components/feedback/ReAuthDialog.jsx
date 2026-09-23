import { useState, useRef, useEffect } from 'react';
import { useApi } from '../../lib/api/client.jsx';

export default function ReAuthDialog({ open, title = 'Konfirmasi Ulang', message, confirmLabel = 'Konfirmasi', cancelLabel = 'Batal', onSubmit, onCancel }) {
  const api = useApi();
  const [pw, setPw] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) {
      setPw(''); setError(null); setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  if (!open) return null;

  const submit = async () => {
    if (!pw) { setError('Password wajib diisi'); return; }
    setError(null); setLoading(true);
    try {
      // ponytail: mock verify until /auth/verify-password endpoint exists
      let verified = false;
      if (api) {
        try {
          await api.post('/auth/verify-password', { password: pw });
          verified = true;
        } catch (e) {
          // Verification failed — do NOT set verified=true
          setError(e.response?.data?.error || 'Password salah');
          setLoading(false);
          return;
        }
      } else {
        setError('API tidak tersedia');
        setLoading(false);
        return;
      }
      if (verified) {
        onSubmit?.(pw);
        setPw('');
      }
    } catch (e) {
      setError(e.message || 'Verifikasi gagal');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="confirm-dialog" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
        <h3>{title}</h3>
        {message && <p>{message}</p>}
        <input
          ref={inputRef}
          type="password"
          value={pw}
          onChange={e => setPw(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !loading && submit()}
          className="pin-input"
          placeholder="Masukkan password"
          disabled={loading}
        />
        {error && <p className="field-error">{error}</p>}
        <div className="confirm-actions">
          <button className="ghost" onClick={onCancel} disabled={loading}>{cancelLabel}</button>
          <button onClick={submit} disabled={loading}>{loading ? 'Memeriksa...' : confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}
