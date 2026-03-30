import type { ExperimentCandidate, Factor } from '../types'
import DesignMatrixTable from './DesignMatrixTable'
import VerificationBadge from './VerificationBadge'
import DecisionCardView from './DecisionCardView'

const strategyLabels: Record<string, string> = {
  max_discrimination: 'Max Discrimination',
  max_robustness: 'Max Robustness',
  max_coverage: 'Max Coverage',
}

interface Props {
  candidate: ExperimentCandidate
  index: number
  factors: Factor[]
}

export default function CandidateCard({ candidate, index, factors }: Props) {
  const dm = candidate.design_matrix

  return (
    <div className="bg-white border rounded-lg p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold text-gray-400">#{index + 1}</span>
          <h3 className="font-semibold">
            {strategyLabels[candidate.strategy] || candidate.strategy}
          </h3>
          <span className="px-2 py-0.5 rounded bg-gray-100 text-xs text-gray-600">
            {dm.design_family.replace(/_/g, ' ')}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">
            Score: <strong>{candidate.total_discrimination_score.toFixed(3)}</strong>
          </span>
          <VerificationBadge status={dm.verification_status} />
        </div>
      </div>

      {/* Justification */}
      <p className="text-sm text-gray-600">{candidate.justification}</p>

      {/* Design Matrix */}
      <div>
        <h4 className="text-xs font-medium text-gray-500 uppercase mb-2">
          Design Matrix ({dm.num_runs} runs)
        </h4>
        <DesignMatrixTable matrix={dm} factors={factors} />
      </div>

      {/* Discrimination Pairs */}
      {candidate.discrimination_pairs.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-gray-500 uppercase mb-2">
            Discrimination Pairs
          </h4>
          <div className="space-y-1">
            {candidate.discrimination_pairs.map((pair, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className="font-mono text-xs">
                  {pair.hypothesis_a_id} vs {pair.hypothesis_b_id}
                </span>
                <div className="flex-1 bg-gray-100 rounded-full h-2">
                  <div
                    className="bg-blue-500 h-2 rounded-full"
                    style={{ width: `${pair.discrimination_power * 100}%` }}
                  />
                </div>
                <span className="text-xs text-gray-500 w-12 text-right">
                  {(pair.discrimination_power * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Critique */}
      {candidate.critique && (
        <div>
          <h4 className="text-xs font-medium text-gray-500 uppercase mb-2">Critique</h4>
          <pre className="text-xs text-gray-600 bg-gray-50 rounded p-3 whitespace-pre-wrap">
            {candidate.critique}
          </pre>
        </div>
      )}

      {/* Decision Card */}
      {candidate.decision_card && (
        <DecisionCardView card={candidate.decision_card} />
      )}
    </div>
  )
}
