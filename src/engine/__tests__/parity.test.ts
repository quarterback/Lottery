// Statistical-parity golden test: the TS engine uses a different PRNG than the
// Python original, so metrics can't match bit-for-bit — but the odds tables,
// effort model, and formulas are faithful, so averaged Monte Carlo metrics must
// land close to the Python reference. Reference values were generated from
// engine/lottery_sim.py: monte_carlo(system, runs=40, seasons=15, seed=42, nba).
import { describe, it, expect } from 'vitest'
import { monteCarlo } from '../monteCarlo'
import { SYSTEM_MAP } from '../systems'
import { NBA_CONFIG } from '../leagues'

const OPTS = { runs: 40, seasons: 15, seed: 42 }

// Python reference (see commit message / artifacts/lottery-lab engine).
const PY = {
  'Current NBA': { lateEffort: 0.9744, gini: 0.701, tank: 2.66, balance: 21.56, top3Wins: 14.37, rankFirst: 77.5, rankLast: 3.4 },
  'Flat Bottom': { lateEffort: 0.996, gini: 0.6037, tank: 0.0, balance: 20.81, top3Wins: 22.06, rankFirst: 77.2, rankLast: 4.5 },
  'Pure Inversion': { lateEffort: 1.0, gini: 0.6243, tank: 0.0, balance: 20.78, top3Wins: 36.92, rankFirst: 76.4, rankLast: 4.0 },
  'Current NHL': { lateEffort: 0.9856, gini: 0.7421, tank: 1.37, balance: 21.13, top3Wins: 12.18, rankFirst: 77.2, rankLast: 3.0 },
} as const

describe('engine statistical parity with Python reference', () => {
  for (const [name, ref] of Object.entries(PY)) {
    it(`${name} metrics land near the Python reference`, () => {
      const m = monteCarlo(SYSTEM_MAP.get(name)!, NBA_CONFIG, OPTS)
      // Competitive balance and the win curve are RNG-robust structural signatures.
      expect(m.competitiveBalance).toBeGreaterThan(ref.balance - 3)
      expect(m.competitiveBalance).toBeLessThan(ref.balance + 3)
      expect(m.avgWinsByRank[0]!).toBeGreaterThan(ref.rankFirst - 5)
      expect(m.avgWinsByRank[0]!).toBeLessThan(ref.rankFirst + 5)
      expect(m.avgWinsByRank.at(-1)!).toBeLessThan(ref.rankLast + 4)
      // Top-3 recipients is the sharpest signature of *which* teams win picks.
      expect(Math.abs(m.avgWinsTop3Recipients - ref.top3Wins)).toBeLessThan(6)
      // Gini of pick concentration.
      expect(Math.abs(m.giniTop5 - ref.gini)).toBeLessThan(0.12)
      // Tanking behaviour.
      expect(Math.abs(m.tankCycles - ref.tank)).toBeLessThan(2.5)
      expect(Math.abs(m.lateSeasonEffort - ref.lateEffort)).toBeLessThan(0.07)
    })
  }

  it('Pure Inversion never tanks (negative incentive is structural)', () => {
    const m = monteCarlo(SYSTEM_MAP.get('Pure Inversion')!, NBA_CONFIG, { runs: 5, seasons: 10, seed: 1 })
    expect(m.tankCycles).toBe(0)
    expect(m.lateSeasonEffort).toBe(1.0)
  })

  it('Current NBA concentrates #1 picks on the worst teams', () => {
    const m = monteCarlo(SYSTEM_MAP.get('Current NBA')!, NBA_CONFIG, { runs: 20, seasons: 15, seed: 7 })
    // The worst team by avg wins should be among the top #1-pick recipients.
    const byWins = [...m.avgWinsByTeam.entries()].sort((a, b) => a[1] - b[1])
    const worstId = byWins[0]![0]
    const pick1 = [...m.pick1ByTeam.values()]
    expect(m.pick1ByTeam.get(worstId)!).toBeGreaterThan(Math.max(...pick1) * 0.4)
  })
})
