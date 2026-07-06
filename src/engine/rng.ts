// A seeded PRNG that mirrors the surface of Python's `random.Random` used by the
// original engine: random(), uniform(), gauss(), betavariate(), choice(),
// shuffle(). We target STATISTICAL parity, not bit-exact parity with CPython's
// Mersenne Twister — this is a Monte Carlo tool, so faithful distributions and
// algorithms are what matter, and results converge to the same metrics.
//
// The base uniform stream is mulberry32 (same generator the Cap Buffet roster
// generator uses), which is fast, deterministic, and well-distributed.

export class RNG {
  private a: number

  constructor(seed?: number | null) {
    // Match Python's `random.Random(None)` = nondeterministic when no seed.
    this.a = (seed ?? Math.floor(Math.random() * 0xffffffff)) >>> 0
  }

  /** Uniform float in [0, 1). */
  random(): number {
    let t = (this.a += 0x6d2b79f5)
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }

  /** Uniform float in [a, b] (Python: a + (b-a)*random()). */
  uniform(a: number, b: number): number {
    return a + (b - a) * this.random()
  }

  /** Normal variate via Box–Muller. */
  gauss(mu: number, sigma: number): number {
    let u1 = this.random()
    const u2 = this.random()
    if (u1 < 1e-12) u1 = 1e-12
    const mag = Math.sqrt(-2.0 * Math.log(u1))
    return mu + sigma * mag * Math.cos(2 * Math.PI * u2)
  }

  /** Gamma variate (shape k, scale θ) via Marsaglia–Tsang. */
  private gamma(k: number, theta: number): number {
    if (k < 1) {
      // Boost: gamma(k) = gamma(k+1) * U^(1/k)
      const u = this.random()
      return this.gamma(1 + k, theta) * Math.pow(u < 1e-12 ? 1e-12 : u, 1 / k)
    }
    const d = k - 1 / 3
    const c = 1 / Math.sqrt(9 * d)
    for (;;) {
      let x: number
      let v: number
      do {
        x = this.gauss(0, 1)
        v = 1 + c * x
      } while (v <= 0)
      v = v * v * v
      const u = this.random()
      const x2 = x * x
      if (u < 1 - 0.0331 * x2 * x2) return d * v * theta
      if (Math.log(u) < 0.5 * x2 + d * (1 - v + Math.log(v))) return d * v * theta
    }
  }

  /** Beta variate via two gamma draws: X/(X+Y), X~Γ(α), Y~Γ(β). */
  betavariate(alpha: number, beta: number): number {
    const x = this.gamma(alpha, 1)
    if (x === 0) return 0
    const y = this.gamma(beta, 1)
    return x / (x + y)
  }

  /** Uniformly pick one element (Python: seq[int(random()*len)]). */
  choice<T>(seq: readonly T[]): T {
    return seq[Math.floor(this.random() * seq.length)]!
  }

  /** In-place Fisher–Yates matching Python's random.shuffle order. */
  shuffle<T>(x: T[]): void {
    for (let i = x.length - 1; i >= 1; i--) {
      const j = Math.floor(this.random() * (i + 1))
      const tmp = x[i]!
      x[i] = x[j]!
      x[j] = tmp
    }
  }

  /** Random integer in [a, b] inclusive (Python random.randint). */
  randint(a: number, b: number): number {
    return a + Math.floor(this.random() * (b - a + 1))
  }

  /** k distinct integers from [0, n) (Python random.sample(range(n), k)). */
  sample(n: number, k: number): number[] {
    const pool = Array.from({ length: n }, (_, i) => i)
    const out: number[] = []
    for (let i = 0; i < k && pool.length; i++) {
      const j = Math.floor(this.random() * pool.length)
      out.push(pool[j]!)
      pool[j] = pool[pool.length - 1]!
      pool.pop()
    }
    return out
  }
}
