import { useMemo, useState } from 'react'
import { ALL_SYSTEMS, LEAGUE_LIST, getLeague, monteCarlo, type LeagueConfig, type MetricsBundle } from '../engine'
import { GroupedBars, Legend, LineChart, type Series } from '../ui/charts'

const COLORS = ['var(--series-1)', 'var(--series-2)']

interface MetricCard {
  label: string
  value: string
  sub: string
  cls: '' | 'good' | 'bad'
}

function cardsFor(m: MetricsBundle): MetricCard[] {
  const cls = (v: number, good: number, bad: number, lowerBetter = true): '' | 'good' | 'bad' => {
    const g = lowerBetter ? v < good : v > good
    const b = lowerBetter ? v > bad : v < bad
    return g ? 'good' : b ? 'bad' : ''
  }
  return [
    { label: 'Late-season effort', value: m.lateSeasonEffort.toFixed(2), sub: 'final vs early games (1.0 = full)', cls: cls(m.lateSeasonEffort, 0.95, 0.8, false) },
    { label: 'Repeat #1 pick', value: `${(m.repeatTop1Frequency * 100).toFixed(0)}%`, sub: 'same team, #1 within 5 yrs', cls: cls(m.repeatTop1Frequency, 0.1, 0.25) },
    { label: 'Gini · top-5 picks', value: m.giniTop5.toFixed(2), sub: 'pick concentration', cls: cls(m.giniTop5, 0.3, 0.5) },
    { label: 'Tank cycles / season', value: m.tankCycles.toFixed(1), sub: 'teams tanking late', cls: cls(m.tankCycles, 3, 7) },
    { label: 'Competitive balance', value: m.competitiveBalance.toFixed(1), sub: 'σ of wins (lower = tighter)', cls: cls(m.competitiveBalance, 12, 16) },
    { label: 'Avg wins · top-3 picks', value: m.avgWinsTop3Recipients.toFixed(1), sub: 'wins of top-3 recipients', cls: cls(m.avgWinsTop3Recipients, 28, 35) },
  ]
}

function Standings({ m, lg }: { m: MetricsBundle; lg: LeagueConfig }) {
  const rows = useMemo(() => {
    const ids = [...m.avgWinsByTeam.keys()].sort((a, b) => (m.avgWinsByTeam.get(b) ?? 0) - (m.avgWinsByTeam.get(a) ?? 0))
    return ids.map((id) => ({
      id,
      name: lg.teamNames[id] ?? `Team ${id}`,
      wins: m.avgWinsByTeam.get(id) ?? 0,
      pick1: m.pick1ByTeam.get(id) ?? 0,
      top5: (m.pickDistribution.get(id) ?? []).reduce((s, v) => s + v, 0),
    }))
  }, [m, lg])
  return (
    <table className="std">
      <thead>
        <tr>
          <th>#</th>
          <th>Team</th>
          <th className="mono">Avg W</th>
          <th className="mono">#1 Pick%</th>
          <th className="mono">Top-5%</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={r.id} data-cut={i === lg.playoffSpots}>
            <td className="mono">{i + 1}</td>
            <td>{r.name}</td>
            <td className="mono">{r.wins.toFixed(1)}</td>
            <td className="mono pick">{r.pick1 > 0 ? `${r.pick1.toFixed(1)}%` : '—'}</td>
            <td className="mono">{r.top5 > 0 ? `${r.top5.toFixed(0)}%` : '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

interface Result {
  system: string
  league: LeagueConfig
  m: MetricsBundle
}

export function Simulator() {
  const [selected, setSelected] = useState<string[]>([ALL_SYSTEMS[0]!.name])
  const [leagueId, setLeagueId] = useState('nba')
  const [runs, setRuns] = useState(30)
  const [seasons, setSeasons] = useState(15)
  const [seed, setSeed] = useState('')
  const [running, setRunning] = useState(false)
  const [results, setResults] = useState<Result[]>([])

  const lg = getLeague(leagueId)

  const toggleSystem = (name: string) =>
    setSelected((cur) => (cur.includes(name) ? cur.filter((n) => n !== name) : cur.length >= 2 ? [cur[1]!, name] : [...cur, name]))

  const run = () => {
    setRunning(true)
    setTimeout(() => {
      const seedNum = /^\d+$/.test(seed.trim()) ? Number(seed.trim()) : null
      setResults(selected.map((name) => ({ system: name, league: lg, m: monteCarlo(ALL_SYSTEMS.find((s) => s.name === name)!, lg, { runs, seasons, seed: seedNum }) })))
      setRunning(false)
    }, 30)
  }

  const effortSeries: Series[] = results.map((r, i) => ({ label: r.system, color: COLORS[i]!, values: r.m.effortByWeek }))
  const winSeries: Series[] = results.map((r, i) => ({ label: r.system, color: COLORS[i]!, values: r.m.avgWinsByRank }))
  const legend = results.map((r, i) => ({ label: r.system, color: COLORS[i]! }))
  const maxWins = Math.max(1, ...winSeries.flatMap((s) => s.values))

  return (
    <div className="grid">
      <div className="card">
        <div className="card__head"><span className="card__title">Build a run</span></div>
        <div className="card__body">
          <div className="field">
            <label>Systems <span className="hint">— up to two</span></label>
            <div className="sys-list">
              {ALL_SYSTEMS.map((s) => {
                const idx = selected.indexOf(s.name)
                const on = idx >= 0
                return (
                  <div key={s.name} className="sys" data-on={on} onClick={() => toggleSystem(s.name)}>
                    <span className="dot" style={{ background: on ? COLORS[idx] : 'var(--border-strong)' }} />
                    {s.name}
                  </div>
                )
              })}
            </div>
          </div>
          <div className="field">
            <label>League</label>
            <div className="chips">
              {LEAGUE_LIST.map((l) => (
                <button key={l.id} className="chip" data-on={l.id === leagueId} onClick={() => setLeagueId(l.id)}>{l.name}</button>
              ))}
            </div>
          </div>
          <div className="field">
            <label>Monte Carlo runs — {runs}</label>
            <input type="range" min={5} max={200} step={5} value={runs} onChange={(e) => setRuns(Number(e.target.value))} />
          </div>
          <div className="field">
            <label>Seasons per run — {seasons}</label>
            <input type="range" min={3} max={30} step={1} value={seasons} onChange={(e) => setSeasons(Number(e.target.value))} />
          </div>
          <div className="field">
            <label>Seed</label>
            <input type="text" placeholder="blank = random" value={seed} onChange={(e) => setSeed(e.target.value)} />
          </div>
          <button className="btn btn--primary" disabled={running || selected.length === 0} onClick={run}>
            {running ? 'Simulating…' : 'Run simulation →'}
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gap: 'var(--s5)' }}>
        {results.length === 0 ? (
          <div className="empty">Pick a system and run a simulation to see results.</div>
        ) : (
          <>
            {results.map(({ system, m, league }, idx) => (
              <div key={system} style={{ display: 'grid', gap: 'var(--s3)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="dot" style={{ width: 10, height: 10, borderRadius: '50%', background: COLORS[idx], display: 'inline-block' }} />
                  <strong style={{ fontFamily: 'var(--font-display)' }}>{system}</strong>
                  <span style={{ color: 'var(--text-3)', fontSize: 12 }}>· {league.name} · {runs}×{seasons}</span>
                </div>
                <div className="tiles">
                  {cardsFor(m).map((c) => (
                    <div className="tile" key={c.label}>
                      <div className="tile__label">{c.label}</div>
                      <div className={`tile__value ${c.cls}`}>{c.value}</div>
                      <div className="tile__sub">{c.sub}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}

            <div className="card">
              <div className="card__head"><span className="card__title">Team effort over the season — bottom teams</span></div>
              <div className="card__body">
                <LineChart series={effortSeries} yMin={0.3} yMax={1.0} yTicks={7} xLabels={effortSeries[0]?.values.map((_, i) => `W${i + 1}`)} />
                <Legend items={legend} />
              </div>
            </div>

            <div className="card">
              <div className="card__head"><span className="card__title">Win distribution by standings rank</span></div>
              <div className="card__body">
                <GroupedBars series={winSeries} yMax={maxWins} xLabels={winSeries[0]?.values.map((_, i) => `${i + 1}`)} cutIndex={lg.playoffSpots} cutLabel="playoff cut" />
                <Legend items={legend} />
              </div>
            </div>

            {results.map(({ system, m, league }) => (
              <div className="card" key={`std-${system}`}>
                <div className="card__head"><span className="card__title">Simulated standings — {system} · {league.name}</span></div>
                <div className="card__body" style={{ paddingTop: 0 }}>
                  <Standings m={m} lg={league} />
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  )
}
