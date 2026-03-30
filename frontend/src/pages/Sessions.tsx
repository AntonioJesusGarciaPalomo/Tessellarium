import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listSessions } from '../api/client'
import type { SessionSummary } from '../types'

export default function Sessions() {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listSessions()
      .then(setSessions)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold mb-6">Sessions</h1>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : sessions.length === 0 ? (
        <div className="text-gray-500">
          <p>No sessions yet.</p>
          <Link to="/upload" className="text-blue-600 hover:underline mt-2 inline-block">
            Start a new experiment
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {sessions.map(s => (
            <Link
              key={s.id}
              to={`/session/${s.id}`}
              className="block bg-white border rounded-lg p-4 hover:border-blue-300 transition-colors"
            >
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-medium">{s.objective || 'Untitled session'}</p>
                  <p className="text-xs text-gray-400 mt-1">{s.id}</p>
                </div>
                <span className="text-xs text-gray-400">
                  {new Date(s.updated_at).toLocaleDateString()}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
