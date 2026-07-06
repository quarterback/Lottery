// Metrics — ported from compute_metrics / _gini in engine/lottery_sim.py.
import type { LeagueConfig } from './leagues'
import type { MetricsBundle, RunResult, SeasonResult } from './types'

const round = (x: number, n = 0): number => {
  const f = 10 ** n
  return Math.round(x * f) / f
}
const mean = (a: number[]): number => (a.length ? a.reduce((s, v) => s + v, 0) / a.length : 0)

export function gini(values: number[]): number {
  const total = values.reduce((s, v) => s + v, 0)
  if (!values.length || total === 0) return 0.0
  const sorted = [...values].sort((a, b) => a - b)
  const n = sorted.length
  let height = 0.0
  let area = 0.0
  for (const v of sorted) {
    height += v
    area += height - v / 2.0
  }
  const fairArea = (height * n) / 2.0
  return fairArea > 0 ? (fairArea - area) / fairArea : 0.0
}

/** Bottom-N team ids by wins ascending (stable), matching the metric code. */
function bottomIds(season: SeasonResult, nTeams: number): Set<number> {
  const bottomN = Math.max(2, Math.floor(nTeams / 5))
  const sorted = [...season.standings].sort((a, b) => a[1] - b[1])
  return new Set(sorted.slice(0, bottomN).map((t) => t[0]))
}

export function computeMetrics(run: RunResult, lg: LeagueConfig): MetricsBundle {
  const { seasons, draftOrders, teamIds } = run
  const nTeams = teamIds.length
  const weeksPerSeason = lg.weeksPerSeason

  // Late-season effort (bottom teams): last ~portion vs first ~portion.
  const lateEffortVals: number[] = []
  const earlyEffortVals: number[] = []
  run.effortLog.forEach((effortLog, sIdx) => {
    const bottom = bottomIds(seasons[sIdx]!, nTeams)
    const lateCutoff = Math.max(1, weeksPerSeason - 7)
    const earlyCutoff = Math.max(1, weeksPerSeason - 12)
    effortLog.forEach((weekEfforts, weekIdx) => {
      weekEfforts.forEach((eff, tIdx) => {
        if (!bottom.has(teamIds[tIdx]!)) return
        const weekNum = weekIdx + 1
        if (weekNum >= lateCutoff) lateEffortVals.push(eff)
        else if (weekNum <= earlyCutoff) earlyEffortVals.push(eff)
      })
    })
  })
  const lateAvg = lateEffortVals.length ? mean(lateEffortVals) : 0.5
  const earlyAvg = earlyEffortVals.length ? mean(earlyEffortVals) : 0.5
  const lateSeasonEffort = earlyAvg > 0 ? lateAvg / earlyAvg : 1.0

  // Repeat #1 pick within 5 years.
  const top1ByYear = draftOrders.filter((o) => o.length).map((o) => o[0]!)
  let repeatCount = 0
  for (let i = 0; i < top1ByYear.length; i++) {
    for (let j = Math.max(0, i - 4); j < i; j++) {
      if (top1ByYear[j] === top1ByYear[i]) {
        repeatCount++
        break
      }
    }
  }
  const repeatFreq = top1ByYear.length ? repeatCount / top1ByYear.length : 0.0

  // Gini of top-5 pick distribution.
  const top5Counts = new Map<number, number>(teamIds.map((t) => [t, 0]))
  for (const order of draftOrders) for (const pick of order.slice(0, 5)) if (top5Counts.has(pick)) top5Counts.set(pick, top5Counts.get(pick)! + 1)
  const giniVal = gini([...top5Counts.values()])

  // Per-slot pick counts (slots 1-5).
  const pickCountsPerSlot = new Map<number, number[]>(teamIds.map((t) => [t, [0, 0, 0, 0, 0]]))
  for (const order of draftOrders) {
    for (let slotIdx = 0; slotIdx < Math.min(5, order.length); slotIdx++) {
      const arr = pickCountsPerSlot.get(order[slotIdx]!)
      if (arr) arr[slotIdx]! += 1
    }
  }

  // Tank cycles: teams tanking in the last 8 weeks.
  const tankThreshold = 0.7
  const tankCyclesPerSeason = run.effortLog.map((effortLog) => {
    const tanking = new Set<number>()
    for (const weekEfforts of effortLog.slice(-8)) weekEfforts.forEach((eff, tIdx) => { if (eff < tankThreshold) tanking.add(tIdx) })
    return tanking.size
  })
  const avgTankCycles = mean(tankCyclesPerSeason)

  // Competitive balance: avg stddev of wins.
  const winStddevs: number[] = []
  for (const season of seasons) {
    const winsList = season.standings.map((s) => s[1])
    if (winsList.length > 1) {
      const m = mean(winsList)
      const variance = mean(winsList.map((w) => (w - m) ** 2))
      winStddevs.push(Math.sqrt(variance))
    }
  }
  const compBalance = mean(winStddevs)

  // Avg wins of top-3 pick recipients.
  const top3Wins: number[] = []
  draftOrders.forEach((order, sIdx) => {
    const season = seasons[sIdx]!
    for (const pick of order.slice(0, 3)) {
      for (const [tid, wins] of season.standings) if (tid === pick) { top3Wins.push(wins); break }
    }
  })
  const avgTop3Wins = mean(top3Wins)

  // Per-slot pick distribution (% of seasons).
  const totalSeasonsSlots = Math.max(draftOrders.length, 1)
  const pickDist = new Map<number, number[]>()
  for (const tid of teamIds) pickDist.set(tid, pickCountsPerSlot.get(tid)!.map((c) => round((c / totalSeasonsSlots) * 100, 2)))

  // Effort by week (bottom teams).
  const effortByWeek: number[] = []
  for (let weekIdx = 0; weekIdx < weeksPerSeason; weekIdx++) {
    const weekEffs: number[] = []
    run.effortLog.forEach((effortLog, s2Idx) => {
      if (weekIdx < effortLog.length) {
        const b6 = bottomIds(seasons[s2Idx]!, nTeams)
        effortLog[weekIdx]!.forEach((eff, tIdx) => { if (b6.has(teamIds[tIdx]!)) weekEffs.push(eff) })
      }
    })
    effortByWeek.push(weekEffs.length ? mean(weekEffs) : 1.0)
  }

  // Avg wins by standings rank (best to worst).
  const rankWins: number[][] = Array.from({ length: nTeams }, () => [])
  for (const season of seasons) {
    const sortedWins = season.standings.map((s) => s[1]).sort((a, b) => b - a)
    sortedWins.forEach((w, rank) => rankWins[rank]!.push(w))
  }
  const avgWinsByRank = rankWins.map((r) => (r.length ? round(mean(r), 1) : 0.0))

  // Avg wins / points per team.
  const avgWinsByTeam = new Map<number, number>()
  const avgPointsByTeam = new Map<number, number>()
  for (const tid of teamIds) {
    const winsList: number[] = []
    for (const season of seasons) for (const [id, w] of season.standings) if (id === tid) winsList.push(w)
    avgWinsByTeam.set(tid, winsList.length ? round(mean(winsList), 1) : 0.0)
    const ptsList = seasons.filter((s) => s.points.size).map((s) => s.points.get(tid) ?? 0)
    avgPointsByTeam.set(tid, ptsList.length ? round(mean(ptsList), 1) : 0.0)
  }

  // #1 pick distribution per team.
  const pick1Counts = new Map<number, number>(teamIds.map((t) => [t, 0]))
  for (const order of draftOrders) if (order.length) pick1Counts.set(order[0]!, (pick1Counts.get(order[0]!) ?? 0) + 1)
  const totalSeasonsN = Math.max(draftOrders.length, 1)
  const pick1ByTeam = new Map<number, number>()
  for (const tid of teamIds) pick1ByTeam.set(tid, round(((pick1Counts.get(tid) ?? 0) / totalSeasonsN) * 100, 2))

  return {
    systemName: run.systemName,
    lateSeasonEffort: round(lateSeasonEffort, 4),
    repeatTop1Frequency: round(repeatFreq, 4),
    giniTop5: round(giniVal, 4),
    tankCycles: round(avgTankCycles, 2),
    competitiveBalance: round(compBalance, 2),
    avgWinsTop3Recipients: round(avgTop3Wins, 2),
    pickDistribution: pickDist,
    effortByWeek: effortByWeek.map((e) => round(e, 4)),
    avgWinsByRank,
    avgWinsByTeam,
    avgPointsByTeam,
    pick1ByTeam,
  }
}
