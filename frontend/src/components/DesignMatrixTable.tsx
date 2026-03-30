import type { DesignMatrix, Factor } from '../types'

interface Props {
  matrix: DesignMatrix
  factors: Factor[]
}

export default function DesignMatrixTable({ matrix, factors }: Props) {
  const factorMap = Object.fromEntries(factors.map(f => [f.id, f]))
  const factorIds = matrix.rows.length > 0 ? Object.keys(matrix.rows[0]) : []

  const levelName = (factorId: string, levelId: string) => {
    const factor = factorMap[factorId]
    if (!factor) return levelId
    const level = factor.levels.find(l => l.id === levelId)
    return level?.name || levelId
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b">
            <th className="text-left py-2 px-3 text-gray-500 font-medium">Run</th>
            {factorIds.map(fid => (
              <th key={fid} className="text-left py-2 px-3 font-medium">
                {factorMap[fid]?.name || fid}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.rows.map((row, i) => (
            <tr key={i} className={i % 2 === 0 ? 'bg-gray-50' : ''}>
              <td className="py-2 px-3 text-gray-400">{i + 1}</td>
              {factorIds.map(fid => (
                <td key={fid} className="py-2 px-3">
                  {levelName(fid, row[fid])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
