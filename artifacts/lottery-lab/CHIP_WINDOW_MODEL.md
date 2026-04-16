# Chip Window — Model Reference

**Project:** Lottery Lab  
**Concept:** Ron Bronson — "Bid Standardization" (April 2026)  
**Document status:** Current implementation as of April 2026  
**Source of truth:** `engine/chip_window_sim.py`

---

## What It Is

The Chip Window is a proposed NBA draft reform that makes tanking structurally impossible. Instead of awarding lottery picks based on record, a team's draft position is determined by chips they earn — or maintain — through head-to-head game results across the final 22 games of the regular season (Games 61–82).

Losing costs chips at the same rate regardless of whether the loss was intentional. There is no mechanism by which a team can improve their draft position by losing.

---

## Who Participates

All 30 teams enter the chip pool. Teams are classified at game 60 based on their record:

| Status | Count | Role in chip window |
|--------|-------|---------------------|
| Safe Playoff | 12 | In pool; conservative strategy by default |
| Play-In | 8 | In pool; aggressive strategy (dual incentive: seeding + chips) |
| Lottery | 14 | In pool; strategy is user-selected; draft position at stake |

The original proposal limited participation to non-playoff teams. The simulator extends it to all 30 teams because safe-playoff teams play these games too, and their betting behavior affects lottery team chip totals.

---

## The 22-Night Structure

Each night of the chip window, all 30 teams are randomly paired into 15 simultaneous head-to-head matchups. Home/away assignment is random per game. This runs for 22 nights (Games 61–82).

The schedule is generated once per season before the window opens. The full schedule is used to:
- Pre-select each team's double game (one pre-assigned home night)
- Pre-select fatigue nights for safe-playoff teams

---

## Chip Mechanics

### Starting state — quintile system
Starting chips are assigned by record rank at game 60. All 30 teams are sorted worst to best, then split into five groups of six:

| Record rank (worst → best) | Starting chips |
|---------------------------|---------------|
| 1–6 (worst 6 records) | 100 |
| 7–12 | 80 |
| 13–18 | 60 |
| 19–24 | 40 |
| 25–30 (best 6 records) | 20 |

This gives worse teams more bidding firepower without rewarding additional losing — the quintile assignment is fixed at game 60 and does not change based on what happens during the window.

### Chip floor
Chips are clamped at the **minimum bet (10)** after every loss. Chips can never go below 10. Teams always have enough chips to participate in the next game.

### Wagering — the pot
Both teams in a matchup announce their wager before the outcome. When the game resolves:

- **Winner** gains the opponent's wager (net positive)
- **Loser** loses their own wager (net negative, floored at 10)

### Upset bonus — win-gap chip reward

When a lower-record team wins a chip window game against a higher-record team, they receive a bonus chip award on top of the normal pot:

**`bonus_chips = opponent_wins_60 − your_wins_60`** (only on a win, only when positive)

- The **winner** collects the normal pot **plus** the bonus
- The **loser** gains nothing from the bonus regardless of record
- No coefficient — the raw win-total gap is the multiplier, self-bounded to approximately 0–50 chips
- A winless team (0 wins) beating a 50-win team would earn the maximum theoretical bonus (~50 chips)
- Same-record matchups produce no bonus (gap = 0)

This mechanic rewards genuine upsets in the chip window and makes every game meaningful for lower-seeded teams — even a lottery team facing a 50-win opponent has extra incentive to compete.

### Analytics bidding — tie prevention
Analytics teams bid with **2-decimal precision** to minimise the chance of finishing with an identical chip total as a rival. Since each team's running sum traces a slightly different path from the start of the window, exact chip ties are extremely rare.

When a tie does occur, the team with the **worse record** (fewer wins) receives the higher draft pick.

### Wager sizing

Three strategies control how much a team bets each night:

| Strategy | Bet logic |
|----------|-----------|
| **Aggressive** | 30–60% of current chip stack per game. Big swings in both directions. |
| **Standard** | 15–40% of stack, proportional to chip total — rising with accumulated chips. |
| **Conservative** | 10–20 chips flat regardless of stack size. Low variance; slow gain or loss. |

The minimum wager is always **10 chips**. Strategy assignments by team class:
- **Lottery teams** → user-selected strategy (choice presented in the simulator UI)
- **Play-In teams** → always aggressive (they need wins for seeding and chips)
- **Safe-Playoff teams** → always conservative by default

### The double

Every team has one pre-assigned home night across the 22 games. On that night they may declare a **double**:

- Their wager is doubled for that game
- The opponent automatically responds with a fixed counter-wager of 25 chips
- The declaring team risks their doubled wager; gains 25 on a win
- All 30 teams are eligible — status doesn't matter. Teams plan their double before the window opens, when final standings are unknown.
- Each team can only double once

The double night is selected randomly before the window opens, not reactively by the team based on standings.

---

## Draft Order

At the end of the 22-night window, the 14 lottery teams (teams with STATUS_LOTTERY at game 82) are sorted by final chip total:

**Most chips = Pick 1 · Second most = Pick 2 · … · Fewest chips = Pick 14**

This is fully deterministic — no lottery draw, no weighted randomness, no ping-pong balls.

**Tie-breaking (rare):** if two lottery teams finish with identical chip totals, the team with the **worse record** (fewer wins) receives the higher pick.

**Picks 15–30:** Safe Playoff and Play-In teams are ordered by record (same as the current NBA system). No chip mechanic affects their pick positions.

**Key effects:**
- Worst-record teams start with more chips (100 vs 20 for the best teams) and have a head start toward the top picks
- A bad-record team that also plays well during the window compounds their advantage
- A bad-record team that plays poorly has their chip lead eroded — the quintile cushion helps but doesn't guarantee a top pick
- Tanking during the window destroys chips regardless of intent

---

## Variance Mechanics

Five variance mechanics model real-world noise in the chip window. These are always active regardless of user strategy selection.

### 0. Lottery behavior shift (on-court play)

At game 60, lottery teams stop tanking and start competing. They call up G-League players, sign veterans, and actually try to win. This is the most fundamental input assumption: the sim uses static season-long win rates that reflect passive losing, not the behavioral shift that the chip window itself induces.

To model this, each lottery team draws a random **effective talent boost** at the start of each season's chip window:

- Range: +4.0 to +12.0 talent points (uniform random, independent per team)  
- Applied only to chip window games (nights 1–22); does not affect season-record bookkeeping  
- Play-in and safe-playoff teams receive no shift (they're already motivated — play-in teams are fighting for seeds, playoff teams are playing for real)

**Effect on win probability** (logistic scale=14):

| Raw talent | Shift | Effective | Win % vs 50-talent team |
|-----------|-------|-----------|------------------------|
| 28 (worst) | +10 | 38 | 30% → was 15% |
| 35 (bad) | +7 | 42 | 36% → was 22% |
| 42 (middling) | +6 | 48 | 46% → was 35% |
| 45 (fringe) | +8 | 53 | 57% → was 43% |

The shift does not make bad teams good. A talent-28 team with a +10 shift still loses 70% of chip window games against average competition — but they're no longer losing 85% of them. The model is correct; the input assumptions about how bad teams play in the window are what changed.

### 1. Bidding personality

All 30 teams are assigned a permanent personality at season start, independent of strategy. Personality applies a multiplier to the base wager after strategy calculation:

| Personality | Frequency | Effect |
|-------------|-----------|--------|
| Standard | 40% | No modifier |
| Bold | 20% | ×1.25–1.50 on base wager |
| Cautious | 20% | ×0.60–0.80 on base wager |
| Volatile | 20% | Randomly picks bold or cautious each individual game |

A bold team playing conservative strategy still bids higher than a standard team playing the same strategy. Personality and strategy are independent axes.

### 2. Hot streak

About 20% of lottery and play-in teams receive a random performance surge during the window:

- Surge window: 5–8 consecutive nights, starting between night 1 and night 18 (stays within the 22-night window)
- Win probability boost: +8% to +15% for each game within the streak window
- The streak is fixed at season start; it does not respond to chip standings
- Narrative label: `HOT — [Team] on a surge (+X% win prob tonight)`

### 3. Playoff fatigue

Safe-playoff teams are modeled as sometimes resting players or playing tired during the chip window. Approximately 30% of a safe-playoff team's 22 nights are designated as fatigue nights:

- Win probability reduced by 10 percentage points on fatigue nights
- Fatigue nights are selected randomly before the window opens (not responsive to standings or outcomes)
- Narrative label: `[REST] [Team] back-to-back fatigue / resting starters`

Fatigue creates natural variance in the playoff-vs-lottery matchups: some nights the lottery team faces a full-strength opponent, some nights they face a depleted one.

### 4. Rally mode

After each night in the window, any lottery team with chips ≤ 20 and at least 10 nights remaining automatically flips into rally mode:

- Strategy is overridden to aggressive for all remaining nights
- Win probability gets an additional +4% boost per game
- Rally mode is permanent once triggered — a team cannot exit it
- Narrative label: `RALLY — [Team] nothing to lose — going all-in`

Rally mode exists to model the dynamics of genuinely desperate teams — they have nothing to conserve and start playing for every chip they can recover. Empirically, about 15–20% of lottery teams enter rally mode across simulated seasons.

---

## Pick-Swap Holder Modeling

Approximately 25% of safe-playoff teams are randomly designated as pick-swap holders at season start. These teams hold a future first-round pick interest in a lottery team and have a strategic incentive to compete harder against lottery opponents.

Behavior change: when a pick-swap holder faces a lottery opponent, their strategy overrides from conservative to aggressive for that matchup only.

This is a background mechanic — it affects chip outcomes but does not change the core draft-order calculation. It models a real-world dynamic where contending teams are not indifferent to lottery team performance. It is not emphasized in the UI because it affects a minority of games and is an edge case relative to the core model.

---

## Strategy Comparison Summary

| Strategy | Typical chip range (14-team lottery field) | Best for |
|----------|-------------------------------------------|----------|
| Aggressive | High variance; can reach 200+ or fall toward the floor | Teams trying to climb the chip board |
| Standard | Moderate variance; tracks proportional to win rate | Balanced play across all standings positions |
| Conservative | Low variance; rarely breaks 150, rarely falls below 50 | Teams protecting a chip lead |

Because draft order is determined by relative chip standings, strategy choice only matters relative to what opponents are doing. A conservative team in an aggressive field accumulates fewer chips than average; an aggressive team in a conservative field accumulates more.

---

## Leaderboard Display

The Chip Window Leaderboard (`/leaderboard`) shows the results of a simulated season across three tabs.

### Tab 1 — Chip Standings

All 30 teams ranked by final chip total within their status group. Columns:
- Team name + status pill (Safe Playoff / Play-In / Lottery)
- Strategy pill (user strategy for lottery; fixed for others)
- **Bidding personality pill** — color-coded: orange = Bold, teal = Cautious, purple = Volatile, grey = Standard
- Record through game 60 and chip W-L during the window
- Current chip total with a bar visualization; 2× badge for doubled teams
- Draft pick # (for lottery teams)

### Tab 2 — Trajectory Chart

An SVG line chart showing each team's chip total across all 22 nights of the window:

- Lines are styled per bidding personality: Bold = thick/solid, Cautious = thin/faint, Volatile = dashed, Standard = normal
- A slider controls how many nights are revealed — the chart progressively reveals the season
- An endpoint dot shows each team's position at the current slider value
- Clicking any team in the legend opens the team detail panel

### Tab 3 — Game-by-Game

The full 22-night schedule with all 15 matchups per night:
- Wager amounts, pot size, outcome
- Variance badges: `HOT` (red), `RALLY` (blue), `[REST]` (grey)
- Double badge for declared double games
- Narrative line generated per matchup from live chip rankings at tip-off

### Team detail panel

Clicking any team row or trajectory legend entry opens a slide-up panel:
- Full-season record and status
- Personality pill with a plain-English description of betting behavior
- Chip stats: starting chips (quintile), final chips, chip W-L, draft pick #
- **Best Night** and **Worst Night** stats — single-game biggest gain and worst loss with game number (G61–G82)
- Full 22-night sparkline styled per personality, with markers (▲ green = best night, ▼ red = worst night)

### CSV export

The leaderboard exports a CSV with all team data including bidding personality, hot streak flag, and rally mode flag.

---

## Narrative System

Each game in the schedule generates a one-line narrative. Priority order (first matching condition wins):

1. Double game declared → Pick position math if team wins
2. Playoff fatigue (home or away safe-playoff team) → Rest/fatigue label
3. Rally mode (home or away lottery team in rally) → RALLY label
4. Hot streak active (home or away lottery/play-in team) → HOT label with boost percentage
5. Lottery vs. lottery matchup → Live chip rank comparison (#X vs #Y)
6. Pick-swap holder vs. lottery team → Swap narrative
7. Safe-playoff vs. lottery → Generic stakes line
8. Near-floor (lottery team at or near their own starting chips) → Floor narrative
9. Play-in matchup → Seeding battle line
10. Default → Team names and night number

Chip ranks used in narratives are computed from live chip totals at the start of each night, not from end-of-season rankings.

---

## Simulation Parameters

| Parameter | Value |
|-----------|-------|
| Window opens | After game 60 |
| Window length | 22 games (G61–G82) |
| Teams in pool | All 30 |
| Starting chips | Quintile: 100 / 80 / 60 / 40 / 20 by record rank (groups of 6) |
| Minimum chip floor | 10 chips — chips never go below this during the window |
| Minimum bet | 10 chips |
| Analytics bid precision | 2 decimal places — minimises exact tie probability |
| Aggressive range | 30–60% of stack |
| Standard range | 15–40% of stack (proportional) |
| Conservative range | 10–20 chips flat |
| Upset bonus | Lower-record winner earns bonus = opponent_wins_60 − winner_wins_60 (max ~50) |
| Double mechanic | One pre-assigned home night per team; all 30 teams eligible; no chip threshold |
| Double opponent response | Fixed 25 chips |
| Tie-breaking | Worse record (fewer wins) gets the higher draft pick |
| Draft order (picks 1–14) | Lottery teams sorted by chips DESC — fully deterministic |
| Draft order (picks 15–30) | Playoff/Play-In teams sorted by record |
| Hot streak frequency | ~20% of lottery + play-in teams |
| Hot streak boost | +8–15% win probability |
| Hot streak length | 5–8 consecutive nights |
| Fatigue nights | ~30% of safe-playoff team's nights |
| Fatigue discount | -10 pp win probability |
| Rally mode trigger | Chips ≤ 20 with ≥ 10 nights remaining |
| Rally boost | +4% win probability |
| Pick-swap holder frequency | ~25% of safe-playoff teams |
| Bidding personality: Standard | 40% |
| Bidding personality: Bold | 20% |
| Bidding personality: Cautious | 20% |
| Bidding personality: Volatile | 20% |

---

## What Changed From the Original Proposal

The original "Bid Standardization" paper described a simpler mechanic. The simulator evolved it through implementation:

| Original | Current implementation |
|----------|----------------------|
| Only lottery/play-in teams participate | All 30 teams in the chip pool |
| Win returns your wager, loss deducts it | Pot mechanic: winner gains opponent's wager, loser loses own wager |
| Double requires finishing with >100 chips | Double is pre-assigned home night for all 30 teams, no chip threshold |
| Play-In consolation bonus (+7.5 chips) | Removed — chips are purely match-based |
| Chips can go negative | Floor at MIN_BET (10) — chips never go below the minimum bid |
| Flat 100 chips for all teams | Quintile starting chips: 100/80/60/40/20 by record rank (groups of 6) |
| Probabilistic lottery draw | Deterministic chip-standings draft order |
| Single strategy (bet big or small) | Three strategies: aggressive, standard, conservative |
| No variance beyond win probability | Four variance mechanics: hot streaks, personalities, fatigue, rally |
| No pick-swap modeling | ~25% of playoff teams modeled as swap-aware |

---

## Technical Files

| File | Purpose |
|------|---------|
| `engine/chip_window_sim.py` | Full 30-team simulation engine, all mechanics |
| `engine/lottery_sim.py` | Simplified `ChipWindow` class for 13-system comparison framework |
| `web/router.py` | `/chip-window`, `/chip-window/run`, `/leaderboard` routes |
| `web/templates/chip_window.html` | Standalone simulator UI |
| `web/templates/chip_leaderboard.html` | Three-tab leaderboard with trajectory chart and team detail |
| `web/templates/index.html` | System selector (short tag: "G60–G82 chip standings decide draft order.") |
| `web/static/lottery-lab.css` | All styles including personality pills, team detail panel |
