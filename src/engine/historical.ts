// Historical-season lottery proxy — ported from _run_historical_lottery /
// _make_historical_season_result in web/router.py. Given a real season's
// lottery standings, runs a chosen system's draft_order many times to get the
// pick-probability distribution, and compares it to the actual lottery result.
import { NBA_CONFIG } from './leagues'
import { RNG } from './rng'
import { makeConstraints } from './simulate'
import type { LotterySystem, SeasonResult, Standing } from './types'
import type { HistoricalSeason } from '../data/historicalSeasons'

const PLAYOFF_TEAMS = 16
const LOTTERY_N = 14

function makeHistoricalSeason(season: HistoricalSeason): { result: SeasonResult; idToName: Map<number, string> } {
  const idToName = new Map<number, string>()
  const standings: Standing[] = []
  // Lottery teams get ids 0..13 (worst record first, as stored).
  season.lotteryTeams.forEach(([name, w, l], i) => {
    standings.push([i, w, l])
    idToName.set(i, name)
  })
  // 16 fake playoff teams (ids 14..29) with high win totals so they rank above.
  for (let k = 0; k < PLAYOFF_TEAMS; k++) {
    const id = LOTTERY_N + k
    const wins = 75 - k
    standings.push([id, wins, 82 - wins])
    idToName.set(id, `Playoff ${k + 1}`)
  }
  standings.sort((a, b) => b[1] - a[1])
  return { result: { standings, headToHead: new Map(), eliminatedWeek: new Map(), points: new Map() }, idToName }
}

export interface HistoricalRow {
  name: string
  wins: number
  losses: number
  seed: number // 1 = worst record
  simPick: number // most-likely pick
  pick1: number // % at pick 1
  top4: number // % in top 4
  dist: number[] // % at picks 1..4 (for mini-bars)
  actualPick: number | null
  delta: number | null // actual - sim
}

export interface HistoricalReport {
  systemName: string
  rows: HistoricalRow[]
}

function actualOrder(season: HistoricalSeason): string[] {
  const rest = season.lotteryTeams.map((t) => t[0]).filter((n) => !season.lotteryTop4.includes(n))
  return [...season.lotteryTop4, ...rest]
}

export function runHistoricalLottery(season: HistoricalSeason, system: LotterySystem, nRuns: number): HistoricalReport {
  const { result } = makeHistoricalSeason(season)
  const rng = new RNG(42)
  const pickCounts = new Map<number, number[]>()
  for (let id = 0; id < LOTTERY_N; id++) pickCounts.set(id, new Array(LOTTERY_N).fill(0))

  for (let r = 0; r < nRuns; r++) {
    const constraints = makeConstraints(NBA_CONFIG) // fresh each run — independent draws
    const order = system.draftOrder([result], constraints, rng)
    order.forEach((id, pick) => {
      const arr = pickCounts.get(id)
      if (arr && pick < LOTTERY_N) arr[pick]! += 1
    })
  }

  const order = season.seasonPending ? [] : actualOrder(season)
  const actualPickOf = (name: string): number | null => {
    if (season.seasonPending) return null
    const idx = order.indexOf(name)
    return idx >= 0 ? idx + 1 : null
  }

  const rows: HistoricalRow[] = []
  for (let id = 0; id < season.lotteryTeams.length && id < LOTTERY_N; id++) {
    const [name, wins, losses] = season.lotteryTeams[id]!
    const counts = pickCounts.get(id)!
    const pct = counts.map((c) => (c / nRuns) * 100)
    let simPick = 1
    let best = -1
    pct.forEach((p, i) => { if (p > best) { best = p; simPick = i + 1 } })
    const actualPick = actualPickOf(name)
    rows.push({
      name,
      wins,
      losses,
      seed: id + 1,
      simPick,
      pick1: pct[0]!,
      top4: pct.slice(0, 4).reduce((s, v) => s + v, 0),
      dist: pct.slice(0, 4),
      actualPick,
      delta: actualPick !== null ? actualPick - simPick : null,
    })
  }
  rows.sort((a, b) => a.simPick - b.simPick)
  return { systemName: system.name, rows }
}
