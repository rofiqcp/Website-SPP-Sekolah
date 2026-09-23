import { fmt, fmtDateTime } from '../../lib/formatting/index.jsx';

export default function ReceiptModal({ open, receipt, onClose, onPrint }) {
  if (!open || !receipt) return null;

  const handlePrint = () => {
    // Open print dialog targeting only the receipt
    const el = document.getElementById('receipt-print-area');
    if (el) {
      const orig = document.body.innerHTML;
      const printWindow = window.open('', '_blank', 'width=400,height=600');
      if (printWindow) {
        const doc = printWindow.document;
        doc.open();
        doc.write('<!doctype html><html><head><title>Struk</title><style>' + RECEIPT_PRINT_CSS + '</style></head><body></body></html>');
        doc.close();
        // Safe DOM transfer: use cloneNode instead of innerHTML to avoid XSS
        const src = document.getElementById('receipt-print-area');
        if (src) {
          const clone = src.cloneNode(true);
          doc.body.appendChild(clone);
        }
        printWindow.focus();
        printWindow.print();
        printWindow.close();
        return;
      }
    }
    // Fallback: global window.print()
    onPrint?.();
  };

  const handleDownload = () => {
    const data = formatReceiptText(receipt);
    const blob = new Blob([data], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `struk-${receipt.id || Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="modal-backdrop receipt-backdrop" onClick={onClose}>
      <div className="receipt-modal" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
        <div id="receipt-print-area" className="receipt-preview">
          <div className="receipt-header">
            <h3 className="receipt-store">{receipt.store || 'El Yaomy Klaten'}</h3>
            {receipt.address && <p className="receipt-addr">{receipt.address}</p>}
            <p className="receipt-date">{fmtDateTime(receipt.date)}</p>
          </div>
          <div className="receipt-divider" />
          {receipt.cashier && <p className="receipt-line"><span>Kasir</span><span>{receipt.cashier}</span></p>}
          {receipt.student_name && <p className="receipt-line"><span>Siswa</span><span>{receipt.student_name}</span></p>}
          <div className="receipt-divider" />
          {receipt.items?.map((it, idx) => (
            <div key={idx} className="receipt-item">
              <div className="receipt-item-name">{it.name} x{it.qty}</div>
              <div className="receipt-item-price">{fmt((it.price || 0) * (it.qty || 1))}</div>
            </div>
          ))}
          <div className="receipt-divider" />
          <div className="receipt-total">
            <span>Total</span>
            <span>{fmt(receipt.total || 0)}</span>
          </div>
          {receipt.paid !== undefined && receipt.paid !== null && (
            <p className="receipt-line"><span>Bayar</span><span>{fmt(receipt.paid)}</span></p>
          )}
          {receipt.change !== undefined && receipt.change !== null && (
            <p className="receipt-line"><span>Kembali</span><span>{fmt(receipt.change)}</span></p>
          )}
          <p className="receipt-line"><span>Metode</span><span>{receipt.method || 'Tunai'}</span></p>
          {receipt.id && <p className="receipt-line"><span>No</span><span>#{receipt.id}</span></p>}
          <div className="receipt-divider" />
          <p className="receipt-footer">Terima kasih</p>
          {receipt.note && <p className="receipt-note">{receipt.note}</p>}
        </div>
        <div className="receipt-actions no-print">
          <button className="ghost" onClick={onClose}>Tutup</button>
          <button onClick={handleDownload}>Download</button>
          <button onClick={handlePrint}>Cetak</button>
        </div>
      </div>
    </div>
  );
}

function formatReceiptText(r) {
  const lines = [];
  lines.push(r.store || 'El Yaomy Klaten');
  if (r.address) lines.push(r.address);
  lines.push(fmtDateTime(r.date));
  lines.push('-'.repeat(32));
  if (r.cashier) lines.push(`Kasir     : ${r.cashier}`);
  if (r.student_name) lines.push(`Siswa     : ${r.student_name}`);
  lines.push('-'.repeat(32));
  (r.items || []).forEach(it => {
    const subtotal = (it.price || 0) * (it.qty || 1);
    lines.push(`${it.name} x${it.qty}`);
    lines.push(`   ${fmt(subtotal)}`);
  });
  lines.push('-'.repeat(32));
  lines.push(`Total     : ${fmt(r.total || 0)}`);
  if (r.paid != null) lines.push(`Bayar     : ${fmt(r.paid)}`);
  if (r.change != null) lines.push(`Kembali   : ${fmt(r.change)}`);
  lines.push(`Metode    : ${r.method || 'Tunai'}`);
  if (r.id) lines.push(`No        : #${r.id}`);
  lines.push('-'.repeat(32));
  lines.push('Terima kasih');
  if (r.note) lines.push(r.note);
  return lines.join('\n');
}

const RECEIPT_PRINT_CSS = `
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Courier New', monospace; font-size: 12px; color: #000; width: 80mm; padding: 4mm; }
  .receipt-header { text-align: center; }
  .receipt-store { font-size: 14px; font-weight: bold; }
  .receipt-addr, .receipt-date { font-size: 11px; }
  .receipt-divider { border-top: 1px dashed #000; margin: 4px 0; }
  .receipt-line, .receipt-total { display: flex; justify-content: space-between; font-size: 12px; }
  .receipt-total { font-weight: bold; }
  .receipt-item { display: flex; justify-content: space-between; font-size: 12px; }
  .receipt-item-name { flex: 1; }
  .receipt-item-price { text-align: right; }
  .receipt-footer { text-align: center; margin-top: 4px; }
  .receipt-note { font-size: 10px; text-align: center; margin-top: 2px; }
`;
