import type { CoverageCell, Factor } from '../types'

interface Props {
    cells: CoverageCell[]
    factors: Factor[]
    totalCombinations: number
    testedCombinations: number
}

function levelName(factors: Factor[], factorId: string, levelId: string): string {
    const f = factors.find(f => f.id === factorId)
    const l = f?.levels.find(l => l.id === levelId)
    return l?.name ?? levelId
}

function cellColor(cell: CoverageCell): string {
    if (cell.is_excluded) return 'bg-gray-200 text-gray-400'
    if (cell.is_tested) return 'bg-green-500 text-white'
    if (cell.is_discriminative_for.length > 0) return 'bg-blue-100 text-blue-800 border border-blue-300'
    return 'bg-white text-gray-500 border border-gray-200'
}

function cellTitle(cell: CoverageCell, factors: Factor[]): string {
    const combo = Object.entries(cell.combination)
        .map(([fid, lid]) => `${factors.find(f => f.id === fid)?.name ?? fid}=${levelName(factors, fid, lid)}`)
        .join(', ')
    if (cell.is_excluded) return `${combo}\nExcluded: ${cell.exclusion_reason ?? ''}`
    if (cell.is_tested) return `${combo}\n✓ Tested`
    if (cell.is_discriminative_for.length > 0)
        return `${combo}\nDiscriminates: ${cell.is_discriminative_for.join(', ')}`
    return `${combo}\nUntested`
}

export default function CoverageMap({ cells, factors, totalCombinations, testedCombinations }: Props) {
    if (!cells.length) return null

    const discriminativeUntested = cells.filter(c => !c.is_tested && !c.is_excluded && c.is_discriminative_for.length > 0)
    const coveragePct = totalCombinations > 0 ? Math.round((testedCombinations / totalCombinations) * 100) : 0

    return (
        <div className="bg-white border rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold">Coverage Map</h2>
                <span className="text-xs text-gray-500">
                    {testedCombinations}/{totalCombinations} tested ({coveragePct}%)
                </span>
            </div>

            {/* Legend */}
            <div className="flex gap-4 text-xs">
                <span className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded bg-green-500 inline-block" /> Tested
                </span>
                <span className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded bg-blue-100 border border-blue-300 inline-block" /> Discriminative
                </span>
                <span className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded bg-white border border-gray-200 inline-block" /> Untested
                </span>
                <span className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded bg-gray-200 inline-block" /> Excluded
                </span>
            </div>

            {/* Grid */}
            <div className="flex flex-wrap gap-1">
                {cells.map((cell, i) => (
                    <div
                        key={i}
                        title={cellTitle(cell, factors)}
                        className={`w-6 h-6 rounded text-xs flex items-center justify-center cursor-default ${cellColor(cell)}`}
                    >
                        {cell.is_discriminative_for.length > 0 && !cell.is_tested && !cell.is_excluded
                            ? cell.is_discriminative_for.length
                            : ''}
                    </div>
                ))}
            </div>

            {discriminativeUntested.length > 0 && (
                <p className="text-xs text-blue-700">
                    {discriminativeUntested.length} untested combinations can discriminate between hypotheses.
                </p>
            )}
        </div>
    )
}
