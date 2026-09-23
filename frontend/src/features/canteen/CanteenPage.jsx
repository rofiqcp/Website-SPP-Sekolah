import { useState, useEffect } from 'react';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/State.jsx';

export default function CanteenPage({ api }) {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true); setError(null);
      try {
        const j = await api.get('/canteen/products');
        setProducts(j?.items || []);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [api]);

  if (loading) return <LoadingState text="Memuat produk kantin..." />;
  if (error) return <ErrorState text={error} />;
  if (!products.length) return <EmptyState text="Belum ada produk kantin" />;

  return <div className="page">
    <div className="page-head"><h1>E-Kantin</h1><p>Kelola produk dan menu kantin</p></div>
    <div className="product-grid">
      {products.map(p => (
        <div key={p.id} className="product-card">
          <b>{p.name}</b>
          <small>{new Intl.NumberFormat('id-ID',{style:'currency',currency:'IDR',maximumFractionDigits:0}).format(p.price || 0)}</small>
        </div>
      ))}
    </div>
  </div>;
}
