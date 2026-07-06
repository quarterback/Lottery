// The lottery systems — ported from engine/lottery_sim.py.
// Each system implements LotterySystem: a draftOrder() that turns the latest
// season's standings into a pick order, and a tankIncentive() that tells the
// season sim how much losing helps a given team's lottery position.
//
// Ported for statistical (not bit-exact) parity: the algorithms, odds tables,
// thresholds, stable-sort semantics and dict-insertion-order draws are faithful;
// the RNG stream is a mulberry32 port of Python's random surface.

import type { RNG } from './rng'
import { h2hKey, type DraftConstraints, type LotterySystem, type SeasonResult, type Standing } from './types'

const LOTTERY_TEAMS_FALLBACK = 14

// ── Shared helpers ──────────────────────────────────────────────────────────

/** Ranking value for a team: league points if tracked, else wins. */
function standingsMetric(season: SeasonResult, teamId: number): number {
  if (season.points.size > 0) return season.points.get(teamId) ?? 0
  for (const [tid, w] of season.standings) if (tid === teamId) return w
  return 0
}

/** Lottery teams sorted worst-to-best (worst record first). Stable. */
function nonPlayoffTeams(season: SeasonResult, numPlayoff: number): Standing[] {
  const sorted = [...season.standings].sort(
    (a, b) => standingsMetric(season, a[0]) - standingsMetric(season, b[0]),
  )
  const nLottery = Math.max(1, sorted.length - numPlayoff)
  return sorted.slice(0, nLottery)
}

/** Lottery rank of teamId (1 = worst record, n = best non-playoff). */
function rankByWinsAsc(season: SeasonResult, teamId: number, playoffSpots: number): number {
  const lottery = nonPlayoffTeams(season, playoffSpots)
  for (let i = 0; i < lottery.length; i++) if (lottery[i]![0] === teamId) return i + 1
  return lottery.length > 0 ? lottery.length : LOTTERY_TEAMS_FALLBACK
}

/** Scale a fixed odds array to n teams (truncate, or pad with the last value). */
function adaptOdds(odds: number[], n: number): number[] {
  if (n <= odds.length) return odds.slice(0, n)
  return [...odds, ...Array(n - odds.length).fill(odds[odds.length - 1]!)]
}

/** Weighted sampling without replacement; iterates weights in insertion order. */
export function weightedLotteryDraw(weights: Map<number, number>, numPicks: number, rng: RNG): number[] {
  const remaining = new Map(weights)
  const order: number[] = []
  for (let p = 0; p < numPicks; p++) {
    if (remaining.size === 0) break
    const ids = [...remaining.keys()]
    const w = ids.map((i) => remaining.get(i)!)
    const total = w.reduce((a, b) => a + b, 0)
    let chosen: number
    if (total <= 0) {
      chosen = rng.choice(ids)
    } else {
      const r = rng.uniform(0, total)
      let cumulative = 0
      chosen = ids[ids.length - 1]!
      for (let k = 0; k < ids.length; k++) {
        cumulative += w[k]!
        if (r <= cumulative) {
          chosen = ids[k]!
          break
        }
      }
    }
    order.push(chosen)
    remaining.delete(chosen)
  }
  return order
}

/** The common tail: picks first, then remaining lottery teams by wins ascending. */
function standardTail(lottery: Standing[], lotteryPicks: number[]): number[] {
  const picked = new Set(lotteryPicks)
  const winsMap = new Map(lottery.map((t) => [t[0], t[1]]))
  const remaining = lottery.filter((t) => !picked.has(t[0])).map((t) => t[0])
  remaining.sort((a, b) => winsMap.get(a)! - winsMap.get(b)!)
  return [...lotteryPicks, ...remaining]
}

function oddsWeights(lottery: Standing[], odds: number[]): Map<number, number> {
  const adapted = adaptOdds(odds, lottery.length)
  const weights = new Map<number, number>()
  lottery.forEach((t, i) => weights.set(t[0], adapted[i]!))
  return weights
}

// ── Odds tables ─────────────────────────────────────────────────────────────

export const NBA_ODDS = [14.0, 14.0, 14.0, 12.5, 10.5, 9.0, 7.5, 6.0, 4.5, 3.0, 2.0, 1.5, 1.0, 0.5]
const LEGACY_NBA_ODDS = [25.0, 19.9, 15.6, 11.9, 8.8, 6.3, 4.3, 2.8, 1.7, 1.1, 0.8, 0.7, 0.6, 0.5]
const LEGACY_LOTTERY_PICKS = 3
const NHL_LOTTERY_ODDS = [18.5, 13.5, 11.5, 9.5, 8.5, 7.5, 6.5, 6.0, 5.0, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0, 0.5]
const CURRENT_NHL_LOTTERY_PICKS = 2
const MLB_LOTTERY_ODDS = [16.5, 16.5, 13.0, 10.0, 7.5, 5.5, 5.0, 4.5, 4.0, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0, 1.0, 0.5, 0.5]
const CURRENT_MLB_LOTTERY_PICKS = 6

const last = <T,>(a: T[]): T => a[a.length - 1]!

// ── Coefficient helpers (UEFA / RCL) ────────────────────────────────────────

function h2hDiff(season: SeasonResult, teamId: number, otherId: number): number {
  const key = h2hKey(teamId, otherId)
  const rec = season.headToHead.get(key)
  if (!rec) return 0
  const [loW, hiW] = rec
  const teamWins = teamId < otherId ? loW : hiW
  const otherWins = teamId < otherId ? hiW : loW
  return teamWins - otherWins
}

function uefaCoefficient(teamId: number, history: SeasonResult[], playoffSpots: number): number {
  const scores: number[] = []
  for (const season of history.slice(-3)) {
    const lottery = nonPlayoffTeams(season, playoffSpots)
    const lotteryIds = lottery.map((t) => t[0])
    if (!lotteryIds.includes(teamId)) {
      scores.push(10.0)
      continue
    }
    const rank = rankByWinsAsc(season, teamId, playoffSpots)
    const base = lottery.length + 1 - rank
    let diff = 0
    for (const otherId of lotteryIds) if (otherId !== teamId) diff += h2hDiff(season, teamId, otherId)
    scores.push(base + diff * 0.1)
  }
  const weights3 = [0.5, 0.3, 0.2]
  const weightsUsed = weights3.slice(-scores.length)
  const totalWeight = weightsUsed.reduce((a, b) => a + b, 0)
  const weighted = totalWeight > 0 ? scores.reduce((s, v, i) => s + v * weightsUsed[i]!, 0) / totalWeight : 5.0
  return Math.max(0.5, weighted)
}

function rclCoefficient(teamId: number, history: SeasonResult[], playoffSpots: number): number {
  const scores: number[] = []
  for (const season of history.slice(-3)) {
    const lottery = nonPlayoffTeams(season, playoffSpots)
    const lotteryIds = lottery.map((t) => t[0])
    if (!lotteryIds.includes(teamId)) {
      scores.push(0.0)
      continue
    }
    const rank = rankByWinsAsc(season, teamId, playoffSpots)
    const base = lottery.length + 1 - rank
    let diff = 0
    for (const otherId of lotteryIds) if (otherId !== teamId) diff += h2hDiff(season, teamId, otherId)
    scores.push(base + diff * 0.05)
  }
  if (scores.length === 0) return 5.0
  const weights3 = [0.5, 0.3, 0.2]
  const weightsUsed = weights3.slice(-scores.length)
  const totalWeight = weightsUsed.reduce((a, b) => a + b, 0)
  return Math.max(0.1, scores.reduce((s, v, i) => s + v * weightsUsed[i]!, 0) / totalWeight)
}

function rclApplyCaps(weights: Map<number, number>, c: DraftConstraints): [Map<number, number>, Map<number, number>] {
  const top1: Map<number, number> = new Map()
  const top3: Map<number, number> = new Map()
  for (const [teamId, w] of weights) {
    const recentTop1 = (c.top1History.get(teamId) ?? []).filter((y) => c.currentYear - y < 5)
    const recentTop3 = (c.top3History.get(teamId) ?? []).filter((y) => c.currentYear - y < 5)
    const capTop1 = recentTop1.length >= 1
    const capTop3 = recentTop3.length >= 2
    if (!capTop1 && !capTop3) top1.set(teamId, w)
    if (!capTop3) top3.set(teamId, w)
  }
  return [top1, top3]
}

// ── Systems ─────────────────────────────────────────────────────────────────

class CurrentNBA implements LotterySystem {
  name = 'Current NBA'
  draftOrder(history: SeasonResult[], c: DraftConstraints, rng: RNG): number[] {
    const lottery = nonPlayoffTeams(last(history), c.playoffSpots)
    const weights = oddsWeights(lottery, NBA_ODDS)
    const picks = weightedLotteryDraw(weights, Math.min(c.lotteryPicks, weights.size), rng)
    return standardTail(lottery, picks)
  }
  tankIncentive(teamId: number, _s: Standing[], history: SeasonResult[], playoffSpots: number): number {
    if (!history.length) return 0.5
    const rank = rankByWinsAsc(last(history), teamId, playoffSpots)
    if (rank <= 3) return 0.9
    if (rank <= 6) return 0.6
    if (rank <= 10) return 0.3
    return 0.1
  }
}

class FlatBottom implements LotterySystem {
  name = 'Flat Bottom'
  draftOrder(history: SeasonResult[], c: DraftConstraints, rng: RNG): number[] {
    const lottery = nonPlayoffTeams(last(history), c.playoffSpots)
    const weights = new Map(lottery.map((t) => [t[0], 1.0]))
    const picks = weightedLotteryDraw(weights, Math.min(c.lotteryPicks, weights.size), rng)
    return standardTail(lottery, picks)
  }
  tankIncentive(): number {
    return 0.15
  }
}

class PlayInBoost implements LotterySystem {
  name = 'Play-In Boost'
  draftOrder(history: SeasonResult[], c: DraftConstraints, rng: RNG): number[] {
    const lottery = nonPlayoffTeams(last(history), c.playoffSpots)
    const n = lottery.length
    const playInCount = Math.min(c.playInSlots, n)
    const floorCount = n - playInCount
    const weights = new Map<number, number>()
    lottery.forEach((t, i) => {
      if (i >= floorCount) {
        const within = n - 1 - i
        weights.set(t[0], NBA_ODDS[Math.min(within, NBA_ODDS.length - 1)]!)
      } else {
        const within = floorCount - 1 - i
        weights.set(t[0], NBA_ODDS[Math.min(playInCount + within, NBA_ODDS.length - 1)]!)
      }
    })
    const picks = weightedLotteryDraw(weights, Math.min(c.lotteryPicks, weights.size), rng)
    return standardTail(lottery, picks)
  }
  tankIncentive(teamId: number, _s: Standing[], history: SeasonResult[], playoffSpots: number): number {
    if (!history.length) return 0.4
    const lottery = nonPlayoffTeams(last(history), playoffSpots)
    const rank = rankByWinsAsc(last(history), teamId, playoffSpots)
    if (rank >= lottery.length - 3) return 0.05
    if (rank <= 3) return 0.8
    return 0.4
  }
}

class UEFACoefficient implements LotterySystem {
  name = 'UEFA Coefficient'
  draftOrder(history: SeasonResult[], c: DraftConstraints, rng: RNG): number[] {
    const lottery = nonPlayoffTeams(last(history), c.playoffSpots)
    const weights = new Map<number, number>()
    for (const [tid] of lottery) weights.set(tid, uefaCoefficient(tid, history, c.playoffSpots))
    const picks = weightedLotteryDraw(weights, Math.min(c.lotteryPicks, weights.size), rng)
    return standardTail(lottery, picks)
  }
  tankIncentive(teamId: number, _s: Standing[], history: SeasonResult[], playoffSpots: number): number {
    if (history.length < 2) return 0.5
    return Math.min(0.7, uefaCoefficient(teamId, history, playoffSpots) / 15.0)
  }
}

class RCL implements LotterySystem {
  name = 'RCL'
  draftOrder(history: SeasonResult[], c: DraftConstraints, rng: RNG): number[] {
    const lottery = nonPlayoffTeams(last(history), c.playoffSpots)
    const baseWeights = new Map<number, number>()
    for (const [tid, wins] of lottery) {
      let coeff = rclCoefficient(tid, history, c.playoffSpots)
      if (wins < 20) coeff *= 0.85
      baseWeights.set(tid, coeff)
    }
    let [top1Pool, top3Pool] = rclApplyCaps(baseWeights, c)
    if (top1Pool.size === 0) top1Pool = new Map(baseWeights)
    const pick1 = weightedLotteryDraw(top1Pool, 1, rng)
    let remainingTop3 = new Map([...top3Pool].filter(([k]) => !pick1.includes(k)))
    if (remainingTop3.size === 0) remainingTop3 = new Map([...baseWeights].filter(([k]) => !pick1.includes(k)))
    const picks23 = weightedLotteryDraw(remainingTop3, Math.min(2, remainingTop3.size), rng)
    const drawn = new Set([...pick1, ...picks23])
    const remainingAll = new Map([...baseWeights].filter(([k]) => !drawn.has(k)))
    const pick4 = weightedLotteryDraw(remainingAll, Math.min(1, remainingAll.size), rng)
    const lotteryPicks = [...pick1, ...picks23, ...pick4]
    if (pick1.length) {
      const arr = c.top1History.get(pick1[0]!) ?? []
      arr.push(c.currentYear)
      c.top1History.set(pick1[0]!, arr)
    }
    for (const pick of lotteryPicks.slice(0, 3)) {
      const arr = c.top3History.get(pick) ?? []
      arr.push(c.currentYear)
      c.top3History.set(pick, arr)
    }
    return standardTail(lottery, lotteryPicks)
  }
  tankIncentive(teamId: number, _s: Standing[], history: SeasonResult[], playoffSpots: number): number {
    if (history.length < 1) return 0.4
    return Math.min(0.6, rclCoefficient(teamId, history, playoffSpots) / 18.0)
  }
}

class LotteryTournament implements LotterySystem {
  name = 'Lottery Tournament'
  draftOrder(history: SeasonResult[], c: DraftConstraints, rng: RNG): number[] {
    const lottery = nonPlayoffTeams(last(history), c.playoffSpots)
    const getWins = (tid: number): number => {
      for (const [id, w] of lottery) if (id === tid) return w
      return 20
    }
    const playGame = (a: number, b: number): number => {
      let pA = 0.5 + (getWins(a) - getWins(b)) * 0.01
      pA = Math.max(0.2, Math.min(0.8, pA))
      return rng.random() < pA ? a : b
    }
    const n = lottery.length
    let tournamentSize = 2
    while (tournamentSize * 2 <= Math.min(n, 8)) tournamentSize *= 2
    const bottomT = lottery.slice(0, tournamentSize)
    const rest = lottery.slice(tournamentSize)
    const bracket = bottomT.map((t) => t[0])
    rng.shuffle(bracket)
    let currentRound = [...bracket]
    while (currentRound.length > 1) {
      const next: number[] = []
      for (let i = 0; i < currentRound.length; i += 2) {
        if (i + 1 < currentRound.length) next.push(playGame(currentRound[i]!, currentRound[i + 1]!))
        else next.push(currentRound[i]!)
      }
      currentRound = next
    }
    const champion = currentRound[0]!
    const losers = bracket.filter((t) => t !== champion).sort((a, b) => getWins(a) - getWins(b))
    const restSorted = rest.map((t) => t[0]).sort((a, b) => getWins(a) - getWins(b))
    return [champion, ...losers, ...restSorted]
  }
  tankIncentive(teamId: number, _s: Standing[], history: SeasonResult[], playoffSpots: number): number {
    if (!history.length) return 0.4
    return rankByWinsAsc(last(history), teamId, playoffSpots) <= 8 ? 0.5 : 0.2
  }
}

class PureInversion implements LotterySystem {
  name = 'Pure Inversion'
  draftOrder(history: SeasonResult[], c: DraftConstraints): number[] {
    const lottery = nonPlayoffTeams(last(history), c.playoffSpots)
    return [...lottery].sort((a, b) => b[1] - a[1]).map((t) => t[0])
  }
  tankIncentive(): number {
    return -0.5
  }
}

class GoldPlan implements LotterySystem {
  name = 'Gold Plan (PWHL)'
  draftOrder(history: SeasonResult[], c: DraftConstraints): number[] {
    const season = last(history)
    const lottery = nonPlayoffTeams(season, c.playoffSpots)
    const wps = c.weeksPerSeason
    const winsByTid = new Map(lottery.map((t) => [t[0], t[1]]))
    const postElimScore = (tid: number): number => {
      const elimWeek = season.eliminatedWeek.get(tid) ?? wps
      const total = season.points.get(tid) ?? winsByTid.get(tid) ?? 0
      const scoredBefore = total * (elimWeek / wps)
      return Math.max(0.0, total - scoredBefore)
    }
    return lottery.map((t) => t[0]).sort((a, b) => postElimScore(b) - postElimScore(a))
  }
  tankIncentive(_teamId: number, _s: Standing[], history: SeasonResult[]): number {
    return history.length ? 0.1 : 0.3
  }
}

class ChipWindowSystem implements LotterySystem {
  name = 'Chip Window'
  private static GAMES_IN_WINDOW = 22
  private static QUINTILE_CHIPS = [100.0, 80.0, 60.0, 40.0, 20.0]
  private simulateChips(winProb: number, rng: RNG, startingChips: number): number {
    let chips = startingChips
    for (let i = 0; i < ChipWindowSystem.GAMES_IN_WINDOW; i++) {
      const bet = chips >= 50.0 ? 25.0 : 10.0
      if (rng.random() < winProb) chips += bet
      else chips = Math.max(10.0, chips - bet)
    }
    if (chips > 100.0) chips *= 2.0
    return chips
  }
  draftOrder(history: SeasonResult[], c: DraftConstraints, rng: RNG): number[] {
    const lottery = nonPlayoffTeams(last(history), c.playoffSpots)
    const byWins = [...lottery].sort((a, b) => a[1] - b[1] || b[2] - a[2] || a[0] - b[0])
    const startChips = new Map<number, number>()
    byWins.forEach((t, rank0) => {
      const q = Math.min(Math.floor(rank0 / 6), 4)
      startChips.set(t[0], ChipWindowSystem.QUINTILE_CHIPS[q]!)
    })
    const rawChips = new Map<number, number>()
    for (const [tid, wins, losses] of lottery) {
      const total = wins + losses
      const winProb = total > 0 ? wins / total : 0.3
      rawChips.set(tid, this.simulateChips(winProb, rng, startChips.get(tid)!))
    }
    const winsMap = new Map(lottery.map((t) => [t[0], t[1]]))
    return [...rawChips.keys()].sort((a, b) => rawChips.get(b)! - rawChips.get(a)! || winsMap.get(a)! - winsMap.get(b)!)
  }
  tankIncentive(teamId: number, _s: Standing[], history: SeasonResult[], playoffSpots: number): number {
    if (!history.length) return 0.2
    const rank = rankByWinsAsc(last(history), teamId, playoffSpots)
    if (rank <= 3) return 0.2
    if (rank <= 7) return 0.12
    return 0.08
  }
}

class TheWheel implements LotterySystem {
  name = 'The Wheel'
  draftOrder(history: SeasonResult[], c: DraftConstraints): number[] {
    const lottery = nonPlayoffTeams(last(history), c.playoffSpots)
    const n = c.numTeams
    const slot = (tid: number): number => (((tid + c.currentYear) % n) + n) % n
    return [...lottery].sort((a, b) => slot(a[0]) - slot(b[0])).map((t) => t[0])
  }
  tankIncentive(): number {
    return 0.0
  }
}

class LegacyNBA implements LotterySystem {
  name = 'Pre-2019 Legacy NBA'
  draftOrder(history: SeasonResult[], c: DraftConstraints, rng: RNG): number[] {
    const lottery = nonPlayoffTeams(last(history), c.playoffSpots)
    const weights = oddsWeights(lottery, LEGACY_NBA_ODDS)
    const picks = weightedLotteryDraw(weights, Math.min(LEGACY_LOTTERY_PICKS, weights.size), rng)
    return standardTail(lottery, picks)
  }
  tankIncentive(teamId: number, _s: Standing[], history: SeasonResult[], playoffSpots: number): number {
    if (!history.length) return 0.6
    const rank = rankByWinsAsc(last(history), teamId, playoffSpots)
    if (rank === 1) return 0.95
    if (rank <= 3) return 0.85
    if (rank <= 6) return 0.55
    if (rank <= 10) return 0.25
    return 0.1
  }
}

class EqualOdds implements LotterySystem {
  name = 'Equal Odds'
  draftOrder(history: SeasonResult[], c: DraftConstraints, rng: RNG): number[] {
    const lottery = nonPlayoffTeams(last(history), c.playoffSpots)
    const weights = new Map(lottery.map((t) => [t[0], 1.0]))
    const picks = weightedLotteryDraw(weights, Math.min(c.lotteryPicks, weights.size), rng)
    return standardTail(lottery, picks)
  }
  tankIncentive(): number {
    return 0.05
  }
}

class TopFourOnly implements LotterySystem {
  name = 'Top-4 Only Lottery'
  draftOrder(history: SeasonResult[], c: DraftConstraints, rng: RNG): number[] {
    const lottery = nonPlayoffTeams(last(history), c.playoffSpots)
    const lp = c.lotteryPicks
    const top4 = lottery.slice(0, lp)
    const rest = lottery.slice(lp)
    const weights = new Map<number, number>()
    top4.forEach((t, i) => weights.set(t[0], lp - i))
    const picks = weightedLotteryDraw(weights, Math.min(c.lotteryPicks, weights.size), rng)
    const winsMap = new Map(lottery.map((t) => [t[0], t[1]]))
    const restSorted = rest.map((t) => t[0]).sort((a, b) => winsMap.get(a)! - winsMap.get(b)!)
    return [...picks, ...restSorted]
  }
  tankIncentive(teamId: number, _s: Standing[], history: SeasonResult[], playoffSpots: number): number {
    if (!history.length) return 0.4
    const rank = rankByWinsAsc(last(history), teamId, playoffSpots)
    if (rank === 1) return 0.85
    if (rank <= 4) return 0.65
    if (rank <= 6) return 0.75
    return 0.05
  }
}

class CurrentNHL implements LotterySystem {
  name = 'Current NHL'
  draftOrder(history: SeasonResult[], c: DraftConstraints, rng: RNG): number[] {
    const lottery = nonPlayoffTeams(last(history), c.playoffSpots)
    const weights = oddsWeights(lottery, NHL_LOTTERY_ODDS)
    const picks = weightedLotteryDraw(weights, Math.min(CURRENT_NHL_LOTTERY_PICKS, weights.size), rng)
    return standardTail(lottery, picks)
  }
  tankIncentive(teamId: number, _s: Standing[], history: SeasonResult[], playoffSpots: number): number {
    if (!history.length) return 0.4
    const rank = rankByWinsAsc(last(history), teamId, playoffSpots)
    if (rank <= 2) return 0.85
    if (rank <= 5) return 0.45
    if (rank <= 9) return 0.2
    return 0.05
  }
}

class CurrentMLB implements LotterySystem {
  name = 'Current MLB'
  draftOrder(history: SeasonResult[], c: DraftConstraints, rng: RNG): number[] {
    const lottery = nonPlayoffTeams(last(history), c.playoffSpots)
    const weights = oddsWeights(lottery, MLB_LOTTERY_ODDS)
    const picks = weightedLotteryDraw(weights, Math.min(CURRENT_MLB_LOTTERY_PICKS, weights.size), rng)
    return standardTail(lottery, picks)
  }
  tankIncentive(teamId: number, _s: Standing[], history: SeasonResult[], playoffSpots: number): number {
    if (!history.length) return 0.35
    const rank = rankByWinsAsc(last(history), teamId, playoffSpots)
    if (rank <= 2) return 0.75
    if (rank <= 6) return 0.5
    if (rank <= 10) return 0.2
    return 0.05
  }
}

export const ALL_SYSTEMS: LotterySystem[] = [
  new CurrentNBA(),
  new FlatBottom(),
  new PlayInBoost(),
  new UEFACoefficient(),
  new RCL(),
  new LotteryTournament(),
  new PureInversion(),
  new GoldPlan(),
  new ChipWindowSystem(),
  new TheWheel(),
  new LegacyNBA(),
  new EqualOdds(),
  new TopFourOnly(),
  new CurrentNHL(),
  new CurrentMLB(),
]

export const SYSTEM_MAP: Map<string, LotterySystem> = new Map(ALL_SYSTEMS.map((s) => [s.name, s]))
