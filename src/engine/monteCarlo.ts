// Monte Carlo driver — ported from monte_carlo in engine/lottery_sim.py.
// Runs `runs` independent multi-season simulations and averages the metrics.
import type { LeagueConfig } from './leagues'
import { computeMetrics } from './metrics'
import { simulateRun } from './simulate'
import type { LotterySystem, MetricsBundle } from './types'

const round = (x: number, n = 0): number => {
  const f = 10 ** n
  return Math.round(x * f) / f
}
const mean = (a: number[]): number => (a.length ? a.reduce((s, v) => s + v, 0) / a.length : 0)

export interface MonteCarloOpts {
  runs?: number
  seasons?: number
  seed?: number | null
  onProgress?: (done: number, total: number) => void
}

export function monteCarlo(system: LotterySystem, lg: LeagueConfig, opts: MonteCarloOpts = {}): MetricsBundle {
  const runs = opts.runs ?? 100
  const seasons = opts.seasons ?? 15
  const seed = opts.seed ?? null
  const nTeams = lg.numTeams
  const weeksPerSeason = lg.weeksPerSeason

  const all: MetricsBundle[] = []
  for (let runIdx = 0; runIdx < runs; runIdx++) {
    const runSeed = seed !== null ? seed + runIdx : null
    all.push(computeMetrics(simulateRun(system, seasons, runSeed, lg), lg))
    opts.onProgress?.(runIdx + 1, runs)
  }

  const avg = (key: keyof MetricsBundle): number => mean(all.map((m) => m[key] as number))

  const avgEffortByWeek: number[] = []
  for (let w = 0; w < weeksPerSeason; w++) {
    const vals = all.filter((m) => w < m.effortByWeek.length).map((m) => m.effortByWeek[w]!)
    avgEffortByWeek.push(vals.length ? mean(vals) : 1.0)
  }

  const avgPickDist = new Map<number, number[]>()
  for (let i = 0; i < nTeams; i++) {
    const slots: number[] = []
    for (let slotIdx = 0; slotIdx < 5; slotIdx++) {
      slots.push(round(mean(all.map((m) => (m.pickDistribution.get(i) ?? [0, 0, 0, 0, 0])[slotIdx]!)), 2))
    }
    avgPickDist.set(i, slots)
  }

  const avgWinsByRank: number[] = []
  for (let rank = 0; rank < nTeams; rank++) {
    const vals = all.filter((m) => rank < m.avgWinsByRank.length).map((m) => m.avgWinsByRank[rank]!)
    avgWinsByRank.push(vals.length ? round(mean(vals), 1) : 0.0)
  }

  const avgWinsByTeam = new Map<number, number>()
  const avgPointsByTeam = new Map<number, number>()
  const avgPick1ByTeam = new Map<number, number>()
  for (let i = 0; i < nTeams; i++) {
    avgWinsByTeam.set(i, round(mean(all.map((m) => m.avgWinsByTeam.get(i) ?? 0.0)), 1))
    avgPointsByTeam.set(i, round(mean(all.map((m) => m.avgPointsByTeam.get(i) ?? 0.0)), 1))
    avgPick1ByTeam.set(i, round(mean(all.map((m) => m.pick1ByTeam.get(i) ?? 0.0)), 2))
  }

  return {
    systemName: system.name,
    lateSeasonEffort: round(avg('lateSeasonEffort'), 4),
    repeatTop1Frequency: round(avg('repeatTop1Frequency'), 4),
    giniTop5: round(avg('giniTop5'), 4),
    tankCycles: round(avg('tankCycles'), 2),
    competitiveBalance: round(avg('competitiveBalance'), 2),
    avgWinsTop3Recipients: round(avg('avgWinsTop3Recipients'), 2),
    pickDistribution: avgPickDist,
    effortByWeek: avgEffortByWeek.map((e) => round(e, 4)),
    avgWinsByRank,
    avgWinsByTeam,
    avgPointsByTeam,
    pick1ByTeam: avgPick1ByTeam,
  }
}
