from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Optional

from engine.lottery_sim import NBA_TEAM_NAMES

# ── Constants ────────────────────────────────────────────────────────────────
GAMES_BEFORE_WINDOW = 60
GAMES_IN_WINDOW = 22
TOTAL_GAMES = 82
STARTING_CHIPS = 100.0
MIN_BET = 10.0
BIG_BET = 25.0
DOUBLE_THRESHOLD = 100.0   # reference line for trajectory chart only; NOT a double eligibility requirement
PLAY_IN_BONUS = 7.5        # consolation for play-in teams that miss playoffs

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


def _simulate_60_games(talent: float, rng: random.Random) -> tuple[int, int]:
    wp = _win_prob(talent)
    wins = sum(1 for _ in range(GAMES_BEFORE_WINDOW) if rng.random() < wp)
    return wins, GAMES_BEFORE_WINDOW - wins


def _pick_bet(chips: float, strategy: str) -> float:
    """Choose wager based on strategy. Minimum wager is always MIN_BET."""
    if strategy == "aggressive":
        return BIG_BET
    if strategy == "conservative":
        return MIN_BET
    # standard: adaptive — bid big when comfortably ahead
    return BIG_BET if chips >= 50.0 else MIN_BET


# ── Lottery odds computation ─────────────────────────────────────────────────

def _effective_odds(chip_teams: list[dict]) -> dict[int, float]:
    """Compute final lottery odds for lottery-eligible teams.
    Floor = record-based NBA odds. Upside = proportional chip weight.
    Negative chips → max(0, chips) for weight (floor odds only, no upside).
    """
    lottery_sorted = sorted(
        [t for t in chip_teams if t["status"] == STATUS_LOTTERY],
        key=lambda t: t["wins_60"],
    )
    n = len(lottery_sorted)
    if n == 0:
        return {}

    floor_weights = {lottery_sorted[i]["id"]: NBA_ODDS[i] for i in range(n)}
    total_floor = sum(NBA_ODDS[:n])

    # Chips weight: use max(0, chips) so negative chips don't penalize further
    eff_chips = [max(0.0, t["chips_end"]) for t in lottery_sorted]
    total_chips = sum(eff_chips)

    if total_chips > 0.0:
        chip_weights = {
            lottery_sorted[i]["id"]: eff_chips[i] / total_chips * total_floor
            for i in range(n)
        }
    else:
        chip_weights = {t["id"]: 0.0 for t in lottery_sorted}

    effective = {
        tid: max(floor_weights[tid], chip_weights.get(tid, 0.0))
        for tid in floor_weights
    }
    total_eff = sum(effective.values())
    if total_eff > 0:
        return {tid: round(w / total_eff * 100.0, 2) for tid, w in effective.items()}
    return {tid: 0.0 for tid in floor_weights}


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


# ── Main simulation ──────────────────────────────────────────────────────────

def simulate_chip_window_league(
    seasons: int = 10,
    seed: Optional[int] = None,
    strategy: str = "standard",
) -> SimResult:
    """
    Simulate seasons × 30-team league with the Bid Standardization chip window.

    Mechanics (paper-accurate):
    ─ ALL 30 teams participate in the chip pool.
    ─ 22-night chip window: each night, 30 teams are randomly paired into
      15 head-to-head matchups. Home/away is randomly assigned.
    ─ Pot mechanic: both teams announce wagers; winner gains opponent's wager
      (net); loser loses own wager. Chips can go negative.
    ─ Double (lottery teams only): first home game where chips ≥ 100, the
      team may double their wager for that game. Opponent auto-responds with
      BIG_BET (25). Team risks doubled wager; gains opponent's bid on a win.
    ─ Strategy assignments:
        Lottery   → user-selected strategy
        Play-In   → always aggressive (dual incentive: seeding + chips)
        Safe PO   → conservative by default; ~25% are "pick swap holders"
                    who bid aggressively vs. lottery opponents
    ─ Draft order: most chips = Pick 1 (record irrelevant) among lottery teams.
    """
    if strategy not in VALID_STRATEGIES:
        strategy = "standard"
    if seed is None:
        seed = random.randint(0, 999_999)

    rng = random.Random(seed)

    # Initial talent distribution: gauss(50,10) clipped [18,76]
    talents: list[float] = []
    for _ in range(30):
        talents.append(max(18.0, min(76.0, rng.gauss(50, 10))))
    talents.sort(reverse=True)

    titles: dict[int, int]        = {i: 0   for i in range(30)}
    playoff_apps: dict[int, int]  = {i: 0   for i in range(30)}
    total_chips_sum: dict[int, float] = {i: 0.0 for i in range(30)}

    season_summaries: list[SeasonSummary] = []

    for season_idx in range(seasons):

        # ── Build team records for this season ──────────────────────────────
        team_data: list[dict] = []
        for i in range(30):
            t = max(18.0, min(76.0, talents[i] + rng.gauss(0, 2.5)))
            w60, l60 = _simulate_60_games(t, rng)
            team_data.append({
                "id":              i,
                "name":            NBA_TEAM_NAMES[i],
                "talent":          round(t, 1),
                "wins_60":         w60,
                "losses_60":       l60,
                "status":          "",
                "in_chip_pool":    True,   # ALL 30 teams participate
                "chips_start":     STARTING_CHIPS,
                "chips_end":       STARTING_CHIPS,
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
            })

        # ── Classify status by wins through game 60 ──────────────────────────
        by_wins = sorted(team_data, key=lambda t: t["wins_60"], reverse=True)
        for rank, td in enumerate(by_wins):
            if rank < SAFE_PLAYOFF_COUNT:
                td["status"] = STATUS_SAFE
            elif rank < PLAYOFF_COUNT:
                td["status"] = STATUS_PLAYIN
            else:
                td["status"] = STATUS_LOTTERY

        # ── Assign strategies ────────────────────────────────────────────────
        for td in team_data:
            if td["status"] == STATUS_PLAYIN:
                td["strategy"] = "aggressive"
            elif td["status"] == STATUS_SAFE:
                # ~25% of safe-playoff teams model pick-swap exposure → aggressive
                td["is_pick_swap_holder"] = rng.random() < 0.25
                td["strategy"] = "aggressive" if td["is_pick_swap_holder"] else "conservative"
            else:
                td["strategy"] = strategy   # lottery: user-chosen

        # ── Build 22-night random pairings ───────────────────────────────────
        ids = [td["id"] for td in team_data]
        team_by_id = {td["id"]: td for td in team_data}

        night_pairings: list[list[tuple[int, int]]] = []
        for _ in range(GAMES_IN_WINDOW):
            shuffled = ids[:]
            rng.shuffle(shuffled)
            pairs: list[tuple[int, int]] = []
            for i in range(0, 30, 2):
                a, b = shuffled[i], shuffled[i + 1]
                home = a if rng.random() < 0.5 else b
                away = b if home == a else a
                pairs.append((home, away))
            night_pairings.append(pairs)

        # ── Chip window simulation (night-by-night) ──────────────────────────
        chips:       dict[int, float] = {i: STARTING_CHIPS for i in ids}
        dbl_tracker: dict[int, bool]  = {i: False          for i in ids}
        trajectories: dict[int, list[float]] = {i: [] for i in ids}
        chip_wins:   dict[int, int]   = {i: 0   for i in ids}
        chip_losses: dict[int, int]   = {i: 0   for i in ids}

        full_schedule: list[list[dict]] = []

        for night_idx, pairs in enumerate(night_pairings):
            night_results: list[dict] = []

            for slot_idx, (home_id, away_id) in enumerate(pairs):
                home_td = team_by_id[home_id]
                away_td = team_by_id[away_id]

                home_chips_before = chips[home_id]
                away_chips_before = chips[away_id]

                # ── Double declaration (lottery teams, any home game, no chip floor) ──
                home_dbl = (
                    not dbl_tracker[home_id]
                    and home_td["status"] == STATUS_LOTTERY
                )
                away_dbl = (
                    not dbl_tracker[away_id]
                    and away_td["status"] == STATUS_LOTTERY
                )
                # Only home team can declare at home; if both eligible, home wins
                if away_dbl and not home_dbl:
                    # Away declaring double at an away game — not allowed per paper
                    away_dbl = False
                if home_dbl:
                    dbl_tracker[home_id] = True
                    home_td["doubled"]     = True
                    home_td["double_night"] = night_idx
                if away_dbl:
                    dbl_tracker[away_id] = True
                    away_td["doubled"]     = True
                    away_td["double_night"] = night_idx

                # ── Wagers ───────────────────────────────────────────────────
                home_base = _pick_bet(chips[home_id], home_td["strategy"])
                away_base = _pick_bet(chips[away_id], away_td["strategy"])

                home_wager = home_base * 2.0 if home_dbl else home_base
                away_wager = away_base * 2.0 if away_dbl else away_base

                # Opponent responds to a double with max bid
                if home_dbl:
                    away_wager = BIG_BET
                if away_dbl:
                    home_wager = BIG_BET

                pot = home_wager + away_wager

                # ── Head-to-head outcome ─────────────────────────────────────
                p_home = _h2h_prob(home_td["talent"], away_td["talent"])
                home_won = rng.random() < p_home

                # ── Pot mechanic: winner += opp_wager, loser -= own_wager ────
                if home_won:
                    chips[home_id] += away_wager
                    chips[away_id] -= away_wager
                    winner_id = home_id
                    chip_wins[home_id]   += 1
                    chip_losses[away_id] += 1
                else:
                    chips[away_id] += home_wager
                    chips[home_id] -= home_wager
                    winner_id = away_id
                    chip_wins[away_id]   += 1
                    chip_losses[home_id] += 1

                # ── Build narrative (client can use directly) ─────────────────
                narrative = _build_narrative(
                    home_td, away_td,
                    home_chips_before, away_chips_before,
                    home_wager, away_wager,
                    home_dbl, away_dbl,
                    night_idx,
                )

                night_results.append({
                    "home_id":            home_id,
                    "away_id":            away_id,
                    "home_name":          home_td["name"],
                    "away_name":          away_td["name"],
                    "home_status":        home_td["status"],
                    "away_status":        away_td["status"],
                    "home_is_pick_swap":  home_td["is_pick_swap_holder"],
                    "away_is_pick_swap":  away_td["is_pick_swap_holder"],
                    "home_strategy":      home_td["strategy"],
                    "away_strategy":      away_td["strategy"],
                    "home_wager":         home_wager,
                    "away_wager":         away_wager,
                    "pot":                pot,
                    "home_won":           home_won,
                    "winner_id":          winner_id,
                    "home_double":        home_dbl,
                    "away_double":        away_dbl,
                    "home_chips_before":  round(home_chips_before, 1),
                    "away_chips_before":  round(away_chips_before, 1),
                    "home_chips_after":   round(chips[home_id], 1),
                    "away_chips_after":   round(chips[away_id], 1),
                    "tip_time":           _TIP_TIMES[slot_idx % len(_TIP_TIMES)],
                    "narrative":          narrative,
                })

            full_schedule.append(night_results)

            # Record trajectory for ALL teams after this night
            for tid in ids:
                trajectories[tid].append(round(chips[tid], 1))

        # ── Play-in consolation for teams that missed playoffs ───────────────
        for td in team_data:
            if td["status"] == STATUS_PLAYIN and chips[td["id"]] <= DOUBLE_THRESHOLD:
                chips[td["id"]] = round(chips[td["id"]] + PLAY_IN_BONUS, 1)
                if trajectories[td["id"]]:
                    trajectories[td["id"]][-1] = chips[td["id"]]

        # ── Finalize team chip data ──────────────────────────────────────────
        for td in team_data:
            tid = td["id"]
            td["chips_end"]       = round(chips[tid], 1)
            td["chip_trajectory"] = trajectories[tid]
            td["chip_wins"]       = chip_wins[tid]
            td["chip_losses"]     = chip_losses[tid]
            td["final_wins"]      = td["wins_60"] + chip_wins[tid]
            td["final_losses"]    = td["losses_60"] + chip_losses[tid]
            total_chips_sum[tid] += td["chips_end"]

        # ── Lottery odds (max(0,chips) for weight; negative → floor only) ────
        lottery_teams = [td for td in team_data if td["status"] == STATUS_LOTTERY]
        play_in_teams = [td for td in team_data if td["status"] == STATUS_PLAYIN]
        odds_map = _effective_odds(lottery_teams + play_in_teams)
        for td in team_data:
            td["lottery_odds"] = odds_map.get(td["id"], 0.0)

        # ── Chip draft rank (most chips = Pick 1 among lottery teams) ────────
        lottery_by_chips = sorted(lottery_teams, key=lambda t: t["chips_end"], reverse=True)
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
            if rank < PLAYOFF_COUNT:
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
        for i in range(30):
            talents[i] = max(18.0, min(76.0, talents[i] + rng.gauss(0, 1.5)))

    # ── Cumulative leaderboard ───────────────────────────────────────────────
    leaderboard = []
    for i in range(30):
        avg_chips = round(total_chips_sum[i] / seasons, 1)
        leaderboard.append({
            "id":       i,
            "name":     NBA_TEAM_NAMES[i],
            "titles":   titles[i],
            "playoffs": playoff_apps[i],
            "avg_chips": avg_chips,
        })
    leaderboard.sort(key=lambda r: (r["titles"], r["playoffs"]), reverse=True)

    return SimResult(
        seasons       = season_summaries,
        leaderboard   = leaderboard,
        seed          = seed,
        seasons_count = seasons,
        strategy      = strategy,
    )


# ── Narrative helper ─────────────────────────────────────────────────────────

def _build_narrative(
    home_td: dict, away_td: dict,
    home_chips: float, away_chips: float,
    home_wager: float, away_wager: float,
    home_dbl: bool, away_dbl: bool,
    night_idx: int,
) -> str:
    """Generate a short game narrative string."""
    home_name = home_td["name"]
    away_name = away_td["name"]
    home_rank = home_td.get("chip_draft_rank")
    away_rank = away_td.get("chip_draft_rank")

    if home_dbl:
        if home_rank and home_rank > 1:
            return f"Double game — {home_name} moves to #{home_rank - 1} if they win"
        return f"Double game — {home_name} playing for chip position"
    if away_dbl:
        if away_rank and away_rank > 1:
            return f"Double declared by {away_name} — playing for Pick #{away_rank - 1}"
        return f"Double declared — {away_name} plays for chip position"

    home_is_lottery = home_td["status"] == STATUS_LOTTERY
    away_is_lottery = away_td["status"] == STATUS_LOTTERY

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

    # Near floor
    floor_team = None
    if home_is_lottery and home_chips <= STARTING_CHIPS + 5:
        floor_team = home_name
    elif away_is_lottery and away_chips <= STARTING_CHIPS + 5:
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
                "chip_gap_down":    td.get("chip_gap_down"),
                "chip_gap_down_team": td.get("chip_gap_down_team"),
            })

        seasons_json.append({
            "season_num":    s.season_num,
            "teams":         teams_json,
            "champion_id":   s.champion_id,
            "champion_name": NBA_TEAM_NAMES[s.champion_id],
            "playoff_ids":   s.playoff_ids,
            "schedule":      s.schedule,   # 22 nights × 15 matchups
        })

    return {
        "seasons":       seasons_json,
        "leaderboard":   result.leaderboard,
        "seed":          result.seed,
        "seasons_count": result.seasons_count,
        "strategy":      result.strategy,
    }
