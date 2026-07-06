// Chip Window simulator — ported from engine/chip_window_sim.py.
// A betting-based draft-position mechanic: over the final window of the season,
// every team wagers chips each night; the winner takes the opponent's stake, and
// among lottery teams the final chip totals ARE the draft order. Tanking is
// structurally impossible — you can only gain position by winning.
//
// Statistical (not bit-exact) parity with the Python original. The RNG draw
// order is preserved so a given seed is reproducible within this engine.

import { chipsForRank, safePlayoffCount, type LeagueConfig } from './leagues'
import { RNG } from './rng'

export const STATUS_SAFE = 'Safe Playoff'
export const STATUS_PLAYIN = 'Play-In'
export const STATUS_LOTTERY = 'Lottery'
export type CWStatus = typeof STATUS_SAFE | typeof STATUS_PLAYIN | typeof STATUS_LOTTERY

const VALID_STRATEGIES = ['standard', 'aggressive', 'conservative'] as const
export type CWStrategy = (typeof VALID_STRATEGIES)[number]
const PERSONALITIES = ['standard', 'bold', 'cautious', 'volatile'] as const
const PERSONALITY_WEIGHTS = [0.4, 0.2, 0.2, 0.2]
const TIP_TIMES = [
  '7:00 PM ET', '7:30 PM ET', '7:30 PM ET', '8:00 PM ET', '8:00 PM ET',
  '8:30 PM ET', '9:00 PM ET', '9:30 PM ET', '10:00 PM ET', '10:30 PM ET',
  '7:00 PM ET', '7:30 PM ET', '8:00 PM ET', '9:00 PM ET', '10:00 PM ET',
]

const clip = (x: number, lo: number, hi: number): number => Math.max(lo, Math.min(hi, x))
const round1 = (x: number): number => Math.round(x * 10) / 10
const round2 = (x: number): number => Math.round(x * 100) / 100

export interface CWMatchup {
  homeId: number
  awayId: number
  homeName: string
  awayName: string
  homeStatus: CWStatus
  awayStatus: CWStatus
  homeWager: number
  awayWager: number
  pot: number
  homeWon: boolean
  winnerId: number
  homeDouble: boolean
  awayDouble: boolean
  homeChipsBefore: number
  awayChipsBefore: number
  homeChipsAfter: number
  awayChipsAfter: number
  tipTime: string
  narrative: string
  upsetBonus: number
  homeHotStreak: boolean
  awayHotStreak: boolean
  homeFatigue: boolean
  awayFatigue: boolean
  homeRally: boolean
  awayRally: boolean
}

export interface CWTeam {
  id: number
  name: string
  talent: number
  wins60: number
  losses60: number
  status: CWStatus
  inChipPool: boolean
  chipsStart: number
  chipsEnd: number
  chipTrajectory: number[]
  chipWins: number
  chipLosses: number
  doubled: boolean
  doubleNight: number
  finalWins: number
  finalLosses: number
  finalRank: number
  playoff: boolean
  strategy: CWStrategy
  isPickSwapHolder: boolean
  chipDraftRank: number | null
  chipPick: number | null
  chipGapUp: number | null
  chipGapUpTeam: string | null
  chipGapDown: number | null
  chipGapDownTeam: string | null
  tonightOpponent: string | null
  tonightWager: number | null
  tonightOppWager: number | null
  tonightPot: number | null
  tonightDouble: boolean
  opponentWagers: number[]
  biddingPersonality: (typeof PERSONALITIES)[number]
  hasHotStreak: boolean
  hotStreakNights: { start: number; end: number } | null
  hotStreakBoost: number
  fatigueNights: number[]
  rallyMode: boolean
  rallyModeNight: number | null
  totalUpsetBonus: number
  behaviorShift: number
}

export interface CWSeason {
  seasonNum: number
  teams: CWTeam[]
  championId: number
  championName: string
  playoffIds: number[]
  schedule: CWMatchup[][]
}

export interface CWLeaderboardRow {
  id: number
  name: string
  titles: number
  playoffs: number
  avgChips: number
}

export interface CWResult {
  seasons: CWSeason[]
  leaderboard: CWLeaderboardRow[]
  seed: number
  seasonsCount: number
  strategy: CWStrategy
  leagueId: string
  leagueName: string
  numTeams: number
  chipWindowStart: number
  chipWindowLength: number
  gamesPerSeason: number
}

function winProb(talent: number): number {
  return 1.0 / (1.0 + Math.exp(-(talent - 50) / 14))
}

function h2hProb(talentA: number, talentB: number): number {
  const wpA = winProb(talentA)
  const wpB = winProb(talentB)
  const denom = wpA * (1 - wpB) + wpB * (1 - wpA)
  return denom > 0 ? (wpA * (1 - wpB)) / denom : 0.5
}

function simulateGames(talent: number, rng: RNG, gamesBefore: number): [number, number] {
  const wp = winProb(talent)
  let wins = 0
  for (let i = 0; i < gamesBefore; i++) if (rng.random() < wp) wins++
  return [wins, gamesBefore - wins]
}

function pickBet(chips: number, strat: CWStrategy, rng: RNG, personality: string): number {
  const available = Math.max(chips, 10)
  let base: number
  if (strat === 'aggressive') base = available * rng.uniform(0.3, 0.6)
  else if (strat === 'conservative') base = 10 + rng.uniform(0, 10)
  else {
    const t = Math.max(0, Math.min(chips, 300)) / 300
    base = Math.max(10, available * (0.15 + 0.25 * t))
  }
  const noise = rng.gauss(0, 2.0)
  const raw = Math.max(10, Math.min(available, base + noise))
  let mult = 1.0
  if (personality === 'bold') mult = rng.uniform(1.25, 1.5)
  else if (personality === 'cautious') mult = rng.uniform(0.6, 0.8)
  else if (personality === 'volatile') mult = rng.random() < 0.5 ? rng.uniform(1.25, 1.5) : rng.uniform(0.6, 0.8)
  return round2(Math.max(10, Math.min(available, raw * mult)))
}

export interface ChipWindowOpts {
  seasons?: number
  seed?: number | null
  strategy?: string
  league: LeagueConfig
}

export function simulateChipWindowLeague(opts: ChipWindowOpts): CWResult {
  const lg = opts.league
  const seasons = Math.max(1, opts.seasons ?? 10)
  const seed = opts.seed ?? Math.floor(Math.random() * 1_000_000)
  const strategy = (VALID_STRATEGIES as readonly string[]).includes(opts.strategy ?? '') ? (opts.strategy as CWStrategy) : 'standard'
  const rng = new RNG(seed)

  const nTeams = lg.numTeams
  const gamesBeforeWnd = lg.chipWindowStart - 1
  const gamesInWnd = lg.chipWindowLength
  const playoffCount = lg.playoffSpots
  const safeCount = safePlayoffCount(lg)
  const teamNames = lg.teamNames

  const talents = Array.from({ length: nTeams }, () => clip(rng.gauss(50, 10), 18, 76))
  talents.sort((a, b) => b - a)
  const titles = new Array(nTeams).fill(0)
  const playoffApps = new Array(nTeams).fill(0)
  const totalChipsSum = new Array(nTeams).fill(0)

  const seasonSummaries: CWSeason[] = []

  for (let seasonIdx = 0; seasonIdx < seasons; seasonIdx++) {
    // 4a. Build records.
    const teamData: CWTeam[] = []
    for (let i = 0; i < nTeams; i++) {
      const t = clip(talents[i]! + rng.gauss(0, 2.5), 18, 76)
      const [w60, l60] = simulateGames(t, rng, gamesBeforeWnd)
      teamData.push({
        id: i, name: teamNames[i] ?? `Team ${i}`, talent: round1(t),
        wins60: w60, losses60: l60, status: STATUS_LOTTERY, inChipPool: true,
        chipsStart: 0, chipsEnd: 0, chipTrajectory: [], chipWins: 0, chipLosses: 0,
        doubled: false, doubleNight: -1, finalWins: w60, finalLosses: l60, finalRank: 0,
        playoff: false, strategy: 'standard', isPickSwapHolder: false, chipDraftRank: null, chipPick: null,
        chipGapUp: null, chipGapUpTeam: null, chipGapDown: null, chipGapDownTeam: null,
        tonightOpponent: null, tonightWager: null, tonightOppWager: null, tonightPot: null, tonightDouble: false,
        opponentWagers: [], biddingPersonality: 'standard', hasHotStreak: false, hotStreakNights: null,
        hotStreakBoost: 0, fatigueNights: [], rallyMode: false, rallyModeNight: null, totalUpsetBonus: 0, behaviorShift: 0,
      })
    }
    const byId = new Map(teamData.map((t) => [t.id, t]))

    // 4b. Classify status.
    const byWins = [...teamData].sort((a, b) => b.wins60 - a.wins60)
    byWins.forEach((t, rank) => { t.status = rank < safeCount ? STATUS_SAFE : rank < playoffCount ? STATUS_PLAYIN : STATUS_LOTTERY })

    // 4c. Lottery behavior shift.
    const lotterySortAsc = (arr: CWTeam[]): CWTeam[] => [...arr].sort((a, b) => a.wins60 - b.wins60 || b.losses60 - a.losses60 || a.id - b.id)
    const lotteryTeams = lotterySortAsc(teamData.filter((t) => t.status === STATUS_LOTTERY))
    lotteryTeams.forEach((t, rank0) => {
      const [lo, hi] = rank0 < Math.floor(lotteryTeams.length / 2) ? [5, 25] : [5, 7]
      t.behaviorShift = round1(rng.uniform(lo, hi))
    })

    // 4d. Starting chips.
    lotterySortAsc(teamData).forEach((t, rank0) => {
      const start = chipsForRank(rank0, nTeams)
      t.chipsStart = start
      t.chipsEnd = start
    })

    // 4e. Strategy assignment.
    for (const t of teamData) {
      if (t.status === STATUS_PLAYIN) t.strategy = 'aggressive'
      else if (t.status === STATUS_SAFE) { t.isPickSwapHolder = rng.random() < 0.25; t.strategy = 'conservative' }
      else t.strategy = strategy
    }

    // 4f. Bidding personality.
    for (const t of teamData) {
      const r = rng.random()
      let cum = 0
      for (let k = 0; k < PERSONALITIES.length; k++) {
        cum += PERSONALITY_WEIGHTS[k]!
        if (r < cum) { t.biddingPersonality = PERSONALITIES[k]!; break }
      }
    }

    // 4g. Hot streak (lottery + play-in).
    for (const t of teamData.filter((x) => x.status === STATUS_LOTTERY || x.status === STATUS_PLAYIN)) {
      if (rng.random() < 0.2) {
        t.hasHotStreak = true
        const start = rng.randint(0, Math.max(0, gamesInWnd - 5))
        const length = rng.randint(Math.min(5, gamesInWnd), Math.min(8, gamesInWnd))
        const end = Math.min(start + length - 1, gamesInWnd - 1)
        t.hotStreakNights = { start, end }
        t.hotStreakBoost = Math.round(rng.uniform(0.08, 0.15) * 1000) / 1000
      }
    }

    // 4h. Night pairings.
    const ids = Array.from({ length: nTeams }, (_, i) => i)
    const pairCount = Math.floor(nTeams / 2)
    const nightPairings: [number, number][][] = []
    for (let night = 0; night < gamesInWnd; night++) {
      const shuffled = [...ids]
      rng.shuffle(shuffled)
      const pairs: [number, number][] = []
      for (let i = 0; i < pairCount * 2; i += 2) {
        const a = shuffled[i]!
        const b = shuffled[i + 1]!
        const home = rng.random() < 0.5 ? a : b
        pairs.push([home, home === a ? b : a])
      }
      nightPairings.push(pairs)
    }

    // 4i. Double-night plan.
    const doubleNightPlan = new Map<number, number>()
    for (const tid of ids) {
      const homeNights = nightPairings.map((pairs, ni) => (pairs.some(([h]) => h === tid) ? ni : -1)).filter((ni) => ni >= 0)
      if (homeNights.length) doubleNightPlan.set(tid, rng.choice(homeNights))
    }

    // 4j. Fatigue nights (safe teams).
    for (const t of teamData.filter((x) => x.status === STATUS_SAFE)) {
      const k = Math.max(1, Math.round(gamesInWnd * 0.3))
      t.fatigueNights = rng.sample(gamesInWnd, k).sort((a, b) => a - b)
    }

    // 4k. Night-by-night window.
    const chips = new Map(teamData.map((t) => [t.id, t.chipsStart]))
    const dblTracker = new Map(teamData.map((t) => [t.id, false]))
    const trajectories = new Map(teamData.map((t) => [t.id, [] as number[]]))
    const chipWins = new Map(teamData.map((t) => [t.id, 0]))
    const chipLosses = new Map(teamData.map((t) => [t.id, 0]))
    const upsetBonusTotal = new Map(teamData.map((t) => [t.id, 0]))
    const oppWagers = new Map(teamData.map((t) => [t.id, [] as number[]]))
    const fullSchedule: CWMatchup[][] = []
    const lotteryIds = teamData.filter((t) => t.status === STATUS_LOTTERY).map((t) => t.id)

    nightPairings.forEach((pairs, nightIdx) => {
      const runningRanks = new Map<number, number>()
      ;[...lotteryIds].sort((a, b) => chips.get(b)! - chips.get(a)!).forEach((tid, i) => runningRanks.set(tid, i + 1))

      const nightResults: CWMatchup[] = []
      pairs.forEach(([homeId, awayId], slotIdx) => {
        const homeTd = byId.get(homeId)!
        const awayTd = byId.get(awayId)!
        const homeChipsBefore = chips.get(homeId)!
        const awayChipsBefore = chips.get(awayId)!

        const homeDbl = doubleNightPlan.get(homeId) === nightIdx && !dblTracker.get(homeId)
        if (homeDbl) { dblTracker.set(homeId, true); homeTd.doubled = true; homeTd.doubleNight = nightIdx }

        let homeStrat = homeTd.strategy
        let awayStrat = awayTd.strategy
        if (homeTd.isPickSwapHolder && awayTd.status === STATUS_LOTTERY) homeStrat = 'aggressive'
        if (awayTd.isPickSwapHolder && homeTd.status === STATUS_LOTTERY) awayStrat = 'aggressive'
        if (homeTd.rallyMode) homeStrat = 'aggressive'
        if (awayTd.rallyMode) awayStrat = 'aggressive'

        const homeWager = pickBet(chips.get(homeId)!, homeStrat, rng, homeTd.biddingPersonality)
        const awayWager = pickBet(chips.get(awayId)!, awayStrat, rng, awayTd.biddingPersonality)
        const pot = homeWager + awayWager

        const inHot = (td: CWTeam): boolean => td.hasHotStreak && !!td.hotStreakNights && nightIdx >= td.hotStreakNights.start && nightIdx <= td.hotStreakNights.end
        const homeHs = inHot(homeTd)
        const awayHs = inHot(awayTd)
        const homeFatigue = homeTd.fatigueNights.includes(nightIdx)
        const awayFatigue = awayTd.fatigueNights.includes(nightIdx)

        let pHome = h2hProb(homeTd.talent + homeTd.behaviorShift, awayTd.talent + awayTd.behaviorShift)
        if (homeHs) pHome = Math.min(0.95, pHome + homeTd.hotStreakBoost)
        if (awayHs) pHome = Math.max(0.05, pHome - awayTd.hotStreakBoost)
        if (homeTd.rallyMode) pHome = Math.min(0.95, pHome + 0.04)
        if (awayTd.rallyMode) pHome = Math.max(0.05, pHome - 0.04)
        if (homeFatigue) pHome = Math.max(0.05, pHome - 0.1)
        if (awayFatigue) pHome = Math.min(0.95, pHome + 0.1)

        const homeWon = rng.random() < pHome
        const dblMult = homeDbl ? 2.0 : 1.0
        let winnerId: number
        if (homeWon) {
          chips.set(homeId, chips.get(homeId)! + awayWager * dblMult)
          chips.set(awayId, Math.max(10, chips.get(awayId)! - awayWager))
          winnerId = homeId
          chipWins.set(homeId, chipWins.get(homeId)! + 1)
          chipLosses.set(awayId, chipLosses.get(awayId)! + 1)
        } else {
          chips.set(awayId, chips.get(awayId)! + homeWager * dblMult)
          chips.set(homeId, Math.max(10, chips.get(homeId)! - homeWager))
          winnerId = awayId
          chipWins.set(awayId, chipWins.get(awayId)! + 1)
          chipLosses.set(homeId, chipLosses.get(homeId)! + 1)
        }

        const winnerTd = byId.get(winnerId)!
        const loserTd = byId.get(homeWon ? awayId : homeId)!
        const upsetBonus = Math.max(0, loserTd.wins60 - winnerTd.wins60)
        if (upsetBonus > 0) {
          chips.set(winnerId, chips.get(winnerId)! + upsetBonus)
          upsetBonusTotal.set(winnerId, upsetBonusTotal.get(winnerId)! + upsetBonus)
        }
        oppWagers.get(homeId)!.push(round1(awayWager))
        oppWagers.get(awayId)!.push(round1(homeWager))

        const narrative = buildNarrative({
          homeTd, awayTd, homeDbl, homeChips: chips.get(homeId)!, awayChips: chips.get(awayId)!,
          homeWager, awayWager, homeRank: runningRanks.get(homeId), awayRank: runningRanks.get(awayId),
          homeHs, awayHs, homeFatigue, awayFatigue, nightIdx,
        })

        nightResults.push({
          homeId, awayId, homeName: homeTd.name, awayName: awayTd.name, homeStatus: homeTd.status, awayStatus: awayTd.status,
          homeWager, awayWager, pot, homeWon, winnerId, homeDouble: homeDbl, awayDouble: false,
          homeChipsBefore: round1(homeChipsBefore), awayChipsBefore: round1(awayChipsBefore),
          homeChipsAfter: round1(chips.get(homeId)!), awayChipsAfter: round1(chips.get(awayId)!),
          tipTime: TIP_TIMES[slotIdx % TIP_TIMES.length]!, narrative, upsetBonus,
          homeHotStreak: homeHs, awayHotStreak: awayHs, homeFatigue, awayFatigue,
          homeRally: homeTd.rallyMode, awayRally: awayTd.rallyMode,
        })
      })
      fullSchedule.push(nightResults)
      for (const t of teamData) trajectories.get(t.id)!.push(round1(chips.get(t.id)!))

      const nightsRemaining = gamesInWnd - 1 - nightIdx
      const rallyThreshold = Math.max(2, Math.floor(gamesInWnd / 2))
      if (nightsRemaining >= rallyThreshold) {
        for (const t of teamData) {
          if (t.status === STATUS_LOTTERY && !t.rallyMode && chips.get(t.id)! <= 20.0) {
            t.rallyMode = true
            t.rallyModeNight = nightIdx + 1
          }
        }
      }
    })

    // 4m. Finalize team chip data.
    const finalNight = fullSchedule[fullSchedule.length - 1] ?? []
    const tonightByTeam = new Map<number, CWMatchup>()
    for (const mu of finalNight) { tonightByTeam.set(mu.homeId, mu); tonightByTeam.set(mu.awayId, mu) }
    for (const t of teamData) {
      t.chipsEnd = round1(chips.get(t.id)!)
      t.chipTrajectory = trajectories.get(t.id)!
      t.chipWins = chipWins.get(t.id)!
      t.chipLosses = chipLosses.get(t.id)!
      t.totalUpsetBonus = round1(upsetBonusTotal.get(t.id)!)
      t.finalWins = t.wins60 + t.chipWins
      t.finalLosses = t.losses60 + t.chipLosses
      t.opponentWagers = oppWagers.get(t.id)!
      totalChipsSum[t.id] += t.chipsEnd
      const mu = tonightByTeam.get(t.id)
      if (mu) {
        const isHome = mu.homeId === t.id
        t.tonightOpponent = isHome ? mu.awayName : mu.homeName
        t.tonightWager = isHome ? mu.homeWager : mu.awayWager
        t.tonightOppWager = isHome ? mu.awayWager : mu.homeWager
        t.tonightPot = mu.pot
        t.tonightDouble = isHome ? mu.homeDouble : mu.awayDouble
      }
    }

    // 4n. Chip draft rank.
    const lotteryByChips = teamData.filter((t) => t.status === STATUS_LOTTERY).sort((a, b) => b.chipsEnd - a.chipsEnd || a.wins60 - b.wins60 || a.id - b.id)
    lotteryByChips.forEach((t, rank) => {
      t.chipDraftRank = rank + 1
      t.chipPick = rank + 1
      const above = lotteryByChips[rank - 1]
      const below = lotteryByChips[rank + 1]
      if (above) { t.chipGapUp = round1(above.chipsEnd - t.chipsEnd); t.chipGapUpTeam = above.name }
      if (below) { t.chipGapDown = round1(t.chipsEnd - below.chipsEnd); t.chipGapDownTeam = below.name }
    })

    // 4o. Final standings.
    const finalSorted = [...teamData].sort((a, b) => b.finalWins - a.finalWins)
    finalSorted.forEach((t, rank) => {
      t.finalRank = rank + 1
      if (rank < playoffCount) { t.playoff = true; playoffApps[t.id]++ }
    })

    // 4p. Champion (talent-weighted among playoff teams).
    const playoffPool = teamData.filter((t) => t.playoff)
    let championId = playoffPool.length ? playoffPool[0]!.id : teamData[0]!.id
    if (playoffPool.length) {
      const weights = playoffPool.map((t) => Math.max(0.5, t.talent))
      const total = weights.reduce((s, v) => s + v, 0)
      const r = rng.uniform(0, total)
      let cum = 0
      for (let i = 0; i < playoffPool.length; i++) {
        cum += weights[i]!
        if (r <= cum) { championId = playoffPool[i]!.id; break }
      }
    }
    titles[championId]++

    seasonSummaries.push({
      seasonNum: seasonIdx + 1,
      teams: teamData.map((t) => ({ ...t })),
      championId,
      championName: byId.get(championId)?.name ?? `Team ${championId}`,
      playoffIds: teamData.filter((t) => t.playoff).map((t) => t.id),
      schedule: fullSchedule,
    })

    // 4r. Talent evolution.
    for (let i = 0; i < nTeams; i++) talents[i] = clip(talents[i]! + rng.gauss(0, 1.5), 18, 76)
  }

  // Cumulative leaderboard.
  const leaderboard: CWLeaderboardRow[] = []
  for (let i = 0; i < nTeams; i++) {
    leaderboard.push({ id: i, name: teamNames[i] ?? `Team ${i}`, titles: titles[i], playoffs: playoffApps[i], avgChips: round1(totalChipsSum[i] / seasons) })
  }
  leaderboard.sort((a, b) => b.titles - a.titles || b.playoffs - a.playoffs)

  return {
    seasons: seasonSummaries,
    leaderboard,
    seed,
    seasonsCount: seasons,
    strategy,
    leagueId: lg.id,
    leagueName: lg.name,
    numTeams: nTeams,
    chipWindowStart: lg.chipWindowStart,
    chipWindowLength: gamesInWnd,
    gamesPerSeason: gamesBeforeWnd + gamesInWnd,
  }
}

interface NarrativeCtx {
  homeTd: CWTeam
  awayTd: CWTeam
  homeDbl: boolean
  homeChips: number
  awayChips: number
  homeWager: number
  awayWager: number
  homeRank: number | undefined
  awayRank: number | undefined
  homeHs: boolean
  awayHs: boolean
  homeFatigue: boolean
  awayFatigue: boolean
  nightIdx: number
}

function buildNarrative(c: NarrativeCtx): string {
  const { homeTd: h, awayTd: a } = c
  const isLot = (t: CWTeam) => t.status === STATUS_LOTTERY
  if (c.homeDbl) {
    return c.homeRank && c.homeRank > 1
      ? `Double night — winner earns 2× chips · ${h.name} moves to #${c.homeRank - 1} if they win`
      : `Double night — winner earns 2× chips · ${h.name} declared the double`
  }
  if (c.homeFatigue && h.status === STATUS_SAFE) return `[REST] ${h.name} ${isLot(a) ? 'back-to-back fatigue' : 'resting starters'} — playing down to the level tonight`
  if (c.awayFatigue && a.status === STATUS_SAFE) return `[REST] ${a.name} ${isLot(h) ? 'back-to-back fatigue' : 'resting starters'} — playing down to the level tonight`
  if (h.rallyMode && isLot(h)) return `RALLY — ${h.name} nothing to lose — going all-in`
  if (a.rallyMode && isLot(a)) return `RALLY — ${a.name} nothing to lose — going all-in`
  if (c.homeHs) return `HOT — ${h.name} on a surge (+${Math.round(h.hotStreakBoost * 100)}% win prob tonight)`
  if (c.awayHs) return `HOT — ${a.name} on a surge (+${Math.round(a.hotStreakBoost * 100)}% win prob tonight)`
  if (isLot(h) && isLot(a) && c.homeRank && c.awayRank) {
    const gap = Math.abs(c.homeChips - c.awayChips)
    return gap <= 15
      ? `#${c.homeRank} vs #${c.awayRank} — gap is only ${gap.toFixed(0)} chips`
      : `#${c.homeRank} vs #${c.awayRank} — winner leads by ${(gap + Math.max(c.homeWager, c.awayWager)).toFixed(0)}+ chips`
  }
  if (h.isPickSwapHolder && isLot(a)) return `${h.name} hold swap rights — bidding to deny ${a.name} chip gains`
  if (a.isPickSwapHolder && isLot(h)) return `${a.name} hold swap rights — bidding to deny ${h.name} chip gains`
  if (h.status === STATUS_SAFE && isLot(a)) return `${h.name} playoff team — chip stakes for ${a.name} draft position`
  if (a.status === STATUS_SAFE && isLot(h)) return `${a.name} playoff team — chip stakes for ${h.name} draft position`
  if (isLot(h) && c.homeChips <= h.chipsStart + 5) return `${h.name} at floor — nothing to lose`
  if (isLot(a) && c.awayChips <= a.chipsStart + 5) return `${a.name} at floor — nothing to lose`
  if (h.status === STATUS_PLAYIN || a.status === STATUS_PLAYIN) return 'Play-in seeding battle — both teams need the win'
  return `${h.name} vs ${a.name} — chip window game ${c.nightIdx + 1}`
}
