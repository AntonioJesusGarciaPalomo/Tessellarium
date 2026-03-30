import { Link } from 'react-router-dom'

export default function Home() {
  return (
    <div className="max-w-2xl">
      <h1 className="text-3xl font-bold mb-4">Tessellarium</h1>
      <p className="text-gray-600 mb-6">
        A decisive experiment compiler. Upload your protocol, results, and constraints.
        Tessellarium computes the optimal next experiment — not as a suggestion,
        but as a verifiable combinatorial design with quantified trade-offs.
      </p>

      <div className="bg-white rounded-lg border p-6 mb-6">
        <h2 className="font-semibold mb-3">How it works</h2>
        <ol className="list-decimal list-inside text-sm text-gray-700 space-y-2">
          <li>Upload a protocol PDF, CSV results, or describe your experiment</li>
          <li>The system extracts factors, hypotheses, and constraints</li>
          <li>The DOE Planner compiles 3 optimal candidates (deterministic, not LLM)</li>
          <li>Each candidate is critiqued and explained with grounded citations</li>
          <li>Add constraints and recompile to see what discrimination is lost</li>
        </ol>
      </div>

      <Link
        to="/upload"
        className="inline-block bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors"
      >
        Start New Experiment
      </Link>
    </div>
  )
}
