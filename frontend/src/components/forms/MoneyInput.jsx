import { useState, useEffect } from 'react';

export function MoneyInput({ value, onChange, label = 'Nominal', disabled, min = 0, placeholder = '0' }) {
  const formatRupiah = (num) => num != null && num !== '' ? new Intl.NumberFormat('id-ID').format(num) : '';
  const parseRupiah = (str) => { const n = str.replace(/[^\d]/g, ''); return n ? parseInt(n, 10) : 0; };
  const [display, setDisplay] = useState('');

  // Sync display whenever value changes externally (e.g., reset/clear)
  useEffect(() => {
    setDisplay(value != null && value !== '' ? formatRupiah(value) : '');
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleChange = (e) => {
    const raw = e.target.value;
    setDisplay(raw);
    const num = parseRupiah(raw);
    if (num >= min) onChange(num);
    else if (raw === '') onChange('');
  };

  return <div className="money-input">
    {label && <label>{label}</label>}
    <div className="money-wrapper">
      <span className="money-prefix">Rp</span>
      <input type="text" value={display} onChange={handleChange} onBlur={() => setDisplay(value ? formatRupiah(value) : '')} disabled={disabled} placeholder={placeholder} inputMode="numeric" />
    </div>
  </div>;
}