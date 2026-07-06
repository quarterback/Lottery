// Core engine types — ported from the dataclasses in engine/lottery_sim.py.
import type { RNG } from './rng'

export interface Team {
  id: number
  name: string
  trueTalent: number // 0-100; 50 = average
  tankPropensity: number // 0-1
}

/** (teamId, wins, losses), sorted by ranking metric descending. */
export type Standing = [number, number, number]

export interface SeasonResult {
  standings: Standing[]
  /** key `${lo},${hi}` -> [loWins, hiWins] where lo = min(a,b). */
  headToHead: Map<string, [number, number]>
  /** teamId -> week they were mathematically eliminated. */
  eliminatedWeek: Map<number, number>
  /** teamId -> league points (= wins for non-points leagues). */
  points: Map<number, number>
}

export interface DraftConstraints {
  top1History: Map<number, number[]> // teamId -> [years it got #1]
  top3History: Map<number, number[]> // teamId -> [years it got top-3]
  currentYear: number
  playoffSpots: number
  numTeams: number
  gamesPerSeason: number
  weeksPerSeason: number
  playInSlots: number
  lotteryPicks: number
}

export interface MetricsBundle {
  systemName: string
  lateSeasonEffort: number
  repeatTop1Frequency: number
  giniTop5: number
  tankCycles: number
  competitiveBalance: number
  avgWinsTop3Recipients: number
  pickDistribution: Map<number, number[]> // teamId -> [pct of picks 1..5]
  effortByWeek: number[]
  avgWinsByRank: number[]
  avgWinsByTeam: Map<number, number>
  avgPointsByTeam: Map<number, number>
  pick1ByTeam: Map<number, number>
}

export interface RunResult {
  systemName: string
  seasons: SeasonResult[]
  draftOrders: number[][]
  effortLog: number[][][] // [season][week][teamIdx]
  teamIds: number[]
}

export interface LotterySystem {
  name: string
  draftOrder(history: SeasonResult[], constraints: DraftConstraints, rng: RNG): number[]
  /** 0-1 (may be negative): how much losing improves this team's lottery position. */
  tankIncentive(teamId: number, standings: Standing[], history: SeasonResult[], playoffSpots: number): number
}

/** Build a fresh DraftConstraints from a league (mirrors simulate_run's setup). */
export function h2hKey(a: number, b: number): string {
  return a < b ? `${a},${b}` : `${b},${a}`
}
