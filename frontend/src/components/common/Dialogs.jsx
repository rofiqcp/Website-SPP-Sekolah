import { useState } from 'react';

export function ConfirmDialog({ open, title, message, confirmLabel = 'Ya', cancelLabel = 'Batal', onConfirm, onCancel }) {
  if (!open) return null;
  return <div className="modal-backdrop" onClick={onCancel}>
    <div className="confirm-dialog" onClick={e => e.stopPropagation()}>
      <h3>{title}</h3>
      <p>{message}</p>
      <div className="confirm-actions">
        <button className="ghost" onClick={onCancel}>{cancelLabel}</button>
        <button className="danger" onClick={onConfirm}>{confirmLabel}</button>
      </div>
    </div>
  </div>;
}

export function PinDialog({ open, title = 'Konfirmasi PIN', message, onSubmit, onCancel, cancelLabel = 'Batal' }) {
  const [pin, setPin] = useState('');
  const [error, setError] = useState(null);
  if (!open) return null;

  const submit = () => {
    if (!pin) { setError('PIN wajib diisi'); return; }
    setError(null);
    onSubmit(pin);
    setPin('');
  };

  return <div className="modal-backdrop" onClick={onCancel}>
    <div className="confirm-dialog" onClick={e => e.stopPropagation()}>
      <h3>{title}</h3>
      <p>{message}</p>
      <input type="password" value={pin} onChange={e => setPin(e.target.value)} onKeyDown={e => e.key === 'Enter' && submit()} autoFocus className="pin-input" placeholder="••••••" />
      {error && <p className="field-error">{error}</p>}
      <div className="confirm-actions">
        <button className="ghost" onClick={() => { setPin(''); onCancel(); }}>{cancelLabel}</button>
        <button className="primary" onClick={submit}>Konfirmasi</button>
      </div>
    </div>
  </div>;
}

export function ReauthDialog({ open, title = 'Masukkan Password', message, onSubmit, onCancel, cancelLabel = 'Batal' }) {
  const [pw, setPw] = useState('');
  const [error, setError] = useState(null);
  if (!open) return null;

  const submit = () => {
    if (!pw) { setError('Password wajib diisi'); return; }
    setError(null);
    onSubmit(pw);
    setPw('');
  };

  return <div className="modal-backdrop" onClick={onCancel}>
    <div className="confirm-dialog" onClick={e => e.stopPropagation()}>
      <h3>{title}</h3>
      <p>{message}</p>
      <input type="password" value={pw} onChange={e => setPw(e.target.value)} onKeyDown={e => e.key === 'Enter' && submit()} autoFocus className="pin-input" />
      {error && <p className="field-error">{error}</p>}
      <div className="confirm-actions">
        <button className="ghost" onClick={() => { setPw(''); onCancel(); }}>{cancelLabel}</button>
        <button className="primary" onClick={submit}>Konfirmasi</button>
      </div>
    </div>
  </div>;
}