// Small inline-SVG chart components, themed via CSS variables so they track
// light/dark. No chart library — keeps the static bundle self-contained.

export interface Series {
  label: string
  color: string
  values: number[]
}

const AXIS = 'var(--text-3)'
const GRID = 'var(--border)'

/** Multi-series line chart with a horizontal grid and x-labels. */
export function LineChart({
  series,
  width = 560,
  height = 240,
  yMin,
  yMax,
  xLabels,
  yTicks = 5,
  refLine,
  refLabel,
}: {
  series: Series[]
  width?: number
  height?: number
  yMin: number
  yMax: number
  xLabels?: string[]
  yTicks?: number
  refLine?: number
  refLabel?: string
}) {
  const padL = 40
  const padB = 26
  const padT = 12
  const padR = 12
  const n = Math.max(1, series[0]?.values.length ?? 1)
  const plotW = width - padL - padR
  const plotH = height - padT - padB
  const x = (i: number) => padL + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW)
  const y = (v: number) => padT + plotH - ((v - yMin) / (yMax - yMin || 1)) * plotH

  const ticks = Array.from({ length: yTicks + 1 }, (_, i) => yMin + ((yMax - yMin) * i) / yTicks)
  const labelEvery = Math.ceil(n / 10)

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" style={{ display: 'block' }}>
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={padL} x2={width - padR} y1={y(t)} y2={y(t)} stroke={GRID} strokeWidth={1} />
          <text x={padL - 6} y={y(t) + 3} textAnchor="end" fontSize={9} fill={AXIS} fontFamily="var(--font-mono)">
            {Number.isInteger(t) ? t : t.toFixed(1)}
          </text>
        </g>
      ))}
      {refLine !== undefined && (
        <g>
          <line x1={padL} x2={width - padR} y1={y(refLine)} y2={y(refLine)} stroke="var(--brand)" strokeWidth={1} strokeDasharray="4 3" opacity={0.7} />
          {refLabel && (
            <text x={width - padR} y={y(refLine) - 4} textAnchor="end" fontSize={9} fill="var(--brand-ink)">
              {refLabel}
            </text>
          )}
        </g>
      )}
      {xLabels &&
        xLabels.map((lbl, i) =>
          i % labelEvery === 0 ? (
            <text key={i} x={x(i)} y={height - 8} textAnchor="middle" fontSize={9} fill={AXIS} fontFamily="var(--font-mono)">
              {lbl}
            </text>
          ) : null,
        )}
      {series.map((s) => (
        <polyline
          key={s.label}
          fill="none"
          stroke={s.color}
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
          points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(' ')}
        />
      ))}
    </svg>
  )
}

/** Grouped vertical bars (one group per x, one bar per series). */
export function GroupedBars({
  series,
  width = 560,
  height = 240,
  yMax,
  xLabels,
  cutIndex,
  cutLabel,
}: {
  series: Series[]
  width?: number
  height?: number
  yMax: number
  xLabels?: string[]
  cutIndex?: number
  cutLabel?: string
}) {
  const padL = 36
  const padB = 26
  const padT = 12
  const padR = 12
  const n = Math.max(1, series[0]?.values.length ?? 1)
  const plotW = width - padL - padR
  const plotH = height - padT - padB
  const groupW = plotW / n
  const barW = Math.max(1, (groupW * 0.7) / series.length)
  const y = (v: number) => padT + plotH - (v / (yMax || 1)) * plotH
  const ticks = Array.from({ length: 5 }, (_, i) => (yMax * i) / 4)
  const labelEvery = Math.ceil(n / 12)

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" style={{ display: 'block' }}>
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={padL} x2={width - padR} y1={y(t)} y2={y(t)} stroke={GRID} strokeWidth={1} />
          <text x={padL - 6} y={y(t) + 3} textAnchor="end" fontSize={9} fill={AXIS} fontFamily="var(--font-mono)">
            {Math.round(t)}
          </text>
        </g>
      ))}
      {cutIndex !== undefined && (
        <g>
          <line x1={padL + cutIndex * groupW} x2={padL + cutIndex * groupW} y1={padT} y2={padT + plotH} stroke="var(--brand)" strokeDasharray="4 3" strokeWidth={1} opacity={0.7} />
          {cutLabel && (
            <text x={padL + cutIndex * groupW + 4} y={padT + 10} fontSize={9} fill="var(--brand-ink)">
              {cutLabel}
            </text>
          )}
        </g>
      )}
      {Array.from({ length: n }, (_, i) =>
        series.map((s, si) => {
          const v = s.values[i] ?? 0
          const bx = padL + i * groupW + groupW * 0.15 + si * barW
          return <rect key={`${i}-${si}`} x={bx} y={y(v)} width={barW} height={padT + plotH - y(v)} fill={s.color} opacity={0.85} rx={1} />
        }),
      )}
      {xLabels &&
        xLabels.map((lbl, i) =>
          i % labelEvery === 0 ? (
            <text key={i} x={padL + i * groupW + groupW / 2} y={height - 8} textAnchor="middle" fontSize={9} fill={AXIS} fontFamily="var(--font-mono)">
              {lbl}
            </text>
          ) : null,
        )}
    </svg>
  )
}

/** Legend row of colored dots + labels. */
export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, fontSize: 12, color: 'var(--text-2)' }}>
      {items.map((it) => (
        <span key={it.label} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: it.color, display: 'inline-block' }} />
          {it.label}
        </span>
      ))}
    </div>
  )
}
