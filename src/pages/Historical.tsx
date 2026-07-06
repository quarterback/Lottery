import { useState } from 'react'
import { ALL_SYSTEMS } from '../engine'
import { runHistoricalLottery, type HistoricalReport } from '../engine/historical'
import { HISTORICAL_SEASONS, SEASON_KEYS } from '../data/historicalSeasons'

const COLORS = ['var(--series-1)', 'var(--series-2)']
// Systems that draw a weighted lottery (the historical proxy is meaningful for these).
const LOTTERY_SYSTEMS = ['Current NBA', 'Flat Bottom', 'Play-In Boost', 'UEFA Coefficient', 'RCL', 'Pure Inversion', 'Pre-2019 Legacy NBA', 'Equal Odds', 'Top-4 Only Lottery', 'Current NHL', 'Current MLB']

function deltaClass(d: number | null): string {
  if (d === null) return ''
  if (Math.abs(d) <= 1) return ''
  return d > 0 ? 'bad' : 'good' // actual worse (later pick) = red; better = green
}

export function Historical() {
  const [seasonKey, setSeasonKey] = useState(SEASON_KEYS[SEASON_KEYS.length - 1] ?? '2024-25')
  const [selected, setSelected] = useState<string[]>(['Current NBA'])
  const [nRuns, setNRuns] = useState(500)
  const [running, setRunning] = useState(false)
  const [reports, setReports] = useState<HistoricalReport[]>([])

  const season = HISTORICAL_SEASONS[seasonKey]!
  const toggle = (name: string) => setSelected((cur) => (cur.includes(name) ? cur.filter((n) => n !== name) : cur.length >= 2 ? [cur[1]!, name] : [...cur, name]))

  const run = () => {
    setRunning(true)
    setTimeout(() => {
      setReports(selected.map((name) => runHistoricalLottery(season, ALL_SYSTEMS.find((s) => s.name === name)!, nRuns)))
      setRunning(false)
    }, 30)
  }

  return (
    <div className="grid">
      <div className="card">
        <div className="card__head"><span className="card__title">Historical season</span></div>
        <div className="card__body">
          <div className="field">
            <label>Season</label>
            <select value={seasonKey} onChange={(e) => setSeasonKey(e.target.value)} style={{ padding: '8px 10px', borderRadius: 'var(--r-sm)', border: '1px solid var(--border-strong)', background: 'var(--surface-2)', color: 'var(--text)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
              {SEASON_KEYS.map((k) => (<option key={k} value={k}>{k}{HISTORICAL_SEASONS[k]!.seasonPending ? ' · pending' : ''}</option>))}
            </select>
          </div>
          <div className="field">
            <label>Systems <span className="hint">— up to two</span></label>
            <div className="sys-list">
              {ALL_SYSTEMS.filter((s) => LOTTERY_SYSTEMS.includes(s.name)).map((s) => {
                const idx = selected.indexOf(s.name)
                const on = idx >= 0
                return (
                  <div key={s.name} className="sys" data-on={on} onClick={() => toggle(s.name)}>
                    <span className="dot" style={{ background: on ? COLORS[idx] : 'var(--border-strong)' }} />
                    {s.name}
                  </div>
                )
              })}
            </div>
          </div>
          <div className="field">
            <label>Simulated lotteries — {nRuns}</label>
            <input type="range" min={100} max={2000} step={100} value={nRuns} onChange={(e) => setNRuns(Number(e.target.value))} />
          </div>
          <button className="btn btn--primary" disabled={running || selected.length === 0} onClick={run}>{running ? 'Analyzing…' : 'Analyze season →'}</button>
        </div>
      </div>

      <div style={{ display: 'grid', gap: 'var(--s5)' }}>
        <div className="card">
          <div className="card__head"><span className="card__title">{seasonKey} · {season.seasonPending ? 'lottery pending' : `#1 pick: ${season.lotteryPick1}`}</span></div>
          <div className="card__body"><p style={{ margin: 0, color: 'var(--text-2)', fontSize: 14 }}>{season.context}</p></div>
        </div>

        {reports.length === 0 ? (
          <div className="empty">Pick a system and analyze the season to see simulated pick odds vs the actual result.</div>
        ) : (
          reports.map((rep, ridx) => (
            <div className="card" key={rep.systemName}>
              <div className="card__head">
                <span className="card__title">
                  <span className="dot" style={{ width: 8, height: 8, borderRadius: '50%', background: COLORS[ridx], display: 'inline-block', marginRight: 6 }} />
                  {rep.systemName} — simulated pick odds{season.seasonPending ? '' : ' vs actual'}
                </span>
              </div>
              <div className="card__body" style={{ paddingTop: 0 }}>
                <table className="std">
                  <thead>
                    <tr>
                      <th>Seed</th>
                      <th>Team</th>
                      <th className="mono">W-L</th>
                      <th className="mono">Sim pick</th>
                      {!season.seasonPending && <th className="mono">Actual</th>}
                      {!season.seasonPending && <th className="mono">Δ</th>}
                      <th className="mono">Pick 1%</th>
                      <th className="mono">Top-4%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rep.rows.map((r) => (
                      <tr key={r.name}>
                        <td className="mono">{r.seed}</td>
                        <td>{r.name}</td>
                        <td className="mono">{r.wins}-{r.losses}</td>
                        <td className="mono">#{r.simPick}</td>
                        {!season.seasonPending && <td className="mono">{r.actualPick ? `#${r.actualPick}` : '—'}</td>}
                        {!season.seasonPending && <td className={`mono ${deltaClass(r.delta)}`}>{r.delta === null ? '—' : r.delta === 0 ? '—' : r.delta > 0 ? `▼${r.delta}` : `▲${-r.delta}`}</td>}
                        <td className="mono pick">{r.pick1 >= 0.1 ? `${r.pick1.toFixed(1)}%` : '—'}</td>
                        <td className="mono">{r.top4 >= 0.1 ? `${r.top4.toFixed(0)}%` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
