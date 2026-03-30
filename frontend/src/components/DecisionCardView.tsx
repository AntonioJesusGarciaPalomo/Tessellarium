import type { DecisionCard } from '../types'

function highlightCitations(text: string) {
  return text.replace(/\[(\d+)\]/g, '<span class="text-blue-600 font-medium">[$1]</span>')
}

export default function DecisionCardView({ card }: { card: DecisionCard }) {
  return (
    <div className="border rounded-lg p-4 space-y-3 bg-blue-50/30">
      <h4 className="font-semibold text-sm text-blue-800">Decision Card</h4>

      <div>
        <span className="text-xs font-medium text-gray-500 uppercase">Recommendation</span>
        <p className="text-sm mt-0.5">{card.recommendation}</p>
      </div>

      <div>
        <span className="text-xs font-medium text-gray-500 uppercase">Why</span>
        <p
          className="text-sm mt-0.5"
          dangerouslySetInnerHTML={{ __html: highlightCitations(card.why) }}
        />
      </div>

      <div>
        <span className="text-xs font-medium text-gray-500 uppercase">Evidence Used</span>
        <ul className="text-sm mt-0.5 space-y-0.5">
          {card.evidence_used.map((e, i) => (
            <li
              key={i}
              className="text-gray-700"
              dangerouslySetInnerHTML={{ __html: highlightCitations(e) }}
            />
          ))}
        </ul>
      </div>

      <div>
        <span className="text-xs font-medium text-gray-500 uppercase">Assumptions</span>
        <ul className="text-sm mt-0.5 list-disc list-inside text-gray-700">
          {card.assumptions.map((a, i) => <li key={i}>{a}</li>)}
        </ul>
      </div>

      <div>
        <span className="text-xs font-medium text-gray-500 uppercase">Limits / Counterevidence</span>
        <ul className="text-sm mt-0.5 list-disc list-inside text-gray-700">
          {card.counterevidence_or_limits.map((l, i) => <li key={i}>{l}</li>)}
        </ul>
      </div>

      <div>
        <span className="text-xs font-medium text-gray-500 uppercase">What Would Change This</span>
        <p className="text-sm mt-0.5 text-gray-700">{card.what_would_change_mind}</p>
      </div>
    </div>
  )
}
