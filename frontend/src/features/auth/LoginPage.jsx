import { useState } from 'react';
import { useAuth, DEMO_CREDS } from '../../lib/auth/AuthProvider.jsx';
import { useToast } from '../../components/common/Toast.jsx';

export default function LoginPage({ onNavigate }) {
  const { doLogin } = useAuth();
  const { showToast } = useToast();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mfaStep, setMfaStep] = useState(false);
  const [mfaCode, setMfaCode] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [showDemo, setShowDemo] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      if (!mfaStep) {
        const res = await doLogin(email, password);
        if (res?.mfa_required) { setMfaStep(true); showToast('Masukkan kode OTP dari authenticator', 'info'); return; }
        showToast('Login berhasil', 'success');
        onNavigate('/dashboard');
      } else {
        const res = await doLogin(email, password, mfaCode);
        if (res?.mfa_required) { showToast('Kode MFA salah, coba lagi', 'error'); return; }
        showToast('Login berhasil', 'success');
        onNavigate('/dashboard');
      }
    } catch (err) {
      showToast(err.message || 'Email/nomor atau password tidak sesuai', 'error');
    } finally { setSubmitting(false); }
  };

  return <div className="login-page">
    <form className="login-card" onSubmit={submit}>
      <img src="/logo%20yaomy.jpg" alt="Logo" />
      {!mfaStep ? (
        <>
          <p className="eyebrow">Login Aman</p>
          <h1>Masuk Sistem</h1>
          <label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} required autoFocus /></label>
          <label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
          <button type="submit" disabled={submitting}>{submitting ? 'Memproses...' : 'Login'}</button>
          {DEMO_CREDS.length > 0 && (
            <div className="demo-creds">
              <button type="button" className="ghost" onClick={() => setShowDemo(!showDemo)}>Demo Account</button>
              {showDemo && DEMO_CREDS.map(([e,p,r]) => (
                <button type="button" key={e} onClick={() => { setEmail(e); setPassword(p); }}>
                  {r.replace(/_/g,' ')}
                </button>
              ))}
            </div>
          )}
        </>
      ) : (
        <>
          <p className="eyebrow">Verifikasi Dua Faktor</p>
          <h1>Kode OTP</h1>
          <p style={{color:'var(--text-secondary)',textAlign:'center',marginBottom:16}}>
            Masukkan kode 6-digit dari authenticator app Anda
          </p>
          <label>Kode OTP
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              value={mfaCode}
              onChange={e => setMfaCode(e.target.value.replace(/\D/g,''))}
              required
              autoFocus
              autoComplete="one-time-code"
              placeholder="000000"
            />
          </label>
          <button type="submit" disabled={submitting || mfaCode.length !== 6}>{submitting ? 'Memverifikasi...' : 'Verifikasi'}</button>
          <button type="button" className="ghost" onClick={() => { setMfaStep(false); setMfaCode(''); }} disabled={submitting}>
            Kembali
          </button>
        </>
      )}
    </form>
  </div>;
}
