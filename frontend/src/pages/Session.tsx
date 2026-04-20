import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getSession, compile, addConstraint } from '../api/client'
import type { ProblemSpace, CompileResponse, Constraint, Factor } from '../types'
import CandidateCard from '../components/CandidateCard'
import CoverageMap from '../components/CoverageMap'

export default function Session() {
  const { id } = useParams<{ id: string }>()
  const [ps, setPs] = useState<ProblemSpace | null>(null)
  const [candidates, setCandidates] = useState<CompileResponse['candidates']>([])
  const [safetyVerdict, setSafetyVerdict] = useState('')
  const [safetyNotes, setSafetyNotes] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [compiling, setCompiling] = useState(false)
  const [error, setError] = useState('')

  // Constraint form
  const [conDesc, setConDesc] = useState('')
  const [conType, setConType] = useState('material_unavailable')
  const [conFactorId, setConFactorId] = useState('')
  const [conLevelId, setConLevelId] = useState('')

  useEffect(() => {
    if (!id) return
    getSession(id)
      .then(data => { setPs(data); setCandidates(data.candidates || []) })
      .catch(() => setError('Session not found'))
      .finally(() => setLoading(false))
  }, [id])

  const handleCompile = async () => {
    if (!id) return
    setCompiling(true)
    setError('')
    try {
      const result = await compile(id)
      setPs(result.problem_space)
      setCandidates(result.candidates)
      setSafetyVerdict(result.safety_verdict)
      setSafetyNotes(result.safety_notes)
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Compilation failed')
    } finally {
      setCompiling(false)
    }
  }

  const handleAddConstraint = async () => {
    if (!id || !conDesc) return
    setCompiling(true)
    setError('')
    try {
      const constraint: Constraint = {
        description: conDesc,
        constraint_type: conType,
        excluded_factor_id: conFactorId || null,
        excluded_level_id: conLevelId || null,
      }
      const result = await addConstraint(id, constraint)
      setPs(result.problem_space)
      setCandidates(result.candidates)
      setSafetyVerdict(result.safety_verdict)
      setSafetyNotes(result.safety_notes)
      setConDesc('')
      setConFactorId('')
      setConLevelId('')
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Constraint failed')
    } finally {
      setCompiling(false)
    }
  }

  if (loading) return <p className="text-gray-500">Loading session...</p>
  if (!ps) return <p className="text-red-600">{error || 'Session not found'}</p>

  const selectedFactor = ps.factors.find(f => f.id === conFactorId)

  return (
    <div className="max-w-5xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">{ps.objective || 'Untitled Session'}</h1>
        <p className="text-xs text-gray-400 mt-1">Session: {ps.id}</p>
      </div>

      {/* ProblemSpace Summary */}
      <div className="grid grid-cols-2 gap-4">
        {/* Factors */}
        <div className="bg-white border rounded-lg p-4">
          <h2 className="text-sm font-semibold mb-2">Factors ({ps.factors.length})</h2>
          {ps.factors.map(f => (
            <div key={f.id} className="mb-2">
              <span className="text-sm font-medium">{f.name}</span>
              {f.is_safety_sensitive && (
                <span className="ml-2 text-xs bg-yellow-100 text-yellow-800 px-1 rounded">safety</span>
              )}
              <div className="flex gap-1 mt-1 flex-wrap">
                {f.levels.map(l => (
                  <span
                    key={l.id}
                    className={`text-xs px-2 py-0.5 rounded ${l.available ? 'bg-gray-100' : 'bg-red-100 text-red-600 line-through'
                      }`}
                  >
                    {l.name}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Hypotheses */}
        <div className="bg-white border rounded-lg p-4">
          <h2 className="text-sm font-semibold mb-2">Hypotheses ({ps.hypotheses.length})</h2>
          {ps.hypotheses.map(h => (
            <div key={h.id} className="mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-gray-400">{h.id}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded ${h.epistemic_state === 'supported' ? 'bg-green-100 text-green-700' :
                  h.epistemic_state === 'challenged' ? 'bg-red-100 text-red-700' :
                    'bg-gray-100 text-gray-600'
                  }`}>
                  {h.epistemic_state}
                </span>
              </div>
              <p className="text-sm mt-0.5">{h.statement}</p>
            </div>
          ))}
        </div>

        {/* Evidence */}
        {ps.evidence.length > 0 && (
          <div className="bg-white border rounded-lg p-4">
            <h2 className="text-sm font-semibold mb-2">Evidence ({ps.evidence.length})</h2>
            {ps.evidence.map(e => (
              <div key={e.id} className="mb-2 text-sm">
                <span className="text-xs font-mono text-gray-400">{e.id}</span>
                <span className="text-xs text-gray-400 ml-2">[{e.source_type}]</span>
                <p className="text-gray-700 mt-0.5">{e.content}</p>
              </div>
            ))}
          </div>
        )}

        {/* Constraints */}
        <div className="bg-white border rounded-lg p-4">
          <h2 className="text-sm font-semibold mb-2">Constraints ({ps.constraints.length})</h2>
          {ps.constraints.length === 0 ? (
            <p className="text-sm text-gray-400">No constraints</p>
          ) : (
            ps.constraints.map((c, i) => (
              <div key={c.id || i} className="mb-1 text-sm">
                <span className={`text-xs px-1.5 py-0.5 rounded mr-2 ${c.is_safety_constraint ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'
                  }`}>
                  {c.constraint_type}
                </span>
                {c.description}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Safety */}
      {safetyVerdict && safetyVerdict !== 'allow' && (
        <div className={`border rounded-lg p-4 ${safetyVerdict === 'block' ? 'bg-red-50 border-red-200' : 'bg-yellow-50 border-yellow-200'
          }`}>
          <h2 className="text-sm font-semibold mb-1">
            Safety: {safetyVerdict.toUpperCase()}
          </h2>
          {safetyNotes.map((n, i) => (
            <p key={i} className="text-sm">{n}</p>
          ))}
        </div>
      )}

      {safetyVerdict === 'block' && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <h2 className="text-lg font-semibold text-red-800 mb-2">
            Compilation Blocked
          </h2>
          <p className="text-sm text-red-700">
            This problem space contains content that requires mandatory human review.
            Tessellarium cannot compile experimental designs for clinical or therapeutic advisory queries.
          </p>
          <p className="text-sm text-gray-600 mt-2">
            Modify the problem space to remove clinical advisory language, then recompile.
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3 items-end">
        <button
          onClick={handleCompile}
          disabled={compiling}
          className="bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {compiling ? 'Compiling...' : candidates.length > 0 ? 'Recompile' : 'Compile'}
        </button>

        {ps.total_combinations > 0 && (
          <span className="text-sm text-gray-500">
            {ps.tested_combinations}/{ps.total_combinations} combinations tested
          </span>
        )}
      </div>

      {/* Add Constraint */}
      <div className="bg-white border rounded-lg p-4">
        <h2 className="text-sm font-semibold mb-3">Add Constraint</h2>
        <div className="flex gap-3 items-end flex-wrap">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs text-gray-500 mb-1">Description</label>
            <input
              value={conDesc}
              onChange={e => setConDesc(e.target.value)}
              placeholder="e.g. Lot C is exhausted"
              className="w-full border rounded px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Type</label>
            <select
              value={conType}
              onChange={e => setConType(e.target.value)}
              className="border rounded px-3 py-1.5 text-sm"
            >
              <option value="material_unavailable">Material Unavailable</option>
              <option value="safety_exclusion">Safety Exclusion</option>
              <option value="budget">Budget</option>
              <option value="equipment">Equipment</option>
              <option value="time">Time</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Factor</label>
            <select
              value={conFactorId}
              onChange={e => { setConFactorId(e.target.value); setConLevelId('') }}
              className="border rounded px-3 py-1.5 text-sm"
            >
              <option value="">--</option>
              {ps.factors.map(f => (
                <option key={f.id} value={f.id}>{f.name}</option>
              ))}
            </select>
          </div>
          {selectedFactor && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">Level</label>
              <select
                value={conLevelId}
                onChange={e => setConLevelId(e.target.value)}
                className="border rounded px-3 py-1.5 text-sm"
              >
                <option value="">--</option>
                {selectedFactor.levels.map(l => (
                  <option key={l.id} value={l.id}>{l.name}</option>
                ))}
              </select>
            </div>
          )}
          <button
            onClick={handleAddConstraint}
            disabled={!conDesc || compiling}
            className="bg-gray-800 text-white px-4 py-1.5 rounded text-sm font-medium hover:bg-gray-700 disabled:opacity-50"
          >
            Add & Recompile
          </button>
        </div>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      {/* Coverage Map */}
      {ps.coverage_map.length > 0 && (
        <CoverageMap
          cells={ps.coverage_map}
          factors={ps.factors}
          totalCombinations={ps.total_combinations}
          testedCombinations={ps.tested_combinations}
        />
      )}

      {/* Candidates */}
      {candidates.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">
            Candidates ({candidates.length})
          </h2>
          <div className="space-y-4">
            {candidates.map((c, i) => (
              <CandidateCard
                key={c.id}
                candidate={c}
                index={i}
                factors={ps.factors}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
