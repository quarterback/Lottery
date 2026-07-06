# After Action Review — Task #43: Multi-Sport League Support

**Date:** April 2026  
**Task:** Add multi-sport league support (NHL, MLB, WNBA, PWHL, MLS) to Draft Lab  
**Outcome:** MERGED after 6 code-review cycles  

---

## What We Set Out to Do

Extend the Draft Lab lottery simulator to support 6 leagues (NBA, NHL, MLB, WNBA, PWHL, MLS) with correct team counts, playoff structures, schedule lengths, chip-window timing, and lottery configurations. The centerpiece was making the Chip Window Simulator — with all its charts, analytics, and UI labels — fully league-aware rather than hardwired to NBA assumptions.

---

## What Actually Happened (Round by Round)

### Rounds 1–2 — Backend foundation + initial UI wiring
**What worked:** `LeagueConfig` dataclass, six league configs, `chips_for_rank()` scaling, `SimResult` metadata fields, `renderAll()` consuming dynamic values.  
**What was missed:** `chip_window.html` JS chart math still hardcoded to NBA (22 nights, G60/G61/G82, 14 lottery teams).

### Round 3 — Playoff cutoff and route fixes
**What worked:** `_rank_by_wins_asc` accepting `playoff_spots`, `/historical` GET/POST passing leagues context, `results.html` using dynamic playoff cutoff.  
**What was missed:** `chip_window.html` JS not yet touched.

### Round 4 — Protocol and template pills
**What worked:** `LotterySystem.tank_incentive` Protocol updated for all 13 systems, `/chip-window` GET serving league pills from server via Jinja2 loop.  
**What was missed:** Still the same chip_window.html JS chart math.

### Round 5 — Chart and analytics parameterization (first attempt)
**What worked:** `cx()` scaling, x-axis ticks, Gini chart, timing chart, analytics loops all made dynamic using `simData.*` values.  
**What was rejected (missed):** Three backend issues surfaced that weren't on the radar yet: (1) `PLAY_IN_SLOTS = 4` hardcoded in `PlayInBoost.draft_order()`, (2) `lottery_picks` defined in `LeagueConfig` but never threaded into draft systems, (3) `chip_window_start` storing "games before window" when spec wanted "opening game number."

### Round 6 — Backend parameterization + semantic fix
**What worked:** All three backend issues resolved. `DraftConstraints` gained `play_in_slots` and `lottery_picks`, populated from `LeagueConfig` in `simulate_run()`. `PlayInBoost` and all six lottery draw calls use `constraints.lottery_picks`. `TopFourOnly` pool size is now dynamic. `chip_window_start` now stores the opening game number (NBA=61, not 60), with `games_before_wnd = lg.chip_window_start - 1` in the sim, and all `+1` compensations removed from the frontend.  
**Supplemental fix:** `make_bar_rows()` `top_n` default changed from hardcoded 14 to `cfg.lottery_teams` so NHL (16) and MLB (18) show all lottery teams in the pick-distribution table.

---

## What Went Well

- **`LeagueConfig` as a single source of truth** worked cleanly. Once all the right fields were in it and threaded through `DraftConstraints`, each downstream fix was mechanical.
- **`chips_for_rank()` fractional-breakpoint scaling** handled PWHL (6 teams) and WNBA (13 teams) without any special casing.
- **Chip Window sim's odd-team bye logic** generalized correctly — the reviewer never flagged it.
- **Frontend `renderAll()` update pattern** — injecting dynamic text into pre-rendered HTML elements via IDs after a sim runs — was the right call and kept the template clean.

---

## What Went Wrong

### 1. The chip_window.html audit was too shallow, too late
The JS chart math audit should have happened before Round 1 was submitted, not discovered through repeated rejections. The file had ~15 distinct places with hardcoded NBA values and they were only systematically found by running `grep` with the reviewer's explicit list as a guide.

**Fix going forward:** Before submitting any template change, run a `grep` for every numeric constant associated with the sport/league (e.g., `22`, `60`, `61`, `82`, `14`) and trace each one to "is this dynamic or hardcoded?"

### 2. `chip_window_start` semantics were ambiguous and stayed ambiguous too long
The field was defined as "games before window" (NBA=60) but the spec described it as the "opening game number" (G61). The frontend compensated with `+1` everywhere, creating a silent inconsistency that the reviewer caught in Round 6.

**Fix going forward:** Semantics for any "position in season" value should be locked to one convention at the schema level and documented in the dataclass docstring. Add an assertion or property that derives the other representation.

### 3. `DraftConstraints` wasn't extended alongside `LeagueConfig`
`play_in_slots` and `lottery_picks` were added to `LeagueConfig` in Round 1 but never added to `DraftConstraints` (the object actually passed to draft systems). The lottery systems couldn't use them even if they wanted to.

**Fix going forward:** When adding a field to a config dataclass that draft systems consume, immediately ask: "Does `DraftConstraints` also need this?" The constraint object is the bridge; the config is the source.

### 4. `make_bar_rows()` wasn't updated when lottery count became variable
A function with `top_n=14` (NBA lottery teams) was never flagged during the multi-league refactor because it wasn't in the "obvious" path. It only appeared in the final approved-with-comments pass.

**Fix going forward:** Search for any hardcoded numeric constant that equals `LOTTERY_TEAMS` when doing multi-league work.

---

## Metrics

| Cycle | Verdict | Primary gap |
|-------|---------|-------------|
| 1-2 | REJECTED | chip_window.html JS hardcoded |
| 3 | REJECTED | chip_window.html JS hardcoded |
| 4 | REJECTED | chip_window.html JS hardcoded |
| 5 | REJECTED | chip_window.html JS hardcoded |
| 6 | APPROVED_WITH_COMMENTS | make_bar_rows top_n + backend gaps |
| 6+ | MERGED | — |

Four consecutive rejections for the same root cause (chip_window.html JS) before it was fully audited.

---

## What to Do Differently Next Time

1. **Audit the full rendering stack before writing a line of code.** For any UI feature, grep the template for all hardcoded values, list them, and confirm each one is in scope before starting.

2. **Propagate config fields through all intermediary objects at the same time.** If `LeagueConfig` gains `foo`, update `DraftConstraints.foo` and every callsite that defaults `foo` in the same commit.

3. **Nail down field semantics in the docstring before using the field.** "Games before window" vs "opening game number" is a one-line comment that would have prevented a 6th round.

4. **Write a cross-league smoke test.** A single test that runs each of the 6 leagues through each lottery system and asserts correct playoff counts, lottery counts, and chip-window bounds would have caught issues before the reviewer did.

---

## Files Changed (Summary)

| File | Nature of change |
|------|-----------------|
| `engine/leagues.py` | Added `LeagueConfig`, 6 league configs, `chips_for_rank()` scaling; updated `chip_window_start` to opening game number |
| `engine/lottery_sim.py` | `DraftConstraints` gains `play_in_slots`/`lottery_picks`; all 13 systems use `constraints.lottery_picks`; `PlayInBoost` uses `constraints.play_in_slots`; `simulate_run()` populates from league |
| `engine/chip_window_sim.py` | League-aware team counts, playoff partitioning, chip-window timing; `games_before_wnd = chip_window_start - 1` |
| `web/router.py` | League threading through `/simulate`, `/chip-window/run`, `/historical`; `make_bar_rows()` `top_n` dynamic |
| `web/templates/chip_window.html` | All chart math, x-axis labels, analytics loops, static text, timing summary, table headers — fully parameterized from `simData.*` |
| `web/templates/results.html` | Dynamic playoff cutoff, league name in header, league preserved in rerun form |
| `web/templates/index.html` | League pill selector rendered from server context |
