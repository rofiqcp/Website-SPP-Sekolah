import { useState, useEffect, useCallback, createContext, useContext, useRef } from 'react';

const ToastContext = createContext(null);

export function useToast() { return useContext(ToastContext); }

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const toastsRef = useRef([]);

  const showToast = useCallback((message, type = 'info', duration = 3000) => {
    const id = Date.now() + Math.random();
    const timer = setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
      toastsRef.current = toastsRef.current.filter(t => t.id !== id);
    }, duration);
    toastsRef.current = [...toastsRef.current, { id, timer }];
    setToasts(prev => [...prev, { id, message, type, duration, timer }]);
  }, []);

  const close = useCallback((id) => {
    const entry = toastsRef.current.find(t => t.id === id);
    if (entry) {
      clearTimeout(entry.timer);
      toastsRef.current = toastsRef.current.filter(t => t.id !== id);
    }
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  useEffect(() => {
    return () => {
      toastsRef.current.forEach(t => clearTimeout(t.timer));
      toastsRef.current = [];
    };
  }, []);

  return <ToastContext.Provider value={{ showToast }}>
    {children}
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.type}`} onClick={() => close(t.id)}>
          <span>{t.message}</span>
          <button className="toast-close" onClick={(e) => { e.stopPropagation(); close(t.id); }}>✕</button>
        </div>
      ))}
    </div>
  </ToastContext.Provider>;
}
