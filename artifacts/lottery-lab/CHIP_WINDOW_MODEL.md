# Chip Window — Canonical Reference

**Concept:** Ron Bronson — "Bid Standardization" (April 2026)  
**Project:** Lottery Lab  
**Source of truth:** `engine/chip_window_sim.py`  
**Last updated:** April 2026

---

## What It Is and Why It Exists

The NBA draft lottery rewards losing. Under the current system, teams that finish with worse records receive higher probabilities of landing the top pick. This creates a structural incentive to lose games intentionally — "tanking" — because losing more games means a better shot at a franchise-altering pick. The system also does not reward competing hard during the final stretch of a lost season, because a team's draft slot is determined by their record before the postseason.

The Chip Window is a proposed reform designed to make tanking structurally impossible. Instead of awarding draft order based on record alone, teams earn chips through head-to-head competition during the final 22 games of the regular season. Draft order is determined by chip totals at the end of game 82 — not by a weighted lottery draw, and not by who lost the most games.

The core anti-tanking logic:

- Losing during the chip window costs chips. There is no mechanism by which a team can improve their draft position by losing.
- Starting chips still reflect record rank (worse teams start with more), so the system rewards historically bad teams — but it then requires them to compete during the window to protect and grow those chips.
- A team that intentionally loses chip-window games destroys the advantage their bad record gave them.

---

## Evolution: From Original Proposal to Current Simulator

The original "Bid Standardization" paper described a simpler version of the mechanic. The simulator evolved it through implementation and testing. Here is the full history of changes:

| Original proposal | Current implementation |
|---|---|
| Only lottery and play-in teams participate | All 30 teams in the chip pool |
| Win returns your wager, loss deducts it | Pot mechanic: winner gains the opponent's wager; loser loses their own wager |
| Double requires finishing with >100 chips | Double is a pre-assigned home night for all 30 teams; no chip threshold |
| Play-in consolation bonus (+7.5 chips for missing playoffs) | Removed — chips are purely match-based |
| Chips can go negative | Floor at 10 chips (minimum bet) — chips never go below this during the window |
| Flat 100 chips for all teams | 7-tier starting chips by record rank (worst → best): 140 / 120 / 100 / 80 / 60 / 40 / 20 |
| Probabilistic lottery draw | Deterministic chip-standings draft order |
| Single strategy (bet big or small) | Three strategies: aggressive, standard, conservative |
| No variance beyond win probability | Five variance mechanics: behavior shift, bidding personality, hot streaks, playoff fatigue, rally mode |
| No pick-swap modeling | ~25% of safe-playoff teams modeled as swap-aware aggressors |

The most significant design decision was moving all 30 teams into the chip pool. Safe-playoff teams play these 22 games regardless — modeling their chip behavior affects lottery team outcomes and creates realistic variance. Play-in teams were already competing for seeding during these games, so they naturally play as aggressors.

The second most significant change was the starting-chip tier structure. Flat 100 chips for everyone gave worse-record teams no head start. The 7-tier system (140 down to 20) gives the worst teams meaningful firepower while ensuring the system doesn't simply reproduce the old lottery order — teams still have to earn their pick by playing well.

---

## Who Participates

All 30 teams. Classification is determined by record at game 60:

| Status | Count | Default wager strategy |
|---|---|---|
| Safe Playoff | 12 | Conservative (unless pick-swap holder facing lottery team) |
| Play-In | 8 | Aggressive (fighting for both seeding and chips) |
| Lottery | 14 | User-selected (standard / aggressive / conservative) |

The 22-night chip window is a real stretch of basketball. Playoff teams are still managing fatigue and resting players. Play-in teams are fighting for their postseason lives. Lottery teams are — under this system — incentivized to try hard, because tanking costs them chips.

---

## The 22-Night Structure

Each night of the chip window, all 30 teams are randomly paired into 15 simultaneous head-to-head matchups. Home/away assignment is random per game.

The schedule is generated once per season before the window opens. It is used to:

1. Pre-select each team's double night (one randomly-chosen home game per team)
2. Pre-select fatigue nights for safe-playoff teams

The schedule does not change based on standings — it is fixed at the start of the window and all 30 teams know their schedule ahead of time, including which night is their pre-assigned double night.

---

## Starting Chips

Starting chips are assigned after game 60 by record rank, with all 30 teams sorted worst to best:

| Record rank (worst → best) | Starting chips |
|---|---|
| Ranks 1–3 (worst records) | 140 |
| Ranks 4–6 | 120 |
| Ranks 7–9 | 100 |
| Ranks 10–12 | 80 |
| Ranks 13–18 | 60 |
| Ranks 19–24 | 40 |
| Ranks 25–30 (best records) | 20 |

The assignment is fixed at game 60 and does not change based on what happens during the window. A team at rank 2 starts with 140 chips whether they win their first chip-window game or not.

Ties in win totals at game 60 are broken by more losses (worse), then by team id as a stable deterministic tiebreaker.

**Why this structure:** The 7-tier system (versus the earlier flat-100 approach) gives the worst teams real firepower proportional to how bad their season was. A rank-1 team starts with 7× the chips of the rank-30 team. But the model stops short of guaranteeing draft position — the chips have to be defended and grown through competition.

---

## Core Chip Mechanics

### The pot

Both teams in a matchup announce their wager before the game. When the outcome is decided:

- **Winner** receives the opponent's full wager (net gain = opponent's wager)
- **Loser** forfeits their own wager (net loss = own wager)

This is a zero-sum pot: the pot size equals the sum of both wagers, and it transfers entirely to the winner. Neither team's chips change by their own wager alone — what matters is what the opponent bet.

### Chip floor

Chips are clamped at **10** (the minimum bet) after every loss. A team that loses a large bet will not fall below 10. This ensures every team can always participate in the next game, and prevents a single bad night from eliminating a team from the competition.

### Upset bonus

When a lower-record team wins a chip-window game against a higher-record team, they earn a bonus chip award on top of the pot:

**`bonus_chips = opponent_wins_at_G60 − winner_wins_at_G60`** (only on a win, only when positive)

- The winning team receives normal pot gains plus the bonus
- Same-record matchups produce no bonus (gap = 0)
- A winless team beating a 50-win team would earn the maximum theoretical bonus (~50 chips)
- The loser receives no bonus regardless of record differential

**Why this exists:** Upset bonuses give every game real stakes for lower-seeded teams. A lottery team facing a 50-win safe-playoff opponent isn't just playing for a narrow pot — there's an extra chip reward for the genuine upset. This mechanic models the spirit of the chip window: hard competition should be rewarded.

### Tie-breaking

When two lottery teams finish with identical chip totals (rare due to 2-decimal-precision bidding), the team with the **worse record** (fewer wins at game 60) receives the higher pick.

---

## Wager Sizing

Three strategies control base wager sizing per game. Strategy is team-level and fixed for the entire window (except when overridden by rally mode or pick-swap logic).

| Strategy | Wager logic |
|---|---|
| **Standard** | 15–40% of current chip stack, proportional to chip total — rising as chips accumulate |
| **Aggressive** | 30–60% of current chip stack — big swings, high variance in both directions |
| **Conservative** | 10–20 chips flat regardless of stack size — slow, stable, low variance |

Minimum wager is always **10 chips**. Maximum wager is the team's current chip total.

A small gaussian noise term (σ=2) is added to every wager, and wagers use 2-decimal precision to minimize the probability of finishing with identical chip totals as a rival.

### Bidding personality

All 30 teams are assigned a permanent bidding personality at the start of each season, independent of strategy. Personality is a multiplier applied to the base wager after strategy calculation:

| Personality | Frequency | Effect |
|---|---|---|
| Standard | 40% | No multiplier |
| Bold | 20% | ×1.25–1.50 on every wager |
| Cautious | 20% | ×0.60–0.80 on every wager |
| Volatile | 20% | Randomly picks bold or cautious each individual game |

A Bold team playing Conservative strategy still bets more than a Standard team playing the same strategy. Personality and strategy are independent axes, producing a 12-combination matrix of betting behavior across the league.

---

## The Double

Every team has one pre-assigned home night across the 22 games. On that night, the home team declares a **double** — this is automatic and happens whenever it is their designated night.

**How it works:**
- Both teams wager their normal strategy-derived amounts
- The **winner** (home or away) earns **2× the opponent's wager** instead of 1×
- The **loser** forfeits only their own wager at 1× (no doubled deduction)
- Each team can only double once; the night is pre-assigned, not chosen reactively

**Design intent:** The double creates one high-stakes night per team per season. Because it is pre-assigned before the window opens (when final standings are unknown), teams cannot time it strategically. The 2× payout multiplier only — not a 2× deduction — keeps the downside bounded while making the win consequential.

---

## Draft Order

At the end of the 22-night window:

**Picks 1–14:** The 14 lottery teams are sorted by final chip total, highest to lowest. Most chips = Pick 1. Fewest chips = Pick 14. This is fully deterministic — no lottery draw, no weighted randomness.

**Picks 15–30:** Safe-playoff and play-in teams are ordered by record (same as the current NBA system). Chips do not affect their pick positions.

**Tie-breaking (rare):** Two lottery teams with identical chip totals → worse record (fewer wins) gets the higher pick.

---

## Variance Mechanics

Five variance mechanics model real-world noise in the chip window. These are always active regardless of user strategy selection.

### 1. Lottery behavior shift (on-court)

At game 60, lottery teams stop tanking and start competing. They call up G-League players, sign veterans, and actually try to win. This is the most fundamental input assumption in the simulator: static season-long win rates reflect passive losing, not the behavioral shift that the chip window itself induces.

Each lottery team draws a random **effective talent boost** at the start of each season's chip window. Two tiers by record rank within the lottery (worst 7 vs. better 7):

| Lottery tier | Shift range | Rationale |
|---|---|---|
| Bottom 7 (worst records, picks 1–7 territory) | +5 to +25 talent points | Wide variance — some truly bad teams dramatically improve with real effort; some don't have the roster to overcome structural talent gaps |
| Top 7 (middling lottery, near play-in bubble) | +5 to +7 talent points | Small nudge — these teams are closer to .500 already; their chip-window behavior change is marginal |

The shift applies only to chip-window games (nights 1–22). It does not affect season record bookkeeping or starting-chip assignment (those are locked at game 60).

Play-in and safe-playoff teams receive no shift — they are already motivated: play-in teams are fighting for seeding, playoff teams are playing real games.

**Effect on win probability** (logistic scale=14, typical examples):

| Raw talent | Shift (bottom tier) | Effective | Chip-window win % vs avg opponent |
|---|---|---|---|
| 28 (worst) | +15 | 43 | ~37% (was ~15% regular season) |
| 35 (bad) | +10 | 45 | ~42% (was ~22%) |
| 42 (middling) | +7 | 49 | ~49% (was ~35%) |

The shift does not make bad teams good. Even with a +25 shift, a talent-28 team still loses most chip-window games against average competition. But they're no longer getting blown out at a 15% win rate.

### 2. Bidding personality

Described above in the wager sizing section. Assigned to all 30 teams at season start. Applies a permanent multiplier to every wager across the window.

### 3. Hot streak

About 20% of lottery and play-in teams receive a random performance surge during the window:

- Surge window: 5–8 consecutive nights, starting between night 1 and night 18 (stays within the 22-night window)
- Win probability boost: +8% to +15% for each game within the streak
- Fixed at season start; does not respond to chip standings or outcomes
- UI label: `HOT` badge with boost percentage

### 4. Playoff fatigue

Safe-playoff teams are modeled as sometimes resting players or playing tired during the chip window. About 30% of a safe-playoff team's 22 nights are designated as fatigue nights:

- Win probability reduced by 10 percentage points on fatigue nights
- Fatigue nights are selected randomly before the window opens
- UI label: `[REST]` badge

Fatigue creates natural variance in playoff-vs-lottery matchups: some nights the lottery team faces a full-strength opponent, some nights a depleted one. This models real-world back-to-back fatigue and load management.

### 5. Rally mode

After each night in the window, any lottery team with chips ≤ 20 and at least 10 nights remaining automatically flips into rally mode:

- Strategy is overridden to aggressive for all remaining nights
- Win probability gets an additional +4% boost per game
- Rally mode is permanent once triggered — a team cannot exit it
- UI label: `RALLY` badge

Rally mode models genuinely desperate teams — a lottery team near the chip floor has nothing to conserve and starts playing for every chip they can recover. Empirically, about 15–20% of lottery teams enter rally mode in any given season.

---

## Pick-Swap Holder Modeling

About 25% of safe-playoff teams are randomly designated as pick-swap holders at season start. These teams hold a future first-round pick interest in a lottery team and have a strategic incentive to compete harder against lottery opponents.

**Behavior change:** When a pick-swap holder faces a lottery opponent, their strategy overrides from conservative to aggressive for that matchup only. Their default conservative behavior against non-lottery opponents is unchanged.

This is a background mechanic — it affects chip outcomes but is not surfaced prominently in the UI. It models the real-world dynamic where contending teams are not indifferent to lottery-team performance.

---

## Win Probability Model

All head-to-head outcomes use a **log5 formula** on logistic win rates.

**Single-team win rate** (logistic, scale=14):
```
win_prob(talent) = 1 / (1 + exp(-(talent - 50) / 14))
```

Calibration: talent 76 ≈ 84% win rate (≈69 wins/season); talent 50 = 50% (≈41 wins); talent 18 ≈ 15% (≈12 wins).

**Head-to-head probability** (log5):
```
p(A beats B) = (p_A × (1 - p_B)) / (p_A × (1 - p_B) + p_B × (1 - p_A))
```

Talent is initialized from a `gauss(50, 10)` distribution clipped to [18, 76], then evolves by ±`gauss(0, 1.5)` each season. Within a season, each team's simulated talent is jittered by ±`gauss(0, 2.5)` before game-60 record simulation.

Effective talent during the chip window = base talent + behavior shift (lottery teams only) + hot streak boost + rally boost − fatigue discount.

---

## Narrative System

Each matchup generates a one-line narrative. Priority order (first matching condition wins):

1. Double game declared → pick-position math if the declarer wins
2. Playoff fatigue (home or away safe-playoff team) → rest/fatigue label
3. Rally mode (home or away lottery team) → RALLY label with chip context
4. Hot streak active (home or away lottery/play-in team) → HOT label with boost percentage
5. Lottery vs. lottery matchup → live chip rank comparison (#X vs #Y)
6. Pick-swap holder vs. lottery team → swap-holder narrative
7. Safe-playoff vs. lottery → generic stakes line
8. Near-floor lottery team → floor narrative
9. Play-in matchup → seeding battle line
10. Default → team names and night number

Chip ranks in narratives are computed from live chip totals at the **start** of each night, not from end-of-season rankings.

---

## Parameters Reference

| Parameter | Value |
|---|---|
| Window opens | After game 60 |
| Window length | 22 games (G61–G82) |
| Teams in pool | All 30 |
| Starting chips — ranks 1–3 (worst) | 140 |
| Starting chips — ranks 4–6 | 120 |
| Starting chips — ranks 7–9 | 100 |
| Starting chips — ranks 10–12 | 80 |
| Starting chips — ranks 13–18 | 60 |
| Starting chips — ranks 19–24 | 40 |
| Starting chips — ranks 25–30 (best) | 20 |
| Chip floor | 10 (minimum bet) |
| Minimum wager | 10 chips |
| Wager precision | 2 decimal places |
| Aggressive wager range | 30–60% of stack |
| Standard wager range | 15–40% of stack (proportional) |
| Conservative wager range | 10–20 chips flat |
| Gaussian wager noise | σ = 2.0 |
| Upset bonus | max(0, opponent_wins_60 − winner_wins_60) chips |
| Double mechanic | Pre-assigned home night; winner earns 2× opponent's wager |
| Tie-breaking | Worse record (fewer wins at G60) gets the higher pick |
| Draft order (picks 1–14) | Chips DESC — fully deterministic |
| Draft order (picks 15–30) | Record (current NBA system) |
| Talent distribution | gauss(50, 10), clipped [18, 76] |
| Season talent drift | gauss(0, 1.5) per season |
| Per-season talent jitter | gauss(0, 2.5) |
| Behavior shift — bottom 7 lottery | +5 to +25 talent points |
| Behavior shift — top 7 lottery | +5 to +7 talent points |
| Hot streak frequency | ~20% of lottery + play-in teams |
| Hot streak boost | +8–15% win probability |
| Hot streak length | 5–8 consecutive nights |
| Fatigue nights | ~30% of safe-playoff team's 22 nights |
| Fatigue discount | −10 pp win probability |
| Rally mode trigger | Chips ≤ 20 with ≥ 10 nights remaining |
| Rally boost | +4% win probability |
| Pick-swap holder frequency | ~25% of safe-playoff teams |
| Personality: Standard | 40% of teams |
| Personality: Bold | 20% (×1.25–1.50 wager) |
| Personality: Cautious | 20% (×0.60–0.80 wager) |
| Personality: Volatile | 20% (bold or cautious, re-rolled each game) |

---

## The Anti-Tanking Property

The Chip Window is designed so that no team can improve their draft position by intentionally losing. Here is why this holds structurally:

1. **Losing costs chips.** Every loss forfeits your wager. A team that tanks during the window bleeds chips at the same rate regardless of whether the loss was intentional.

2. **Starting chips are locked at game 60.** A team cannot improve their starting chip position by losing more games. The 7-tier assignment is determined at the start of the window and does not change based on chip-window performance.

3. **Draft order is determined by chip total, not record.** A team with a bad record but low chips finishes lower in the draft order than a team with a better record but high chips. There is no record-based backstop.

4. **The behavior-shift mechanic models realistic compliance.** When the chip window is active, lottery teams are assumed to actually try — because losing costs them chips. The talent shift (+5 to +25) models this behavioral change. The system's anti-tanking property is self-reinforcing: the incentives change behavior, and changed behavior is modeled.

5. **No mechanism rewards passivity.** There is no way to "save" chips by not playing. Every game requires a wager (minimum 10). The only path to more chips is winning.

---

## Simulator UI

The Chip Window Simulator (available at `/chip-window`) runs Monte Carlo simulations of the chip window across 5–15 seasons.

**Input parameters:**
- Seasons (5–15)
- Random seed (optional — same seed produces identical results)
- Lottery team strategy (Standard / Aggressive / Conservative)

**Output — season-by-season view:**
- Chip standings table: all 30 teams sorted by chip total within status group
- Trajectory chart: chip totals across all 22 nights, progressive reveal via slider
- Game-by-game schedule: all 15 nightly matchups with wagers, outcomes, variance badges, narratives
- Team detail panel: full stats, personality description, sparkline, best/worst night

**Output — analytics panels** (toggle, shown/hidden):
- Double Effectiveness: win rate and chip gain when double is declared
- Gini Coefficient over time: chip inequality within the lottery field across the window
- Biggest Swings: top single-night chip gains and losses
- Personality ROI: average chips-per-game by bidding personality
- Starting-rank vs. final-pick scatter: how well starting chips predict draft order
- Double Timing analysis: early vs. late double declarations compared by outcome

**Export options:**
- CSV: per-team stats for the current season
- JSON: full simulation data (all seasons, all nights, all wagers) for external analysis
- Print / PDF: clean white-background version with all analytics expanded

---

## Technical Files

| File | Purpose |
|---|---|
| `engine/chip_window_sim.py` | Full 30-team simulation engine — all mechanics, variance, schedule, narratives |
| `engine/lottery_sim.py` | Simplified `ChipWindow` class used by the 13-system comparison framework |
| `web/router.py` | `/chip-window`, `/chip-window/run`, `/leaderboard` routes |
| `web/templates/chip_window.html` | Standalone simulator UI — form, results, analytics, export |
| `web/templates/chip_leaderboard.html` | Three-tab leaderboard with trajectory chart and team detail panel |
| `web/templates/index.html` | System selector (Chip Window short tag: "G60–G82 chip standings decide draft order.") |
| `web/static/lottery-lab.css` | All styles: personality pills, team detail panel, analytics panels, print CSS |
