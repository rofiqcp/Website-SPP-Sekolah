import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { useApi, AuthError } from '../api/client.jsx';

const AuthContext = createContext(null);

const ROLES = ['super_admin','admin','bendahara','kasir','wali_kelas','guru','siswa','orang_tua','auditor','petugas_kantin','petugas_gudang','kepala_sekolah','admin_unit'];
export const DEMO_CREDS = [
  ['admin@elyaomy.sch.id','admin123','super_admin'],
  ['bendahara@elyaomy.sch.id','admin123','bendahara'],
  ['kepsek@elyaomy.sch.id','admin123','kepala_sekolah'],
  ['kasir@elyaomy.sch.id','admin123','kasir'],
  ['kantin@elyaomy.sch.id','admin123','petugas_kantin'],
  ['wali@elyaomy.sch.id','admin123','wali_kelas'],
  ['guru@elyaomy.sch.id','admin123','guru'],
  ['siswa@elyaomy.sch.id','admin123','siswa'],
  ['ortu@elyaomy.sch.id','admin123','orang_tua'],
  ['auditor@elyaomy.sch.id','admin123','auditor'],
];

export function AuthProvider({ children }) {
  const api = useApi();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/auth/me')
      .then(r => { if (r.user) setUser(r.user); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [api]);

  const doLogin = useCallback(async (email, password, mfa_code) => {
    const body = { email, password };
    if (mfa_code) body.mfa_code = mfa_code;
    const res = await api.post('/auth/login', body);
    if (res.user) setUser(res.user);
    return res;
  }, [api]);

  const doLogout = useCallback(async () => {
    try {
      await api.post('/auth/logout');
    } catch (e) {
      console.warn('Server logout failed, clearing local state anyway:', e);
    }
    setUser(null);
  }, [api]);

  const hasPerm = useCallback((perm) => {
    if (!user) return false;
    const perms = user.permissions || [];
    return perms.includes(perm);
  }, [user]);

  const hasObjectAccess = useCallback((perm, obj) => {
    if (!hasPerm(perm)) return false;
    if (!user || !obj) return true;
    if (obj.unit_id && !user?.allowed_unit_ids?.includes(obj.unit_id)) return false;
    if (user.role === 'orang_tua' && obj.student_id && !user.guardian_student_ids?.includes(obj.student_id)) return false;
    return true;
  }, [user, hasPerm]);

  return <AuthContext.Provider value={{ user, setUser, loading, doLogin, doLogout, hasPerm, hasObjectAccess }}>
    {children}
  </AuthContext.Provider>;
}

export function useAuth() { return useContext(AuthContext); }