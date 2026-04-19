from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Optional

from engine.leagues import LeagueConfig, NBA_CONFIG, chips_for_rank as _league_chips_for_rank
from engine.lottery_sim import NBA_TEAM_NAMES

# ── Constants (NBA defaults — kept for backward compatibility) ────────────────
GAMES_BEFORE_WINDOW = 60
GAMES_IN_WINDOW = 22
TOTAL_GAMES = 82
MIN_BET = 10.0
BIG_BET = 25.0
DOUBLE_THRESHOLD = 100.0   # reference line for trajectory chart only; NOT a double eligibility requirement
PLAY_IN_BONUS = 7.5        # consolation for play-in teams that miss playoffs

def _chips_for_rank(rank_0: int, n_teams: int = 30) -> float:
    """Starting chips by zero-based rank (0=worst), scaled to league team count."""
    return _league_chips_for_rank(rank_0, n_teams)

SAFE_PLAYOFF_COUNT = 12
PLAY_IN_COUNT = 8
PLAYOFF_COUNT = 16
LOTTERY_COUNT = 14

# NBA lottery odds (slot 0 = worst record → slot 13 = best non-playoff)
NBA_ODDS = [14.0, 14.0, 14.0, 12.5, 10.5, 9.0, 7.5, 6.0, 4.5, 3.0, 2.0, 1.5, 1.0, 0.5]

STATUS_SAFE   = "Safe Playoff"
STATUS_PLAYIN = "Play-In"
STATUS_LOTTERY = "Lottery"

VALID_STRATEGIES = ("standard", "aggressive", "conservative")

# ── Lottery behavior shift ───────────────────────────────────────────────────
# At game 60, lottery teams stop tanking and start trying: G-League call-ups,
# vet signings, real effort.  Two tiers by record rank within the lottery:
#
#   Bottom 7 (worst records, picks 1–7 territory):
#     Wide variance — some bottom teams dramatically improve, some don't.
#     Range 5–25 creates a relegation/promotion feel.
#
#   Top 7 (middling lottery, vying for play-in bubble):
#     Small nudge only — these teams are closer to .500 already.
#     Range 5–7.
LOTTERY_SHIFT_WORST_MIN  = 5.0
LOTTERY_SHIFT_WORST_MAX  = 25.0
LOTTERY_SHIFT_MIDDLE_MIN = 5.0
LOTTERY_SHIFT_MIDDLE_MAX = 7.0

# Placeholder tip-off slots (cycled for 15 games/night)
_TIP_TIMES = [
    "7:00 PM ET", "7:30 PM ET", "7:30 PM ET", "8:00 PM ET", "8:00 PM ET",
    "8:30 PM ET", "9:00 PM ET", "9:30 PM ET", "10:00 PM ET", "10:30 PM ET",
    "7:00 PM ET", "7:30 PM ET", "8:00 PM ET", "9:00 PM ET", "10:00 PM ET",
]


# ── Win-probability helpers ──────────────────────────────────────────────────

def _win_prob(talent: float) -> float:
    """Logistic win rate. Scale=14 calibrated to real NBA:
    talent 76 ≈ 84% (≈ 69 wins), talent 50 = 50% (41 wins), talent 18 ≈ 15% (12 wins).
    """
    return 1.0 / (1.0 + math.exp(-(talent - 50.0) / 14.0))


def _h2h_prob(talent_a: float, talent_b: float) -> float:
    """Head-to-head win probability for team A vs team B (log5 formula)."""
    wp_a = _win_prob(talent_a)
    wp_b = _win_prob(talent_b)
    denom = wp_a * (1.0 - wp_b) + wp_b * (1.0 - wp_a)
    return (wp_a * (1.0 - wp_b)) / denom if denom > 0.0 else 0.5


def _simulate_60_games(talent: float, rng: random.Random, games_before: int = GAMES_BEFORE_WINDOW) -> tuple[int, int]:
    wp = _win_prob(talent)
    wins = sum(1 for _ in range(games_before) if rng.random() < wp)
    return wins, games_before - wins


def _pick_bet(chips: float, strategy: str, rng: random.Random,
              personality: str = "standard") -> float:
    """Choose wager. Floor is MIN_BET (10). Cap is the team's current chip total.

    Analytics teams bid with 2-decimal precision to minimise the chance of
    finishing with an identical chip total as a rival. Exact ties are extremely
    rare as a result — each team's running sum traces a slightly different path.

    personality: "standard" | "bold" | "cautious" | "volatile"
      Applied as a multiplier on the base bet AFTER strategy calculation.
    """
    available = max(chips, MIN_BET)   # effective ceiling; floor always MIN_BET

    if strategy == "aggressive":
        # Bid 30–60% of stack — big swings, scales with chip count
        frac = rng.uniform(0.30, 0.60)
        base = available * frac
    elif strategy == "conservative":
        # Bid low flat: 10–20 chips regardless of stack size
        base = MIN_BET + rng.uniform(0, 10)
    else:
        # Standard: proportional momentum — 15–40% of stack, rising with chip count
        t = max(0.0, min(chips, 300.0)) / 300.0
        frac = 0.15 + 0.25 * t
        base = max(MIN_BET, available * frac)

    noise = rng.gauss(0, 2.0)
    raw = max(MIN_BET, min(available, base + noise))

    # Apply bidding personality multiplier
    if personality == "bold":
        mult = rng.uniform(1.25, 1.50)
    elif personality == "cautious":
        mult = rng.uniform(0.60, 0.80)
    elif personality == "volatile":
        # Randomly pick bold or cautious each game
        if rng.random() < 0.5:
            mult = rng.uniform(1.25, 1.50)
        else:
            mult = rng.uniform(0.60, 0.80)
    else:
        mult = 1.0

    # 2-decimal precision: analytics teams vary bids finely to avoid chip ties
    return round(max(MIN_BET, min(available, raw * mult)), 2)



# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class SeasonSummary:
    season_num: int
    teams: list[dict]
    champion_id: int
    playoff_ids: list[int]
    schedule: list[list[dict]]   # 22 nights × 15 matchups


@dataclass
class SimResult:
    seasons: list[SeasonSummary]
    leaderboard: list[dict]
    seed: int
    seasons_count: int
    strategy: str = "standard"
    league_id: str = "nba"
    league_name: str = "NBA"
    num_teams: int = 30
    chip_window_start: int = 60
    chip_window_length: int = 22
    games_per_season: int = 82


# ── Main simulation ──────────────────────────────────────────────────────────

def simulate_chip_window_league(
    seasons: int = 10,
    seed: Optional[int] = None,
    strategy: str = "standard",
    league: Optional[LeagueConfig] = None,
) -> SimResult:
    """
    Simulate seasons × n-team league with the Bid Standardization chip window.

    Mechanics (paper-accurate):
    ─ ALL n teams participate in the chip pool.
    ─ chip_window_length-night chip window: each night, teams are randomly paired.
    ─ Starting chips by record at game chip_window_start:
        Scaled proportionally to 7 tiers [140/120/100/80/60/40/20].
    ─ Pot mechanic: both teams announce wagers; winner gains opponent's wager
      (net); loser loses own wager. Chips clamped at MIN_BET (10) — never negative.
    ─ Analytics bidding: bets use 2-decimal precision to minimise ties.
      Ties in final chip totals are broken by worse record (fewer wins).
    ─ Double: home team may declare their pre-assigned home night as the double.
      Both teams wager normally; the winner earns 2× the opponent's wager (payout
      multiplier only). Loser's own deduction stays at 1×.
    ─ Draft order: lottery teams sorted by chips DESC → Pick 1..n_lottery.
      Fully deterministic. Remaining picks by record.
    ─ Strategy assignments:
        Lottery   → user-selected strategy
        Play-In   → always aggressive (dual incentive: seeding + chips)
        Safe PO   → conservative by default; ~25% are "pick swap holders"
                    who bid aggressively vs. lottery opponents
    """
    lg = league or NBA_CONFIG
    n_teams          = lg.num_teams
    games_before_wnd = lg.chip_window_start
    games_in_wnd     = lg.chip_window_length
    playoff_count    = lg.playoff_spots
    safe_count       = lg.safe_playoff_count
    play_in_count    = lg.play_in_count
    team_names       = lg.team_names

    if strategy not in VALID_STRATEGIES:
        strategy = "standard"
    if seed is None:
        seed = random.randint(0, 999_999)

    rng = random.Random(seed)

    # Initial talent distribution: gauss(50,10) clipped [18,76]
    talents: list[float] = []
    for _ in range(n_teams):
        talents.append(max(18.0, min(76.0, rng.gauss(50, 10))))
    talents.sort(reverse=True)

    titles: dict[int, int]        = {i: 0   for i in range(n_teams)}
    playoff_apps: dict[int, int]  = {i: 0   for i in range(n_teams)}
    total_chips_sum: dict[int, float] = {i: 0.0 for i in range(n_teams)}

    season_summaries: list[SeasonSummary] = []

    for season_idx in range(seasons):

        # ── Build team records for this season ──────────────────────────────
        team_data: list[dict] = []
        for i in range(n_teams):
            t = max(18.0, min(76.0, talents[i] + rng.gauss(0, 2.5)))
            w60, l60 = _simulate_60_games(t, rng, games_before=games_before_wnd)
            team_data.append({
                "id":              i,
                "name":            team_names[i] if i < len(team_names) else f"Team {i}",
                "talent":          round(t, 1),
                "wins_60":         w60,
                "losses_60":       l60,
                "status":          "",
                "in_chip_pool":    True,   # ALL 30 teams participate
                "chips_start":     0.0,    # filled in after game-60 quintile assignment
                "chips_end":       0.0,    # filled in after game-60 quintile assignment
                "chip_trajectory": [],
                "chip_wins":       0,
                "chip_losses":     0,
                "doubled":         False,
                "double_night":    -1,
                "final_wins":      w60,
                "final_losses":    l60,
                "playoff":         False,
                "lottery_odds":    0.0,
                "chip_draft_rank": None,
                "chip_pick":       None,
                "is_pick_swap_holder": False,
                "chip_gap_up":     None,
                "chip_gap_down":   None,
                "chip_gap_down_team": None,
                "strategy":        "standard",
                # Variance fields (populated after status classification)
                "bidding_personality": "standard",
                "has_hot_streak":      False,
                "hot_streak_nights":   None,   # {"start": int, "end": int}
                "hot_streak_boost":    0.0,
                "fatigue_nights":      [],
                "rally_mode":          False,
                "rally_mode_night":    None,
                "behavior_shift":      0.0,   # talent boost during chip window (lottery only)
            })

        # ── Classify status by wins through game chip_window_start ─────────
        by_wins = sorted(team_data, key=lambda t: t["wins_60"], reverse=True)
        for rank, td in enumerate(by_wins):
            if rank < safe_count:
                td["status"] = STATUS_SAFE
            elif rank < playoff_count:
                td["status"] = STATUS_PLAYIN
            else:
                td["status"] = STATUS_LOTTERY

        # ── Lottery behavior shift — two tiers by record rank within lottery ──
        # Sort lottery teams worst → best so we can assign bottom-7 vs top-7.
        lottery_teams = sorted(
            [td for td in team_data if td["status"] == STATUS_LOTTERY],
            key=lambda t: (t["wins_60"], -t["losses_60"], t["id"]),
        )
        for rank_0, td in enumerate(lottery_teams):
            if rank_0 < len(lottery_teams) // 2:
                # Bottom half: widest variance (worst records, picks 1-7 territory)
                lo, hi = LOTTERY_SHIFT_WORST_MIN, LOTTERY_SHIFT_WORST_MAX
            else:
                # Top half: tighter band (middling lottery, near play-in bubble)
                lo, hi = LOTTERY_SHIFT_MIDDLE_MIN, LOTTERY_SHIFT_MIDDLE_MAX
            td["behavior_shift"] = round(rng.uniform(lo, hi), 1)

        # ── Starting chips (all 30 teams, worst → best record at G60) ────────
        # Worst 3 → 140, next 3 → 120, next 3 → 100, next 3 → 80, next 6 → 60, next 6 → 40, best 6 → 20.
        # Ties in wins_60 broken by more losses (worse) → lower rank → more chips,
        # then by team id (stable deterministic tie-break).
        by_wins_asc = sorted(
            team_data,
            key=lambda t: (t["wins_60"], -t.get("losses_60", 0), t["id"]),
        )
        for rank_0, td in enumerate(by_wins_asc):
            start = _chips_for_rank(rank_0, n_teams)
            td["chips_start"] = start
            td["chips_end"]   = start

        # ── Assign strategies ────────────────────────────────────────────────
        for td in team_data:
            if td["status"] == STATUS_PLAYIN:
                td["strategy"] = "aggressive"
            elif td["status"] == STATUS_SAFE:
                # ~25% of safe-playoff teams model pick-swap exposure.
                # Their BASE strategy is conservative; they go aggressive only
                # when matched against a lottery opponent (handled per-matchup below).
                td["is_pick_swap_holder"] = rng.random() < 0.25
                td["strategy"] = "conservative"
            else:
                td["strategy"] = strategy   # lottery: user-chosen

        # ── Variance mechanics setup ─────────────────────────────────────────

        # 1. Bidding personality — assigned to ALL teams; independent of strategy
        _PERSONALITIES = ["standard", "bold", "cautious", "volatile"]
        _PERS_WEIGHTS   = [0.40, 0.20, 0.20, 0.20]
        for td in team_data:
            r = rng.random()
            cumul = 0.0
            for pers, w in zip(_PERSONALITIES, _PERS_WEIGHTS):
                cumul += w
                if r < cumul:
                    td["bidding_personality"] = pers
                    break

        # 2. Hot streak — ~20% of lottery+play-in teams get a surge window
        eligible_for_streak = [td for td in team_data
                                if td["status"] in (STATUS_LOTTERY, STATUS_PLAYIN)]
        for td in eligible_for_streak:
            if rng.random() < 0.20:
                td["has_hot_streak"]   = True
                start = rng.randint(0, max(0, games_in_wnd - 5))
                length = rng.randint(min(5, games_in_wnd), min(8, games_in_wnd))
                end = min(start + length - 1, games_in_wnd - 1)
                td["hot_streak_nights"] = {"start": start, "end": end}
                td["hot_streak_boost"]  = round(rng.uniform(0.08, 0.15), 3)

        # 3. Playoff fatigue — ~30% of chip-window games for safe-playoff teams
        safe_teams = [td for td in team_data if td["status"] == STATUS_SAFE]
        # We'll determine home nights per team once pairings are built; for now
        # store a target fatigue fraction and resolve actual nights after pairings.
        _FATIGUE_FRAC = 0.30

        # ── Build chip-window-length night random pairings ───────────────────
        ids = [td["id"] for td in team_data]
        team_by_id = {td["id"]: td for td in team_data}

        # For odd-team leagues, one team gets a bye each night (the last in the shuffle)
        pair_count = n_teams // 2
        night_pairings: list[list[tuple[int, int]]] = []
        for _ in range(games_in_wnd):
            shuffled = ids[:]
            rng.shuffle(shuffled)
            pairs: list[tuple[int, int]] = []
            for i in range(0, pair_count * 2, 2):
                a, b = shuffled[i], shuffled[i + 1]
                home = a if rng.random() < 0.5 else b
                away = b if home == a else a
                pairs.append((home, away))
            night_pairings.append(pairs)

        # ── Pre-select each team's double game (one home game, randomly) ────────
        # All 30 teams get a pre-assigned home night where they may declare a double.
        # Nobody knows their final status until game 82 — so every team plans ahead.
        # We scan all pairings up front and choose randomly among home-game nights.
        double_night_plan: dict[int, int] = {}
        for tid in ids:
            home_nights = [
                ni for ni, pairs in enumerate(night_pairings)
                if any(home == tid for home, away in pairs)
            ]
            if home_nights:
                double_night_plan[tid] = rng.choice(home_nights)

        # ── Playoff fatigue night resolution ─────────────────────────────────
        # Now that pairings are fixed, pick ~30% of each safe-playoff team's
        # 22 chip-window nights as fatigue/rest nights.
        for td in team_data:
            if td["status"] == STATUS_SAFE:
                all_nights = list(range(games_in_wnd))
                k = max(1, round(games_in_wnd * _FATIGUE_FRAC))
                td["fatigue_nights"] = sorted(rng.sample(all_nights, k))

        # ── Chip window simulation (night-by-night) ──────────────────────────
        chips:        dict[int, float]       = {td["id"]: td["chips_start"] for td in team_data}
        dbl_tracker:  dict[int, bool]        = {i: False          for i in ids}
        trajectories: dict[int, list[float]] = {i: []             for i in ids}
        chip_wins:         dict[int, int]         = {i: 0  for i in ids}
        chip_losses:       dict[int, int]         = {i: 0  for i in ids}
        upset_bonus_total: dict[int, float]       = {i: 0.0 for i in ids}
        opp_wagers:        dict[int, list[float]] = {i: []  for i in ids}

        full_schedule: list[list[dict]] = []

        for night_idx, pairs in enumerate(night_pairings):
            night_results: list[dict] = []

            # ── Live lottery chip rankings for narrative context (pre-night chips) ──
            lottery_sorted_now = sorted(
                [t["id"] for t in team_data if t["status"] == STATUS_LOTTERY],
                key=lambda tid: -chips[tid],
            )
            running_ranks: dict[int, int] = {
                tid: i + 1 for i, tid in enumerate(lottery_sorted_now)
            }

            for slot_idx, (home_id, away_id) in enumerate(pairs):
                home_td = team_by_id[home_id]
                away_td = team_by_id[away_id]

                home_chips_before = chips[home_id]
                away_chips_before = chips[away_id]

                # ── Double declaration ────────────────────────────────────────
                # Rule: the HOME team may declare on their pre-assigned night.
                # All 30 teams have a designated home night; status doesn't matter.
                # Away team never declares (only home team has this right).
                home_dbl = (
                    double_night_plan.get(home_id) == night_idx
                    and not dbl_tracker[home_id]   # safety — only once
                )
                away_dbl = False   # away team is never the declarer

                if home_dbl:
                    dbl_tracker[home_id]    = True
                    home_td["doubled"]      = True
                    home_td["double_night"] = night_idx

                # ── Effective strategy per matchup ────────────────────────────
                # Pick-swap holders are conservative by default but go aggressive
                # when they face a lottery opponent (protecting their draft position).
                home_strat = home_td["strategy"]
                away_strat = away_td["strategy"]
                if home_td["is_pick_swap_holder"] and away_td["status"] == STATUS_LOTTERY:
                    home_strat = "aggressive"
                if away_td["is_pick_swap_holder"] and home_td["status"] == STATUS_LOTTERY:
                    away_strat = "aggressive"

                # Rally mode overrides strategy to aggressive for floor teams
                if home_td["rally_mode"]:
                    home_strat = "aggressive"
                if away_td["rally_mode"]:
                    away_strat = "aggressive"

                # ── Wagers (with bidding personality applied) ─────────────────
                home_base  = _pick_bet(chips[home_id], home_strat, rng,
                                       home_td["bidding_personality"])
                away_base  = _pick_bet(chips[away_id], away_strat, rng,
                                       away_td["bidding_personality"])

                # Double is a payout multiplier only — both teams wager normally.
                # The home team declares which home game to use; winner gets 2× opponent's wager.
                home_wager = home_base
                away_wager = away_base

                pot = home_wager + away_wager

                # ── Variance: compute flags for this matchup ──────────────────
                home_hs = home_td["has_hot_streak"] and home_td["hot_streak_nights"] is not None and \
                          home_td["hot_streak_nights"]["start"] <= night_idx <= home_td["hot_streak_nights"]["end"]
                away_hs = away_td["has_hot_streak"] and away_td["hot_streak_nights"] is not None and \
                          away_td["hot_streak_nights"]["start"] <= night_idx <= away_td["hot_streak_nights"]["end"]

                home_fatigue = night_idx in home_td["fatigue_nights"]
                away_fatigue = night_idx in away_td["fatigue_nights"]

                # ── Head-to-head outcome (with variance adjustments) ──────────
                # Lottery teams get an effective talent boost: they're actually
                # trying to win now (G-League call-ups, vet signings, real effort).
                home_eff = home_td["talent"] + home_td.get("behavior_shift", 0.0)
                away_eff = away_td["talent"] + away_td.get("behavior_shift", 0.0)
                p_home = _h2h_prob(home_eff, away_eff)
                # Hot streak boost
                if home_hs:
                    p_home = min(0.95, p_home + home_td["hot_streak_boost"])
                if away_hs:
                    p_home = max(0.05, p_home - away_td["hot_streak_boost"])
                # Rally mode boost (+4%)
                if home_td["rally_mode"]:
                    p_home = min(0.95, p_home + 0.04)
                if away_td["rally_mode"]:
                    p_home = max(0.05, p_home - 0.04)
                # Playoff fatigue discount (-10pp for the fatigued team)
                if home_fatigue:
                    p_home = max(0.05, p_home - 0.10)
                if away_fatigue:
                    p_home = min(0.95, p_home + 0.10)

                home_won = rng.random() < p_home

                # ── Pot mechanic: winner += opp_wager (×2 on double night) ──
                # loser -= own_wager (always 1×). Chips clamped at MIN_BET (10).
                dbl_mult = 2.0 if home_dbl else 1.0
                if home_won:
                    chips[home_id] += away_wager * dbl_mult
                    chips[away_id]  = max(MIN_BET, chips[away_id] - away_wager)
                    winner_id = home_id
                    chip_wins[home_id]   += 1
                    chip_losses[away_id] += 1
                else:
                    chips[away_id] += home_wager * dbl_mult
                    chips[home_id]  = max(MIN_BET, chips[home_id] - home_wager)
                    winner_id = away_id
                    chip_wins[away_id]   += 1
                    chip_losses[home_id] += 1

                # ── Upset bonus: lower-record winner earns bonus = win-gap ────
                # bonus_chips = loser_wins_60 - winner_wins_60  (only when positive)
                if home_won:
                    win_gap = away_td["wins_60"] - home_td["wins_60"]
                else:
                    win_gap = home_td["wins_60"] - away_td["wins_60"]
                upset_bonus = max(0, win_gap)
                if upset_bonus > 0:
                    chips[winner_id] += upset_bonus
                    upset_bonus_total[winner_id] += upset_bonus

                # Track what each team's opponent wagered (for opponent_wagers list)
                opp_wagers[home_id].append(round(away_wager, 1))
                opp_wagers[away_id].append(round(home_wager, 1))

                # ── Build narrative using live chip rankings (pre-night) ──────
                narrative = _build_narrative(
                    home_td, away_td,
                    home_chips_before, away_chips_before,
                    home_wager, away_wager,
                    home_dbl, away_dbl,
                    night_idx,
                    running_ranks,
                    home_hot_streak=home_hs,
                    away_hot_streak=away_hs,
                    home_fatigue=home_fatigue,
                    away_fatigue=away_fatigue,
                )

                night_results.append({
                    "home_id":                home_id,
                    "away_id":                away_id,
                    "home_name":              home_td["name"],
                    "away_name":              away_td["name"],
                    "home_status":            home_td["status"],
                    "away_status":            away_td["status"],
                    "home_is_pick_swap":      home_td["is_pick_swap_holder"],
                    "away_is_pick_swap":      away_td["is_pick_swap_holder"],
                    "home_strategy":          home_td["strategy"],
                    "away_strategy":          away_td["strategy"],
                    "home_bidding_personality": home_td["bidding_personality"],
                    "away_bidding_personality": away_td["bidding_personality"],
                    "home_wager":             home_wager,
                    "away_wager":             away_wager,
                    "pot":                    pot,
                    "home_won":               home_won,
                    "winner_id":              winner_id,
                    "home_double":            home_dbl,
                    "away_double":            away_dbl,
                    "home_chips_before":      round(home_chips_before, 1),
                    "away_chips_before":      round(away_chips_before, 1),
                    "home_chips_after":       round(chips[home_id], 1),
                    "away_chips_after":       round(chips[away_id], 1),
                    "tip_time":               _TIP_TIMES[slot_idx % len(_TIP_TIMES)],
                    "narrative":              narrative,
                    # Upset bonus: 0 if no upset, otherwise = win-gap chips awarded to winner
                    "upset_bonus":            upset_bonus,
                    # Variance fields
                    "home_hot_streak":        home_hs,
                    "away_hot_streak":        away_hs,
                    "home_fatigue":           home_fatigue,
                    "away_fatigue":           away_fatigue,
                    "home_rally":             home_td["rally_mode"],
                    "away_rally":             away_td["rally_mode"],
                })

            full_schedule.append(night_results)

            # Record trajectory for ALL teams after this night
            for tid in ids:
                trajectories[tid].append(round(chips[tid], 1))

            # ── Rally mode check (post-night) ─────────────────────────────────
            # Flip lottery teams into rally mode if chips ≤ 20 and enough nights remain.
            nights_remaining = games_in_wnd - 1 - night_idx  # nights after this one
            rally_threshold = max(2, games_in_wnd // 2)
            if nights_remaining >= rally_threshold:
                for td in team_data:
                    if (td["status"] == STATUS_LOTTERY
                            and not td["rally_mode"]
                            and chips[td["id"]] <= 20.0):
                        td["rally_mode"]      = True
                        td["rally_mode_night"] = night_idx + 1  # first night it takes effect

        # (Play-in consolation bonus removed — chips are purely match-based)

        # ── Finalize team chip data ──────────────────────────────────────────
        # Build tonight lookup from final chip-window night (night 22 = schedule[-1])
        final_night = full_schedule[-1] if full_schedule else []
        tonight_by_team: dict[int, dict] = {}
        for m in final_night:
            tonight_by_team[m["home_id"]] = m
            tonight_by_team[m["away_id"]] = m

        for td in team_data:
            tid = td["id"]
            td["chips_end"]          = round(chips[tid], 1)
            td["chip_trajectory"]    = trajectories[tid]
            td["chip_wins"]          = chip_wins[tid]
            td["chip_losses"]        = chip_losses[tid]
            td["total_upset_bonus"]  = round(upset_bonus_total[tid], 1)
            td["final_wins"]         = td["wins_60"] + chip_wins[tid]
            td["final_losses"]       = td["losses_60"] + chip_losses[tid]
            td["opponent_wagers"]    = opp_wagers[tid]
            total_chips_sum[tid]    += td["chips_end"]

            # tonight_* fields — based on the final night of the chip window (G82)
            m = tonight_by_team.get(tid)
            if m:
                is_home = m["home_id"] == tid
                td["tonight_opponent"]  = m["away_name"]  if is_home else m["home_name"]
                td["tonight_wager"]     = round(m["home_wager"]  if is_home else m["away_wager"], 1)
                td["tonight_opp_wager"] = round(m["away_wager"]  if is_home else m["home_wager"], 1)
                td["tonight_pot"]       = round(m["pot"], 1)
                td["tonight_double"]    = m["home_double"] if is_home else False
            else:
                td["tonight_opponent"]  = None
                td["tonight_wager"]     = None
                td["tonight_opp_wager"] = None
                td["tonight_pot"]       = None
                td["tonight_double"]    = False

        # ── Chip draft rank (most chips = Pick 1 among lottery teams) ────────
        # Fully deterministic: sort by chips DESC, then wins_60 ASC (worse record
        # wins tie), then team id as stable tiebreaker (coin-flip proxy).
        lottery_teams = [td for td in team_data if td["status"] == STATUS_LOTTERY]
        lottery_by_chips = sorted(
            lottery_teams,
            key=lambda t: (-t["chips_end"], t["wins_60"], t["id"]),
        )
        for rank, td in enumerate(lottery_by_chips):
            td["chip_draft_rank"] = rank + 1
            td["chip_pick"]       = rank + 1

        for i, td in enumerate(lottery_by_chips):
            if i == 0:
                td["chip_gap_up"]        = None
                td["chip_gap_up_team"]   = None
            else:
                above = lottery_by_chips[i - 1]
                td["chip_gap_up"]      = round(above["chips_end"] - td["chips_end"], 1)
                td["chip_gap_up_team"] = above["name"]

            if i == len(lottery_by_chips) - 1:
                td["chip_gap_down"]      = None
                td["chip_gap_down_team"] = None
            else:
                below = lottery_by_chips[i + 1]
                td["chip_gap_down"]      = round(td["chips_end"] - below["chips_end"], 1)
                td["chip_gap_down_team"] = below["name"]

        # ── Final standings by total wins ────────────────────────────────────
        final_sorted = sorted(team_data, key=lambda t: t["final_wins"], reverse=True)
        for rank, td in enumerate(final_sorted):
            td["final_rank"] = rank + 1
            if rank < playoff_count:
                td["playoff"] = True
                playoff_apps[td["id"]] += 1

        # ── Champion (weighted by talent among playoff qualifiers) ────────────
        playoff_pool = [td for td in team_data if td["playoff"]]
        weights      = [max(0.5, td["talent"]) for td in playoff_pool]
        total_w      = sum(weights)
        r = rng.uniform(0, total_w)
        cumulative = 0.0
        champion_id = playoff_pool[0]["id"]
        for td, w in zip(playoff_pool, weights):
            cumulative += w
            if r <= cumulative:
                champion_id = td["id"]
                break
        titles[champion_id] += 1

        season_summaries.append(SeasonSummary(
            season_num  = season_idx + 1,
            teams       = list(team_data),
            champion_id = champion_id,
            playoff_ids = [td["id"] for td in team_data if td["playoff"]],
            schedule    = full_schedule,
        ))

        # ── Talent evolution (season-to-season) ──────────────────────────────
        for i in range(n_teams):
            talents[i] = max(18.0, min(76.0, talents[i] + rng.gauss(0, 1.5)))

    # ── Cumulative leaderboard ───────────────────────────────────────────────
    leaderboard = []
    for i in range(n_teams):
        avg_chips = round(total_chips_sum[i] / seasons, 1)
        leaderboard.append({
            "id":       i,
            "name":     team_names[i] if i < len(team_names) else f"Team {i}",
            "titles":   titles[i],
            "playoffs": playoff_apps[i],
            "avg_chips": avg_chips,
        })
    leaderboard.sort(key=lambda r: (r["titles"], r["playoffs"]), reverse=True)

    return SimResult(
        seasons            = season_summaries,
        leaderboard        = leaderboard,
        seed               = seed,
        seasons_count      = seasons,
        strategy           = strategy,
        league_id          = lg.id,
        league_name        = lg.name,
        num_teams          = n_teams,
        chip_window_start  = games_before_wnd,
        chip_window_length = games_in_wnd,
        games_per_season   = games_before_wnd + games_in_wnd,
    )


# ── Narrative helper ─────────────────────────────────────────────────────────

def _build_narrative(
    home_td: dict, away_td: dict,
    home_chips: float, away_chips: float,
    home_wager: float, away_wager: float,
    home_dbl: bool, away_dbl: bool,
    night_idx: int,
    running_ranks: dict[int, int] | None = None,
    home_hot_streak: bool = False,
    away_hot_streak: bool = False,
    home_fatigue: bool = False,
    away_fatigue: bool = False,
) -> str:
    """Generate a short game narrative string.

    running_ranks: live chip rankings computed at the start of this night
    (lottery teams only; keyed by team id → 1-indexed rank among lottery teams).
    """
    home_name = home_td["name"]
    away_name = away_td["name"]
    home_id   = home_td["id"]
    away_id   = away_td["id"]
    # Use live running ranks (accurate at game time) — not end-of-season chip_draft_rank
    home_rank = (running_ranks or {}).get(home_id)
    away_rank = (running_ranks or {}).get(away_id)

    home_is_lottery = home_td["status"] == STATUS_LOTTERY
    away_is_lottery = away_td["status"] == STATUS_LOTTERY
    home_in_rally   = home_td.get("rally_mode", False)
    away_in_rally   = away_td.get("rally_mode", False)

    if home_dbl:
        if home_rank and home_rank > 1:
            return f"Double night — winner earns 2× chips · {home_name} moves to #{home_rank - 1} if they win"
        return f"Double night — winner earns 2× chips · {home_name} declared the double"

    # Playoff fatigue — highest priority for safe-playoff games
    if home_fatigue and home_td["status"] == STATUS_SAFE:
        label = "back-to-back fatigue" if away_is_lottery else "resting starters"
        return f"[REST] {home_name} {label} — playing down to the level tonight"
    if away_fatigue and away_td["status"] == STATUS_SAFE:
        label = "back-to-back fatigue" if home_is_lottery else "resting starters"
        return f"[REST] {away_name} {label} — playing down to the level tonight"

    # Rally mode — nothing-to-lose, going all-in
    if home_in_rally and home_is_lottery:
        return f"RALLY — {home_name} nothing to lose — going all-in"
    if away_in_rally and away_is_lottery:
        return f"RALLY — {away_name} nothing to lose — going all-in"

    # Hot streak (eligible teams: lottery + play-in)
    home_is_eligible_for_streak = home_is_lottery or home_td["status"] == STATUS_PLAYIN
    away_is_eligible_for_streak = away_is_lottery or away_td["status"] == STATUS_PLAYIN
    if home_hot_streak and home_is_eligible_for_streak:
        boost_pct = round(home_td.get("hot_streak_boost", 0) * 100)
        return f"HOT — {home_name} on a surge (+{boost_pct}% win prob tonight)"
    if away_hot_streak and away_is_eligible_for_streak:
        boost_pct = round(away_td.get("hot_streak_boost", 0) * 100)
        return f"HOT — {away_name} on a surge (+{boost_pct}% win prob tonight)"

    # Lottery vs lottery — chip race
    if home_is_lottery and away_is_lottery and home_rank and away_rank:
        gap = abs(home_chips - away_chips)
        if gap <= 15:
            return f"#{home_rank} vs #{away_rank} — gap is only {gap:.0f} chips"
        return f"#{home_rank} vs #{away_rank} — winner leads by {gap + max(home_wager, away_wager):.0f}+ chips"

    # Pick-swap holder facing lottery team
    if home_td["is_pick_swap_holder"] and away_is_lottery:
        return f"{home_name} hold swap rights — bidding to deny {away_name} chip gains"
    if away_td["is_pick_swap_holder"] and home_is_lottery:
        return f"{away_name} hold swap rights — bidding to deny {home_name} chip gains"

    # Playoff vs lottery
    if home_td["status"] == STATUS_SAFE and away_is_lottery:
        return f"{home_name} playoff team — chip stakes for {away_name} draft position"
    if away_td["status"] == STATUS_SAFE and home_is_lottery:
        return f"{away_name} playoff team — chip stakes for {home_name} draft position"

    # Near floor (lottery team at or near their own starting chips)
    floor_team = None
    home_start = home_td.get("chips_start", 100.0)
    away_start = away_td.get("chips_start", 100.0)
    if home_is_lottery and home_chips <= home_start + 5:
        floor_team = home_name
    elif away_is_lottery and away_chips <= away_start + 5:
        floor_team = away_name
    if floor_team:
        return f"{floor_team} at floor — nothing to lose"

    # Play-in seeding
    if home_td["status"] == STATUS_PLAYIN or away_td["status"] == STATUS_PLAYIN:
        return f"Play-in seeding battle — both teams need the win"

    return f"{home_name} vs {away_name} — chip window game {night_idx + 1}"


# ── JSON serialisation ───────────────────────────────────────────────────────

def result_to_json(result: SimResult) -> dict:
    seasons_json = []
    for s in result.seasons:
        teams_json = []
        for td in s.teams:
            teams_json.append({
                "id":               td["id"],
                "name":             td["name"],
                "talent":           td["talent"],
                "wins_60":          td["wins_60"],
                "losses_60":        td["losses_60"],
                "status":           td["status"],
                "in_chip_pool":     td["in_chip_pool"],
                "chips_start":      td["chips_start"],
                "chips_end":        td["chips_end"],
                "chip_trajectory":  td["chip_trajectory"],
                "chip_wins":        td["chip_wins"],
                "chip_losses":      td["chip_losses"],
                "doubled":          td["doubled"],
                "double_night":     td["double_night"],
                "final_wins":       td["final_wins"],
                "final_losses":     td["final_losses"],
                "final_rank":       td.get("final_rank", 30),
                "playoff":          td["playoff"],
                "lottery_odds":     td["lottery_odds"],
                "strategy":         td.get("strategy", "none"),
                "is_pick_swap_holder": td.get("is_pick_swap_holder", False),
                "chip_draft_rank":  td.get("chip_draft_rank"),
                "chip_pick":        td.get("chip_pick"),
                "chip_gap_up":      td.get("chip_gap_up"),
                "chip_gap_up_team": td.get("chip_gap_up_team"),
                "chip_gap_down":      td.get("chip_gap_down"),
                "chip_gap_down_team": td.get("chip_gap_down_team"),
                # tonight_* fields (from final chip-window night, G82)
                "tonight_opponent":   td.get("tonight_opponent"),
                "tonight_wager":      td.get("tonight_wager"),
                "tonight_opp_wager":  td.get("tonight_opp_wager"),
                "tonight_pot":        td.get("tonight_pot"),
                "tonight_double":     td.get("tonight_double", False),
                # per-night opponent wager amounts (22 values, one per night)
                "opponent_wagers":    td.get("opponent_wagers", []),
                # Variance fields
                "bidding_personality": td.get("bidding_personality", "standard"),
                "has_hot_streak":      td.get("has_hot_streak", False),
                "hot_streak_nights":   td.get("hot_streak_nights"),
                "hot_streak_boost":    td.get("hot_streak_boost", 0.0),
                "fatigue_nights":      td.get("fatigue_nights", []),
                "rally_mode":          td.get("rally_mode", False),
                "rally_mode_night":    td.get("rally_mode_night"),
                "total_upset_bonus":   td.get("total_upset_bonus", 0.0),
                "behavior_shift":      td.get("behavior_shift", 0.0),
            })

        champion_name_map = {td["id"]: td["name"] for td in s.teams}
        seasons_json.append({
            "season_num":    s.season_num,
            "teams":         teams_json,
            "champion_id":   s.champion_id,
            "champion_name": champion_name_map.get(s.champion_id, f"Team {s.champion_id}"),
            "playoff_ids":   s.playoff_ids,
            "schedule":      s.schedule,   # games_in_wnd nights × (n_teams/2) matchups
        })

    return {
        "seasons":            seasons_json,
        "leaderboard":        result.leaderboard,
        "seed":               result.seed,
        "seasons_count":      result.seasons_count,
        "strategy":           result.strategy,
        "league_id":          result.league_id,
        "league_name":        result.league_name,
        "num_teams":          result.num_teams,
        "chip_window_start":  result.chip_window_start,
        "chip_window_length": result.chip_window_length,
        "games_per_season":   result.games_per_season,
    }
