# Chip Window — Model Reference

**Project:** Lottery Lab  
**Concept:** Ron Bronson — "Bid Standardization" (April 2026)  
**Document status:** Current implementation as of April 2026  
**Source of truth:** `engine/chip_window_sim.py`

---

## What It Is

The Chip Window is a proposed NBA draft reform that makes tanking structurally impossible. Instead of awarding lottery odds based on record, a team's draft odds are determined by chips they earn — or deplete — through head-to-head game results across the final 22 games of the regular season (Games 61–82).

Losing costs chips at the same rate regardless of whether the loss was intentional. There is no mechanism by which a team can improve their draft odds by losing.

---

## Who Participates

All 30 teams enter the chip pool. Teams are classified at game 60 based on their record:

| Status | Count | Role in chip window |
|--------|-------|---------------------|
| Safe Playoff | 12 | In pool; conservative strategy by default |
| Play-In | 8 | In pool; aggressive strategy (dual incentive: seeding + chips) |
| Lottery | 14 | In pool; strategy is user-selected; draft odds at stake |

The original proposal limited participation to non-playoff teams. The simulator extends it to all 30 teams because safe-playoff teams play these games too, and their betting behavior affects lottery team chip totals.

---

## The 22-Night Structure

Each night of the chip window, all 30 teams are randomly paired into 15 simultaneous head-to-head matchups. Home/away assignment is random per game. This runs for 22 nights (Games 61–82).

The schedule is generated once per season before the window opens. The full schedule is used to:
- Pre-select each lottery team's double game (their one designated home night)
- Pre-select fatigue nights for safe-playoff teams

---

## Chip Mechanics

### Starting state
Every team begins with **100 chips**.

### Wagering — the pot
Both teams in a matchup announce their wager before the outcome. When the game resolves:

- **Winner** gains the opponent's wager (net positive)  
- **Loser** loses their own wager (net negative)

Chips can go **negative**. There is no floor during the window. A team that loses enough games can end with negative chips.

### Wager sizing

Three strategies control how much a team bets each night:

| Strategy | Bet logic |
|----------|-----------|
| **Aggressive** | 30–60% of current chip stack per game. Big swings in both directions. |
| **Standard** | 15–40% of stack, proportional to chip total — rising with accumulated chips. |
| **Conservative** | 10–20 chips flat regardless of stack size. Low variance; slow gain or loss. |

The minimum wager is always **10 chips**. There is no cap.

Strategy assignments by team class:
- **Lottery teams** → user-selected strategy (choice presented in the simulator UI)
- **Play-In teams** → always aggressive (they need wins for seeding and chips)
- **Safe-Playoff teams** → always conservative by default

### The double

Each lottery team has one pre-assigned home night across the 22 games. On that night they may declare a **double**:

- Their wager is doubled for that game
- The opponent automatically responds with a fixed counter-wager of 25 chips
- The declaring team risks their doubled wager; gains 25 on a win
- No chip threshold is required — any lottery team can declare regardless of current chip total
- Each team can only double once

The double night is selected randomly before the window opens, not reactively by the team based on standings.

---

## Draft Odds Calculation

At the end of the 22-night window, lottery odds are computed as follows:

1. Lottery teams are sorted by final chip total (most chips = Pick 1 rank)
2. Each team's floor is their current NBA lottery odds for their draft slot (worst record = highest floor)
3. Effective weight for the proportional pool = `max(0, chips_end)` — negative chips clip to zero and receive floor odds only
4. Final odds = `max(floor_odds, proportional_chip_share)`

Teams that deplete their chips to zero or negative receive the odds they would have earned under the current NBA system. They cannot fall below that floor. Teams that accumulate chips above their starting position can exceed their floor odds proportionally.

---

## Variance Mechanics

Four variance mechanics were added to model real-world noise in the chip window. These are always active regardless of user strategy selection.

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

This is a background mechanic — it affects chip outcomes but does not change the core draft-odds calculation. It models a real-world dynamic where contending teams are not indifferent to lottery team performance. It is not emphasized in the UI because it affects a minority of games and is an edge case relative to the core model.

---

## Strategy Comparison Summary

| Strategy | Typical chip range (14-team lottery field) | Best for |
|----------|-------------------------------------------|----------|
| Aggressive | High variance; can reach 200+ or go deeply negative | Teams trying to climb the chip board |
| Standard | Moderate variance; tracks proportional to win rate | Balanced play across all standings positions |
| Conservative | Low variance; rarely breaks 150, rarely goes below 50 | Teams protecting a chip lead |

Because lottery odds are proportional to the field, strategy choice only matters relative to what opponents are doing. A conservative team in an aggressive field accumulates fewer chips than average; an aggressive team in a conservative field accumulates more.

---

## Leaderboard Display

The Chip Window Leaderboard (`/leaderboard`) shows the results of a simulated season across three tabs.

### Tab 1 — Leaderboard

All 30 teams ranked by final chip total within their status group. Columns:
- Team name + status pill (Safe Playoff / Play-In / Lottery)
- Strategy pill (user strategy for lottery; fixed for others)
- **Bidding personality pill** — color-coded: orange = Bold, teal = Cautious, purple = Volatile, grey = Standard
- Record through game 60 and chip W-L during the window
- Current chip total with a bar visualization; 2× badge for doubled teams
- Lottery odds % (for lottery teams)

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
- Chip stats: starting chips, final chips, chip W-L, lottery odds, chip draft rank
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
8. Near-floor (lottery team at or below starting chips) → Floor narrative
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
| Starting chips | 100 |
| Minimum bet | 10 chips |
| Aggressive range | 30–60% of stack |
| Standard range | 15–40% of stack (proportional) |
| Conservative range | 10–20 chips flat |
| Double mechanic | One pre-selected home game per lottery team; no chip minimum |
| Double opponent response | Fixed 25 chips |
| Chip floor during window | None (chips can go negative) |
| Draft odds floor | Record-based current NBA odds |
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
| Double requires finishing with >100 chips | Double is pre-assigned home night, no chip threshold |
| Play-In consolation bonus (+7.5 chips) | Removed — chips are purely match-based |
| Floor at 0 chips | Floor at current NBA odds; chips can go negative during window |
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
| `web/templates/index.html` | System selector (short tag: "G60–G82 chip bets decide lottery order.") |
| `web/static/lottery-lab.css` | All styles including personality pills, team detail panel |
