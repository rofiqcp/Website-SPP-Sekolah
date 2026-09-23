import { useState, useEffect } from 'react';
import { useAuth } from '../../lib/auth/AuthProvider.jsx';
import { useRfidScanner } from '../../hooks/useRfidScanner.jsx';
import { fmt } from '../../lib/formatting/index.jsx';
import ConfirmDialog from '../../components/feedback/ConfirmDialog.jsx';

export default function CanteenPOSPage({ api: propApi }) {
  const api = propApi;
  const { hasPerm, user } = useAuth();
  const { state: rfid, connectSerial } = useRfidScanner('canteen');
  const [products, setProducts] = useState([]);
  const [cart, setCart] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState(null);

  const loadProducts = async () => {
    setLoading(true);
    try {
      const j = await api.get('/canteen/products');
      setProducts(j?.items || []);
    } catch (e) { /* ignore */ }
    finally { setLoading(false); }
  };

  useEffect(() => { loadProducts(); }, [api]);

  useEffect(() => {
    if (!rfid.lastUid) return;
    const found = products.find(p => p.rfid_tag === rfid.lastUid);
    if (found) addToCart(found);
  }, [rfid.lastUid, products]);

  const addToCart = (product) => {
    setCart(c => {
      const ex = c.find(x => x.id === product.id);
      if (ex) return c.map(x => x.id === product.id ? { ...x, qty: x.qty + 1 } : x);
      return [...c, { ...product, qty: 1 }];
    });
  };

  const updateQty = (id, qty) => {
    if (qty <= 0) setCart(c => c.filter(x => x.id !== id));
    else setCart(c => c.map(x => x.id === id ? { ...x, qty } : x));
  };

  const total = cart.reduce((a, i) => a + (i.selling_price * i.qty), 0);

  const checkout = async () => {
    setSubmitting(true);
    try {
      await api.post('/canteen/checkout', { items: cart.map(i => ({ product_id: i.id, qty: i.qty })), total });
      setCart([]);
      loadProducts();
    } catch (e) { setError?.(e.message); }
    finally { setSubmitting(false); setConfirmOpen(false); }
  };

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>POS Kantin</h1><p>Role: {user?.role?.replace(/_/g,' ')}</p></div>
        <div style={{display:'flex',gap:8,alignItems:'center'}}>
          <span className="rfid-indicator"><span className={`dot ${rfid.status?.includes('ready')||rfid.status?.includes('connected')?'green':''}`}></span><small>{rfid.status || 'RFID siap'}</small></span>
          <button className="ghost" onClick={connectSerial} disabled={!!rfid.serialPort}>Hubungkan Serial</button>
        </div>
      </div>
      <div className="grid-2">
        <div>
          {loading ? <div className="loading-container"><div className="loading-spinner"></div></div> : (
            <div className="product-grid">
              {products.map(p => (
                <button key={p.id} className="product-card" onClick={()=>addToCart(p)}>
                  <b>{p.name}</b>
                  <span>{fmt(p.selling_price)}</span>
                  <small>Stok {p.stock_qty}</small>
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="canteen-orders">
          <h3>Keranjang</h3>
          {cart.length === 0 && <p style={{color:'var(--muted)',fontSize:14}}>Belum ada item</p>}
          {cart.map(i => (
            <div key={i.id} className="cart-item">
              <div><b>{i.name}</b><div><small>{fmt(i.selling_price)} x {i.qty}</small></div></div>
              <div style={{display:'flex',alignItems:'center',gap:8}}>
                <button className="ghost" onClick={()=>updateQty(i.id, i.qty-1)}>-</button>
                <b>{i.qty}</b>
                <button className="ghost" onClick={()=>updateQty(i.id, i.qty+1)}>+</button>
              </div>
            </div>
          ))}
          {cart.length > 0 && <div className="cart-total"><span>Total</span><b>{fmt(total)}</b></div>}
          {cart.length > 0 && <button style={{marginTop:12,width:'100%'}} onClick={()=>setConfirmOpen(true)} disabled={submitting}>{submitting?'Memproses...':'Bayar / Cetak Struk'}</button>}
        </div>
      </div>
      <ConfirmDialog open={confirmOpen} title="Checkout Kantin" message={`Total ${fmt(total)}. Lanjutkan?`} onConfirm={checkout} onCancel={()=>setConfirmOpen(false)} />
    </div>
  );
}
