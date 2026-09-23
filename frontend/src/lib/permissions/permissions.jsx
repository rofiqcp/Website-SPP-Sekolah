// Permission mapping per role — mirror of DB permissions. ponytail: replace with API-driven when roles become dynamic.
const ROLE_PERMISSIONS = {
  super_admin: ['accounting.close','accounting.journal','accounting.view','approvals.decide','assets.depreciate','assets.manage','audit.view','billing.generate','billing.manage','budget.approve','budget.manage','canteen.checkout','canteen.manage','cashier.close','cashier.open','cashier.pay','classes.manage','dashboard.view','employees.manage','inventory.manage','inventory.stock','invoices.manage','mfa.manage','payments.create','payments.refund','reports.view','rfid.block','rfid.issue','rfid.manage','roles.manage','students.manage','students.view','units.manage','users.manage','wallet.adjust','wallet.debit','wallet.topup'],
  admin: ['dashboard.view','students.view','students.manage','billing.manage','billing.generate','payments.create','wallet.topup','wallet.debit','canteen.manage','canteen.checkout','inventory.manage','inventory.stock','rfid.manage','rfid.issue','reports.view','mfa.manage'],
  bendahara: ['accounting.close','accounting.journal','accounting.view','approvals.decide','assets.depreciate','assets.manage','audit.view','billing.generate','billing.manage','budget.approve','budget.manage','canteen.checkout','canteen.manage','cashier.open','cashier.pay','dashboard.view','inventory.manage','inventory.stock','invoices.manage','mfa.manage','payments.create','payments.refund','reports.view','rfid.block','rfid.manage','students.view','users.manage','wallet.adjust','wallet.debit','wallet.topup'],
  kasir: ['canteen.checkout','cashier.open','cashier.pay','dashboard.view','inventory.stock','payments.create','students.view','wallet.debit','wallet.topup'],
  wali_kelas: ['dashboard.view','reports.view','students.view','wallet.topup'],
  guru: ['dashboard.view','reports.view','students.view','wallet.topup'],
  siswa: ['dashboard.view','wallet.debit'],
  orang_tua: ['dashboard.view','payments.create','reports.view','wallet.debit'],
  auditor: ['accounting.view','audit.view','dashboard.view','reports.view','students.view'],
  petugas_kantin: ['canteen.checkout','dashboard.view'],
  petugas_gudang: ['assets.manage','dashboard.view','inventory.manage','inventory.stock'],
  kepala_sekolah: ['accounting.view','approvals.decide','audit.view','budget.approve','dashboard.view','invoices.manage','reports.view','students.view'],
  admin_unit: ['accounting.close','accounting.journal','accounting.view','assets.depreciate','assets.manage','audit.view','billing.generate','billing.manage','budget.approve','budget.manage','canteen.checkout','canteen.manage','cashier.close','cashier.open','cashier.pay','classes.manage','dashboard.view','employees.manage','inventory.manage','inventory.stock','mfa.manage','payments.create','payments.refund','reports.view','rfid.block','rfid.issue','rfid.manage','students.manage','students.view','units.manage','users.manage','wallet.adjust','wallet.debit','wallet.topup'],
};

export function getRolePermissions(role) {
  return ROLE_PERMISSIONS[role] || [];
}

export function can(user, permission, obj = null) {
  const perms = user?.permissions || getRolePermissions(user?.role) || [];
  if (!perms.includes(permission)) return false;
  if (obj) {
    if (obj.unit_id && user?.allowed_unit_ids?.includes(obj.unit_id)) return false;
    if (user?.role === 'orang_tua' && obj.student_id && !user?.guardian_student_ids?.includes(obj.student_id)) return false;
  }
  return true;
}
