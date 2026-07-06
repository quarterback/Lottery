# Chip Window Simulator — Product Requirements Document

**Project:** Lottery Lab  
**Feature:** Chip Window (Bid Standardization)  
**Author:** Ron Bronson  
**Date:** April 2026  
**Status:** Implemented

---

## Background

The NBA draft lottery creates structural incentives for losing. Under the current system, the three teams with the worst records share the highest odds (14% each) for the first pick. A team that loses intentionally in a playoff race suffers no penalty — in fact, it improves their odds. This is commonly called "tanking."

The **Chip Window** is a proposed reform that makes tanking structurally impossible by replacing a team's draft lottery odds with a chip total they earn — or deplete — through late-season game performance. No team can improve their odds by losing. Losing costs chips regardless of intent.

This document describes the Chip Window simulator built into Lottery Lab.

---

## Goals

- Model the Chip Window mechanic faithfully across simulated seasons and real historical NBA standings
- Show how draft lottery odds would differ from the current system
- Visualize chip trajectories game-by-game so the "leaderboard" narrative is legible
- Allow comparison between Chip Window and other reform proposals in a common framework
- Serve as a reference implementation to accompany the "Bid Standardization" paper

---

## Non-Goals

- This is not a real-time system connected to live NBA data
- It does not model player-level performance, injuries, or trades
- It does not propose a specific implementation timeline or policy process
- It does not handle edge cases like play-in tournament seeding changes mid-window (a future enhancement)

---

## Core Mechanic

### The Chip Window

The chip window activates at **game 60** of the regular season (22 games remaining through game 82) for all teams outside the top 12 playoff seeds. This covers:

- **Play-In teams** (seeds 13–16): in the chip pool with a consolation bonus
- **Lottery teams** (seeds 17–30): in the chip pool with floor protection

Each eligible team starts the window with **100 chips**.

### Wagering

Each game, a team must wager a minimum of **10 chips**. They may choose to wager **25 chips** if they prefer. The simulator uses a "standard" strategy: bet 25 when chips ≥ 50, bet 10 when chips < 50 (conserving when depleted).

| Outcome | Effect |
|---------|--------|
| Win | +wager chips (chips increase) |
| Loss | −wager chips (chips decrease, floor at 0) |

Tanking is structurally impossible: a loss costs chips at the same rate whether it was intentional or not.

### Double Mechanic

Teams that finish the window with **more than 100 chips** (i.e., net-positive performance) may exercise a one-time double: their final chip total is multiplied by 2×. This rewards hot streaks with compounding upside.

### Play-In Consolation

Play-In teams that participate in the play-in tournament but fail to secure a playoff spot receive a **+7.5 chip consolation bonus**. This rewards play-in effort and acknowledges that play-in teams are close to the playoff line.

### Lottery Odds

Final lottery odds are proportional to each team's chip total, with a **floor equal to the team's current NBA odds** for their draft position (worst record = highest floor). The floor prevents double punishment — a team that has the worst record and depletes all chips still receives the odds they would have earned under the current NBA system. A team that accumulates chips above their floor can exceed those odds.

---

## Simulator Features

### 1. Standalone Chip Window Simulator (`/chip-window`)

A dedicated simulator page that runs a full 30-team NBA league across 5–15 seasons.

**Simulation engine:**
- Each team is assigned a talent rating (logistic win probability model)
- 60 pre-window games determine standings and chip-pool eligibility
- 22-game chip window runs for all non-safe-playoff teams
- Talent drifts slightly between seasons to model roster evolution
- Championship odds are talent-weighted (not chip-weighted) — the chip system only affects draft order, not actual playoff results
- Multi-season cumulative leaderboard tracks titles and playoff appearances

**Per-season display:**
- Season slider to browse individual simulated years
- Standings table with team status pills (Safe Playoff / Play-In / Lottery), 60-game record, final record, chip bar with 2× badge for doubled teams, and lottery odds percentage
- Inline SVG chip trajectory chart: one line per team, color-coded, with a dashed baseline at 100 chips showing pre-double performance across all 22 window games

**Cumulative leaderboard:**
- Sorted by total titles across all simulated seasons
- Shows playoff appearances and average chip total per season

### 2. Historical Season Analysis (via Lottery Lab Historical Mode)

When "Chip Window" is selected in the Historical NBA Seasons Analysis mode alongside a real historical season (2000–01 through 2025–26):

**Chip Window Leaderboard section:**
- 600 randomized chip-window scenarios per lottery team, using each team's full-season win percentage as a proxy for their game 60–82 performance
- Per-team chip range bar showing the p25–p75 spread and median
- Double Chance %: probability of finishing with >100 chips in a given scenario
- Inline sparkline trajectory showing median chip count across the 22-game window
- Teams sorted by median chips (leaderboard order)
- Transparent footnote: win% is used as a proxy since game-by-game historical records are not stored

**Comparison table:**
- Shows simulated pick distribution under the Chip Window alongside any other selected system
- Highlights divergence from actual historical lottery outcomes

### 3. System Comparison (via Lottery Lab Main Simulator)

Chip Window participates as one of 13 selectable systems in the main Monte Carlo comparison simulator. Users can run the Chip Window head-to-head against any other system (Current NBA, Flat Bottom, Play-In Boost, etc.) across 3–30 simulated seasons with 5–500 Monte Carlo runs.

System explainer panel includes:
- Full plain-English description of the mechanic
- Approximate odds table
- Note explaining the dynamic nature of chip-based odds

---

## Simulation Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Window start | Game 60 | 22 games remaining |
| Window length | 22 games | Games 61–82 |
| Starting chips | 100 | All eligible teams |
| Minimum bet | 10 chips | Per game |
| Optional bet | 25 chips | Per game |
| Standard strategy | Bet 25 if ≥50 chips, else 10 | Default used in simulator |
| Double threshold | >100 chips | Strict greater-than |
| Double effect | 2× chip total | Applied at window end |
| Play-In bonus | +7.5 chips | For play-in teams that miss playoffs |
| Floor | Current NBA odds for draft rank | Applied to all lottery teams |

---

## Design Decisions and Tradeoffs

**Win probability model:** The simulator uses a logistic function centered at 50 (on a 0–100 talent scale) with a spread of 8. This produces realistic win probability distributions without requiring real schedule data.

**Strategy assumption:** The simulator uses the "standard" strategy (bet big when healthy, conservative when depleted) as a reasonable middle ground. Aggressive (always bet 25) and conservative (always bet 10) strategies are supported in the simulation engine but not exposed as a user control yet.

**Historical seasons proxy:** For historical mode, each team's full-season win percentage is used as a proxy for their game 60–82 win rate. This is an approximation — a team's late-season performance can diverge from their season average — but it produces directionally correct results and correctly shows lottery teams depleting chips while bubble teams retain or accumulate them.

**Floor mechanic:** Without a floor, the worst teams in the lottery could theoretically receive lower odds under Chip Window than under the current NBA system (if they happen to lose all their chip window games). The floor prevents this, ensuring the system is strictly non-punitive for genuinely bad teams.

---

## What the Simulator Shows

The Chip Window simulator demonstrates three key properties of the system:

1. **Anti-tank:** Lottery teams with 18–28% win rates almost always deplete their chips (median final chips: 0). Their floor guarantees they keep their current NBA odds, but they cannot improve them by losing — chips only go down regardless of whether the loss is intentional.

2. **Late-season stakes:** Bubble teams (40–55% win rates) have meaningful chip ranges (p25–p75 spans can be 0–200+ chips) and significant double chances (15–35%). Every game in the window carries real consequences for their draft odds.

3. **Variance and narrative:** The chip trajectory chart makes each season's window a readable story — teams rising, falling, crossing the 100-chip baseline, triggering doubles. This is the "public leaderboard alongside the standings" that the paper describes as turning garbage-time games into must-watch TV.

---

## Technical Implementation

**Language/framework:** Python 3.11, FastAPI, Jinja2 templates  
**Files:**
- `engine/chip_window_sim.py` — standalone 30-team simulation engine
- `engine/lottery_sim.py` — `ChipWindow` class integrated into the 13-system comparison framework
- `web/router.py` — `/chip-window` GET and `/chip-window/run` POST endpoints; historical mode chip leaderboard computation
- `web/templates/chip_window.html` — standalone simulator page with SVG trajectory chart
- `web/templates/historical_results.html` — chip leaderboard section (conditionally rendered)

**Chip trajectory rendering:** Inline SVG polylines, no external chart library. Scales dynamically to the maximum chip value in the season.

---

## Future Enhancements

- **Betting strategy selector:** Let users choose between aggressive (always 25), conservative (always 10), and standard (adaptive) strategies and compare outcomes
- **Game-by-game historical data:** For recent seasons, store actual game results for the chip window period (games 60–82) to replace the win-rate proxy with real outcomes
- **Live integration:** During an active season, show current chip standings updated through the most recent game
- **Play-In strategy modeling:** Model teams near the 13–16 seed line differently — they have incentive to win for playoff seeding, not just chip accumulation
- **Public leaderboard mockup:** Visualize what the chip leaderboard would look like as a public-facing standings page alongside the traditional standings table
- **Export:** Allow downloading chip leaderboard results as CSV for further analysis
