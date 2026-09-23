export function fmt(v) { return new Intl.NumberFormat('id-ID',{style:'currency',currency:'IDR',maximumFractionDigits:0}).format(Number(v)||0); }
export function fmtDate(d) { return d ? d.split('T')[0] : '-'; }
export function fmtDateTime(d) { return d ? new Date(d).toLocaleString('id-ID') : '-'; }
export function fmtNum(v) { return new Intl.NumberFormat('id-ID').format(Number(v)||0); }
