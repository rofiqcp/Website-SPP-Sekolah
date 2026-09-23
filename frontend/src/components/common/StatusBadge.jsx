const STATUS_STYLES = {
  active: 'green', published: 'green', paid: 'green', success: 'green', posted: 'green',
  pending: 'yellow', partial: 'blue', draft: 'gray', waiting_verification: 'yellow',
  waiting_approval: 'yellow', overdue: 'red', blocked: 'red', lost: 'red', failed: 'red',
  rejected: 'red', cancelled: 'gray-dark', closed: 'gray-dark', replaced: 'gray',
  expired: 'gray', damaged: 'red', frozen: 'purple', unissued: 'gray', voided: 'gray-dark',
  reversed: 'gray-dark', locked: 'purple', inactive: 'gray',
};

export function StatusBadge({ status }) {
  const cls = STATUS_STYLES[status] || 'gray';
  return <span className={`badge ${cls}`}>{status}</span>;
}
