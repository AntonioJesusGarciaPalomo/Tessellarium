import type { VerificationStatus } from '../types'

const badges: Record<VerificationStatus, { label: string; className: string }> = {
  verified: { label: 'VERIFIED', className: 'bg-green-100 text-green-800' },
  failed: { label: 'FAILED', className: 'bg-red-100 text-red-800' },
  timeout: { label: 'TIMEOUT', className: 'bg-yellow-100 text-yellow-800' },
  not_attempted: { label: 'NOT ATTEMPTED', className: 'bg-gray-100 text-gray-600' },
}

export default function VerificationBadge({ status }: { status: VerificationStatus }) {
  const b = badges[status] || badges.not_attempted
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${b.className}`}>
      {status === 'verified' && <span className="mr-1">&#10003;</span>}
      {status === 'failed' && <span className="mr-1">&#10007;</span>}
      {status === 'timeout' && <span className="mr-1">&#9203;</span>}
      {b.label}
    </span>
  )
}
