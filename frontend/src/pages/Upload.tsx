import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadFiles, parseText } from '../api/client'

export default function Upload() {
  const navigate = useNavigate()
  const [protocol, setProtocol] = useState<File | null>(null)
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [image, setImage] = useState<File | null>(null)
  const [context, setContext] = useState('')
  const [budget, setBudget] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [mode, setMode] = useState<'file' | 'text'>('file')
  const [protocolText, setProtocolText] = useState('')

  const handleFileUpload = async () => {
    setLoading(true)
    setError('')
    try {
      const formData = new FormData()
      if (protocol) formData.append('protocol', protocol)
      if (csvFile) formData.append('csv_file', csvFile)
      if (image) formData.append('image', image)
      if (budget) formData.append('max_runs_budget', budget)
      const result = await uploadFiles(formData)
      navigate(`/session/${result.session_id}`)
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  const handleTextParse = async () => {
    setLoading(true)
    setError('')
    try {
      const result = await parseText({
        protocol_text: protocolText || undefined,
        user_context: context || undefined,
        max_runs_budget: budget ? parseInt(budget) : undefined,
      })
      navigate(`/session/${result.session_id}`)
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Parse failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold mb-6">New Experiment</h1>

      {/* Mode toggle */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setMode('file')}
          className={`px-4 py-2 rounded text-sm font-medium ${
            mode === 'file' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'
          }`}
        >
          Upload Files
        </button>
        <button
          onClick={() => setMode('text')}
          className={`px-4 py-2 rounded text-sm font-medium ${
            mode === 'text' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'
          }`}
        >
          Paste Text
        </button>
      </div>

      <div className="bg-white rounded-lg border p-6 space-y-4">
        {mode === 'file' ? (
          <>
            <div>
              <label className="block text-sm font-medium mb-1">Protocol PDF</label>
              <input
                type="file"
                accept=".pdf"
                onChange={e => setProtocol(e.target.files?.[0] || null)}
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Results CSV</label>
              <input
                type="file"
                accept=".csv"
                onChange={e => setCsvFile(e.target.files?.[0] || null)}
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Experiment Image</label>
              <input
                type="file"
                accept="image/*"
                onChange={e => setImage(e.target.files?.[0] || null)}
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              />
            </div>
          </>
        ) : (
          <div>
            <label className="block text-sm font-medium mb-1">Protocol / Experiment Description</label>
            <textarea
              value={protocolText}
              onChange={e => setProtocolText(e.target.value)}
              rows={10}
              placeholder="Paste your protocol text, experiment description, or raw observations..."
              className="w-full border rounded-lg p-3 text-sm"
            />
          </div>
        )}

        <div>
          <label className="block text-sm font-medium mb-1">Additional Context</label>
          <textarea
            value={context}
            onChange={e => setContext(e.target.value)}
            rows={3}
            placeholder="Any additional context for the parser..."
            className="w-full border rounded-lg p-3 text-sm"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Run Budget</label>
          <input
            type="number"
            value={budget}
            onChange={e => setBudget(e.target.value)}
            placeholder="Max additional runs (optional)"
            className="border rounded-lg p-2 text-sm w-40"
          />
        </div>

        {error && (
          <p className="text-red-600 text-sm">{error}</p>
        )}

        <button
          onClick={mode === 'file' ? handleFileUpload : handleTextParse}
          disabled={loading}
          className="bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {loading ? 'Processing...' : 'Submit'}
        </button>
      </div>
    </div>
  )
}
