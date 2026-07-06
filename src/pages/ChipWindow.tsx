import { useMemo, useState } from 'react'
import { LEAGUE_LIST, getLeague } from '../engine'
import { simulateChipWindowLeague, STATUS_LOTTERY, STATUS_PLAYIN, type CWResult, type CWTeam } from '../engine/chipWindow'
import { LineChart, Legend, type Series } from '../ui/charts'

const STRATEGIES = ['standard', 'aggressive', 'conservative'] as const
const PALETTE = ['#fe4e00', '#570000', '#e0a800', '#1a659e', '#a83250', '#0d9488', '#8b5cf6', '#d1495b', '#2f855a', '#b45309', '#0ea5e9', '#c026d3']

function chipColor(c: number): string {
  if (c >= 200) return '#e0a800' // gold
  if (c >= 100) return '#fe4e00' // flame
  if (c >= 50) return '#f39c6b' // soft flame
  return 'var(--text-3)'
}
function pickClass(pick: number): string {
  if (pick <= 3) return '#e0a800' // gold — top picks
  if (pick <= 8) return 'var(--brand)' // flame
  return 'var(--text-3)'
}

export function ChipWindow() {
  const [seasonsN, setSeasonsN] = useState(10)
  const [seed, setSeed] = useState('')
  const [strategy, setStrategy] = useState<(typeof STRATEGIES)[number]>('standard')
  const [leagueId, setLeagueId] = useState('nba')
  const [running, setRunning] = useState(false)
  const [data, setData] = useState<CWResult | null>(null)
  const [seasonIdx, setSeasonIdx] = useState(0)
  const [game, setGame] = useState(0) // 0-based night index; default final

  const run = () => {
    setRunning(true)
    setTimeout(() => {
      const seedNum = /^\d+$/.test(seed.trim()) ? Number(seed.trim()) : null
      const r = simulateChipWindowLeague({ seasons: seasonsN, seed: seedNum, strategy, league: getLeague(leagueId) })
      setData(r)
      setSeasonIdx(0)
      setGame(r.chipWindowLength - 1)
      setRunning(false)
    }, 30)
  }

  const season = data?.seasons[seasonIdx]
  const nights = data?.chipWindowLength ?? 22

  const poolTeams = useMemo(() => {
    if (!season) return []
    const pool = season.teams.filter((t) => t.status === STATUS_LOTTERY || t.status === STATUS_PLAYIN)
    const chipsAt = (t: CWTeam) => t.chipTrajectory[game] ?? t.chipsStart
    return [...pool].sort((a, b) => chipsAt(b) - chipsAt(a))
  }, [season, game])

  const chipsAt = (t: CWTeam) => t.chipTrajectory[game] ?? t.chipsStart
  const maxChips = Math.max(120, ...poolTeams.map((t) => Math.max(...t.chipTrajectory, t.chipsStart)))

  const trajSeries: Series[] = useMemo(() => {
    if (!season) return []
    const top = season.teams.filter((t) => t.status !== 'Safe Playoff').sort((a, b) => b.chipsEnd - a.chipsEnd).slice(0, 12)
    return top.map((t, i) => ({ label: t.name, color: PALETTE[i % PALETTE.length]!, values: t.chipTrajectory.slice(0, game + 1) }))
  }, [season, game])

  return (
    <div className="grid">
      <div className="card">
        <div className="card__head"><span className="card__title">Chip window</span></div>
        <div className="card__body">
          <div className="field">
            <label>Seasons — {seasonsN}</label>
            <input type="range" min={1} max={15} step={1} value={seasonsN} onChange={(e) => setSeasonsN(Number(e.target.value))} />
          </div>
          <div className="field">
            <label>Lottery-team strategy</label>
            <div className="chips">
              {STRATEGIES.map((s) => (
                <button key={s} className="chip" data-on={s === strategy} onClick={() => setStrategy(s)} style={{ textTransform: 'capitalize' }}>{s}</button>
              ))}
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
            <label>Seed</label>
            <input type="text" placeholder="blank = random" value={seed} onChange={(e) => setSeed(e.target.value)} />
          </div>
          <button className="btn btn--primary" disabled={running} onClick={run}>{running ? 'Simulating…' : 'Run simulation →'}</button>
        </div>
      </div>

      <div style={{ display: 'grid', gap: 'var(--s5)' }}>
        {!data || !season ? (
          <div className="empty">Run a chip-window simulation to see the standings play out.</div>
        ) : (
          <>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--s4)', alignItems: 'center' }}>
              {data.seasons.length > 1 && (
                <div className="field" style={{ minWidth: 200 }}>
                  <label>Season — {season.seasonNum} of {data.seasons.length} · champ {season.championName}</label>
                  <input type="range" min={0} max={data.seasons.length - 1} value={seasonIdx} onChange={(e) => { setSeasonIdx(Number(e.target.value)); setGame(nights - 1) }} />
                </div>
              )}
              <div className="field" style={{ minWidth: 220, flex: 1 }}>
                <label>Game {game + 1} of {nights} {game === nights - 1 ? '· final standings' : ''}</label>
                <input type="range" min={0} max={nights - 1} value={game} onChange={(e) => setGame(Number(e.target.value))} />
              </div>
            </div>

            <div className="card">
              <div className="card__head"><span className="card__title">Chip standings — {data.leagueName}</span></div>
              <div className="card__body" style={{ paddingTop: 0 }}>
                <table className="std">
                  <thead>
                    <tr>
                      <th>Pick</th>
                      <th>Team</th>
                      <th>Status</th>
                      <th className="mono">Rec (G{data.chipWindowStart - 1})</th>
                      <th className="mono">Chips</th>
                      <th className="mono" style={{ width: 130 }}>—</th>
                    </tr>
                  </thead>
                  <tbody>
                    {poolTeams.map((t, i) => {
                      const c = chipsAt(t)
                      const isLot = t.status === STATUS_LOTTERY
                      return (
                        <tr key={t.id}>
                          <td className="mono">
                            {isLot ? (
                              <span style={{ display: 'inline-grid', placeItems: 'center', width: 22, height: 22, borderRadius: '50%', background: pickClass(i + 1), color: '#fff', fontSize: 11, fontWeight: 700 }}>{i + 1}</span>
                            ) : '—'}
                          </td>
                          <td>{t.name}{t.doubled && t.doubleNight <= game ? <span className="pick"> 2×</span> : null}</td>
                          <td><span style={{ fontSize: 11, color: isLot ? 'var(--brand-ink)' : 'var(--text-3)' }}>{t.status}</span></td>
                          <td className="mono">{t.wins60}-{t.losses60}</td>
                          <td className="mono">{c.toFixed(0)}</td>
                          <td>
                            <div style={{ height: 8, borderRadius: 4, background: 'var(--surface-3)', overflow: 'hidden' }}>
                              <div style={{ height: '100%', width: `${Math.min(100, (c / maxChips) * 100)}%`, background: chipColor(c) }} />
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="card">
              <div className="card__head"><span className="card__title">Chip trajectories</span></div>
              <div className="card__body">
                <LineChart series={trajSeries} yMin={0} yMax={maxChips} refLine={100} refLabel="double @ 100" xLabels={Array.from({ length: game + 1 }, (_, i) => `G${data.chipWindowStart - 1 + i + 1}`)} />
                <Legend items={trajSeries.slice(0, 8).map((s) => ({ label: s.label, color: s.color }))} />
              </div>
            </div>

            <div className="card">
              <div className="card__head"><span className="card__title">Cumulative leaderboard — {data.seasonsCount} seasons</span></div>
              <div className="card__body" style={{ paddingTop: 0 }}>
                <table className="std">
                  <thead>
                    <tr><th>#</th><th>Team</th><th className="mono">Titles</th><th className="mono">Playoffs</th><th className="mono">Avg chips</th></tr>
                  </thead>
                  <tbody>
                    {data.leaderboard.slice(0, 12).map((r, i) => (
                      <tr key={r.id}>
                        <td className="mono">{i + 1}</td>
                        <td>{r.name}</td>
                        <td className="mono">{'★'.repeat(r.titles) || '—'}</td>
                        <td className="mono">{r.playoffs}</td>
                        <td className="mono" style={{ color: r.avgChips >= 100 ? 'var(--success)' : undefined }}>{r.avgChips.toFixed(0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
