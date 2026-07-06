// Season + multi-season simulation — ported from engine/lottery_sim.py.
import type { LeagueConfig } from './leagues'
import { RNG } from './rng'
import { h2hKey, type DraftConstraints, type LotterySystem, type RunResult, type SeasonResult, type Standing, type Team } from './types'

export function makeConstraints(lg: LeagueConfig): DraftConstraints {
  return {
    top1History: new Map(),
    top3History: new Map(),
    currentYear: 0,
    playoffSpots: lg.playoffSpots,
    numTeams: lg.numTeams,
    gamesPerSeason: lg.gamesPerSeason,
    weeksPerSeason: lg.weeksPerSeason,
    playInSlots: lg.playInSlots,
    lotteryPicks: lg.lotteryPicks,
  }
}

export function defaultTeams(seed: number | null | undefined, lg: LeagueConfig): Team[] {
  const rng = new RNG(seed)
  return lg.teamNames.map((name, i) => {
    let talent = rng.gauss(50, 15)
    talent = Math.max(10, Math.min(90, talent))
    const propensity = rng.betavariate(1.5, 3.0)
    return { id: i, name, trueTalent: talent, tankPropensity: propensity }
  })
}

function winProbability(talentA: number, talentB: number): number {
  return 1.0 / (1.0 + Math.exp(-(talentA - talentB) / 8.0))
}

function awardPoints(points: Map<number, number>, lg: LeagueConfig, winner: number, loser: number, rng: RNG): void {
  if (lg.pointsSystem === 'wins') return
  const isRegulation = rng.random() < lg.regulationWinShare
  if (lg.pointsSystem === '3-2-1-0') {
    points.set(winner, (points.get(winner) ?? 0) + (isRegulation ? 3 : 2))
    if (!isRegulation) points.set(loser, (points.get(loser) ?? 0) + 1)
  } else if (lg.pointsSystem === '2-1-1') {
    points.set(winner, (points.get(winner) ?? 0) + 2)
    if (!isRegulation) points.set(loser, (points.get(loser) ?? 0) + 1)
  }
}

function playoffProbability(teamId: number, standings: Standing[], week: number, weeksPerSeason: number, playoffSpots: number): number {
  const sortedByWins = [...standings].sort((a, b) => b[1] - a[1])
  let rank = 1
  for (let i = 0; i < sortedByWins.length; i++) {
    if (sortedByWins[i]![0] === teamId) {
      rank = i + 1
      break
    }
  }
  const progress = week / weeksPerSeason
  const sharpness = 1.0 + progress * 3.0
  const logit = (playoffSpots - rank + 0.5) * sharpness * 0.4
  return 1.0 / (1.0 + Math.exp(-logit))
}

function effortMultiplier(team: Team, system: LotterySystem, standings: Standing[], history: SeasonResult[], week: number, weeksPerSeason: number, playoffSpots: number): number {
  const playoffP = playoffProbability(team.id, standings, week, weeksPerSeason, playoffSpots)
  const rawIncentive = system.tankIncentive(team.id, standings, history, playoffSpots)
  if (rawIncentive <= 0) return 1.0
  const tankDesire = team.tankPropensity * rawIncentive * (1.0 - playoffP)
  return Math.max(0.3, Math.min(1.0, 1.0 - tankDesire))
}

function isEliminated(teamId: number, standings: Standing[], week: number, gamesPerSeason: number, weeksPerSeason: number, playoffSpots: number): boolean {
  const gamesRemaining = Math.trunc((gamesPerSeason / weeksPerSeason) * (weeksPerSeason - week))
  let currentWins = 0
  for (const [tid, w] of standings) if (tid === teamId) { currentWins = w; break }
  const maxPossible = currentWins + gamesRemaining
  const sortedByWins = [...standings].sort((a, b) => b[1] - a[1])
  const cutoffWins = sortedByWins.length >= playoffSpots ? sortedByWins[playoffSpots - 1]![1] : 0
  return maxPossible < cutoffWins
}

function recordH2H(h2h: Map<string, [number, number]>, winner: number, loser: number): void {
  const key = h2hKey(winner, loser)
  const rec = h2h.get(key) ?? [0, 0]
  if (winner < loser) rec[0] += 1
  else rec[1] += 1
  h2h.set(key, rec)
}

export function simulateSeason(teams: Team[], system: LotterySystem, history: SeasonResult[], rng: RNG, lg: LeagueConfig): { season: SeasonResult; effortLog: number[][] } {
  const wins = new Map<number, number>(teams.map((t) => [t.id, 0]))
  const losses = new Map<number, number>(teams.map((t) => [t.id, 0]))
  let points = new Map<number, number>(teams.map((t) => [t.id, 0]))
  const h2h = new Map<string, [number, number]>()
  const eliminatedWeek = new Map<number, number>()
  const effortLog: number[][] = []
  const byId = new Map(teams.map((t) => [t.id, t]))

  const gamesPerWeek = Math.floor(lg.gamesPerSeason / lg.weeksPerSeason)
  const extraGames = lg.gamesPerSeason % lg.weeksPerSeason

  for (let week = 1; week <= lg.weeksPerSeason; week++) {
    const standings: Standing[] = teams.map((t) => [t.id, wins.get(t.id)!, losses.get(t.id)!])

    const efforts = new Map<number, number>()
    for (const t of teams) efforts.set(t.id, effortMultiplier(t, system, standings, history, week, lg.weeksPerSeason, lg.playoffSpots))
    effortLog.push(teams.map((t) => efforts.get(t.id)!))

    for (const t of teams) {
      if (!eliminatedWeek.has(t.id) && isEliminated(t.id, standings, week, lg.gamesPerSeason, lg.weeksPerSeason, lg.playoffSpots)) {
        eliminatedWeek.set(t.id, week)
      }
    }

    const weekGames = gamesPerWeek + (week <= extraGames ? 1 : 0)
    const teamIds = teams.map((t) => t.id)
    rng.shuffle(teamIds)
    const matchups: [number, number][] = []
    for (let i = 0; i + 1 < teamIds.length; i += 2) matchups.push([teamIds[i]!, teamIds[i + 1]!])
    const rounds = matchups.length ? weekGames : 0

    for (let r = 0; r < rounds; r++) {
      for (const [aId, bId] of matchups) {
        const teamA = byId.get(aId)!
        const teamB = byId.get(bId)!
        const effectiveA = teamA.trueTalent * efforts.get(aId)!
        const effectiveB = teamB.trueTalent * efforts.get(bId)!
        const pA = winProbability(effectiveA, effectiveB)
        if (rng.random() < pA) {
          wins.set(aId, wins.get(aId)! + 1)
          losses.set(bId, losses.get(bId)! + 1)
          awardPoints(points, lg, aId, bId, rng)
          recordH2H(h2h, aId, bId)
        } else {
          wins.set(bId, wins.get(bId)! + 1)
          losses.set(aId, losses.get(aId)! + 1)
          awardPoints(points, lg, bId, aId, rng)
          recordH2H(h2h, bId, aId)
        }
      }
    }
  }

  if (lg.pointsSystem === 'wins') points = new Map(wins)

  const standings: Standing[] = teams
    .map((t): Standing => [t.id, wins.get(t.id)!, losses.get(t.id)!])
    .sort((a, b) => (points.get(b[0]) ?? 0) - (points.get(a[0]) ?? 0))

  return { season: { standings, headToHead: h2h, eliminatedWeek, points }, effortLog }
}

export function simulateRun(system: LotterySystem, seasons: number, seed: number | null | undefined, lg: LeagueConfig): RunResult {
  const rng = new RNG(seed)
  const teams = defaultTeams(seed, lg)
  const byId = new Map(teams.map((t) => [t.id, t]))
  const history: SeasonResult[] = []
  const draftOrders: number[][] = []
  const allEffortLogs: number[][][] = []
  const constraints = makeConstraints(lg)

  for (let year = 0; year < seasons; year++) {
    constraints.currentYear = year
    const { season, effortLog } = simulateSeason(teams, system, history, rng, lg)
    history.push(season)
    allEffortLogs.push(effortLog)

    const draftOrder = system.draftOrder(history, constraints, rng)
    draftOrders.push(draftOrder)

    if (draftOrder.length) {
      const top = byId.get(draftOrder[0]!)
      if (top) top.trueTalent = Math.min(90, top.trueTalent + rng.uniform(3, 8))
    }
    for (const t of teams) {
      const drift = rng.gauss(0, 1.5)
      t.trueTalent = Math.max(10, Math.min(90, t.trueTalent + drift))
    }
  }

  return {
    systemName: system.name,
    seasons: history,
    draftOrders,
    effortLog: allEffortLogs,
    teamIds: teams.map((t) => t.id),
  }
}
