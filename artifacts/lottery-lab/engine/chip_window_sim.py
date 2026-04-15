from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Optional

from engine.lottery_sim import NBA_TEAM_NAMES

GAMES_BEFORE_WINDOW = 60
GAMES_IN_WINDOW = 22
TOTAL_GAMES = 82
STARTING_CHIPS = 100.0
MIN_BET = 10.0
BIG_BET = 25.0
DOUBLE_THRESHOLD = 100.0
PLAY_IN_BONUS = 7.5

SAFE_PLAYOFF_COUNT = 12
PLAY_IN_COUNT = 8
PLAYOFF_COUNT = 16
LOTTERY_COUNT = 14

NBA_ODDS = [14.0, 14.0, 14.0, 12.5, 10.5, 9.0, 7.5, 6.0, 4.5, 3.0, 2.0, 1.5, 1.0, 0.5]

STATUS_SAFE = "Safe Playoff"
STATUS_PLAYIN = "Play-In"
STATUS_LOTTERY = "Lottery"


def _win_prob(talent: float) -> float:
    return 1.0 / (1.0 + math.exp(-(talent - 50.0) / 8.0))


def _simulate_60_games(talent: float, rng: random.Random) -> tuple[int, int]:
    wp = _win_prob(talent)
    wins = sum(1 for _ in range(GAMES_BEFORE_WINDOW) if rng.random() < wp)
    return wins, GAMES_BEFORE_WINDOW - wins


def _simulate_chip_window(
    talent: float,
    rng: random.Random,
    strategy: str = "standard",
) -> tuple[float, list[float], int, int, bool]:
    """
    Simulate the 22-game chip window.
    Returns (final_chips, trajectory, wins, losses, doubled).
    trajectory includes chip count after each game (length 22, not including start).
    """
    wp = _win_prob(talent)
    chips = STARTING_CHIPS
    trajectory: list[float] = []
    wins = 0
    losses = 0

    for _ in range(GAMES_IN_WINDOW):
        if strategy == "aggressive":
            bet = BIG_BET
        elif strategy == "conservative":
            bet = MIN_BET
        else:
            bet = BIG_BET if chips >= 50.0 else MIN_BET

        if rng.random() < wp:
            chips += bet
            wins += 1
        else:
            chips = max(0.0, chips - bet)
            losses += 1
        trajectory.append(round(chips, 1))

    doubled = chips > DOUBLE_THRESHOLD
    if doubled:
        chips *= 2.0

    return round(chips, 1), trajectory, wins, losses, doubled


def _effective_odds(chip_teams: list[dict]) -> dict[int, float]:
    """
    Compute final lottery odds for lottery-eligible teams.
    Floor = current NBA odds based on rank. Upside from chips.
    """
    lottery_ids = [t["id"] for t in chip_teams if t["status"] == STATUS_LOTTERY]
    lottery_sorted = sorted(
        [t for t in chip_teams if t["status"] == STATUS_LOTTERY],
        key=lambda t: t["wins_60"],
    )

    n = len(lottery_sorted)
    floor_weights = {lottery_sorted[i]["id"]: NBA_ODDS[i] for i in range(n)}

    total_chips = sum(t["chips_end"] for t in lottery_sorted)
    total_floor = sum(NBA_ODDS[:n])
    if total_chips > 0:
        chip_weights = {
            t["id"]: t["chips_end"] / total_chips * total_floor
            for t in lottery_sorted
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


@dataclass
class SeasonSummary:
    season_num: int
    teams: list[dict]
    champion_id: int
    playoff_ids: list[int]


@dataclass
class SimResult:
    seasons: list[SeasonSummary]
    leaderboard: list[dict]
    seed: int
    seasons_count: int
    strategy: str = "standard"


VALID_STRATEGIES = ("standard", "aggressive", "conservative")


def simulate_chip_window_league(
    seasons: int = 10,
    seed: Optional[int] = None,
    strategy: str = "standard",
) -> SimResult:
    if strategy not in VALID_STRATEGIES:
        strategy = "standard"
    if seed is None:
        seed = random.randint(0, 999999)

    rng = random.Random(seed)

    talents: list[float] = []
    for _ in range(30):
        t = rng.gauss(50, 16)
        talents.append(max(12.0, min(88.0, t)))
    talents.sort(reverse=True)

    titles: dict[int, int] = {i: 0 for i in range(30)}
    playoff_apps: dict[int, int] = {i: 0 for i in range(30)}
    total_chips_sum: dict[int, float] = {i: 0.0 for i in range(30)}

    season_summaries: list[SeasonSummary] = []

    for season_idx in range(seasons):
        team_data: list[dict] = []

        for i in range(30):
            drift = rng.gauss(0, 2.5)
            t = max(8.0, min(92.0, talents[i] + drift))
            w60, l60 = _simulate_60_games(t, rng)
            team_data.append({
                "id": i,
                "name": NBA_TEAM_NAMES[i],
                "talent": round(t, 1),
                "wins_60": w60,
                "losses_60": l60,
                "status": "",
                "in_chip_pool": False,
                "chips_start": STARTING_CHIPS,
                "chips_end": STARTING_CHIPS,
                "chip_trajectory": [],
                "chip_wins": 0,
                "chip_losses": 0,
                "doubled": False,
                "final_wins": w60,
                "final_losses": l60,
                "playoff": False,
                "lottery_odds": 0.0,
            })

        by_wins = sorted(team_data, key=lambda t: t["wins_60"], reverse=True)
        for rank, td in enumerate(by_wins):
            if rank < SAFE_PLAYOFF_COUNT:
                td["status"] = STATUS_SAFE
            elif rank < PLAYOFF_COUNT:
                td["status"] = STATUS_PLAYIN
            else:
                td["status"] = STATUS_LOTTERY
            td["in_chip_pool"] = td["status"] != STATUS_SAFE

        for td in team_data:
            if not td["in_chip_pool"]:
                td["chip_trajectory"] = [STARTING_CHIPS] * GAMES_IN_WINDOW
                td["chips_end"] = STARTING_CHIPS
                continue

            # Play-In teams have dual incentive to win (playoff seeding + chips),
            # so they always bet aggressively regardless of the chosen strategy.
            team_strategy = "aggressive" if td["status"] == STATUS_PLAYIN else strategy
            chips_end, traj, cw, cl, doubled = _simulate_chip_window(
                td["talent"], rng, strategy=team_strategy
            )
            td["strategy"] = team_strategy

            if td["status"] == STATUS_PLAYIN and chips_end <= DOUBLE_THRESHOLD:
                chips_end = round(chips_end + PLAY_IN_BONUS, 1)

            td["chips_end"] = chips_end
            td["chip_trajectory"] = traj
            td["chip_wins"] = cw
            td["chip_losses"] = cl
            td["doubled"] = doubled
            td["final_wins"] = td["wins_60"] + cw
            td["final_losses"] = td["losses_60"] + cl
            total_chips_sum[td["id"]] += chips_end

        lottery_teams = [td for td in team_data if td["status"] == STATUS_LOTTERY]
        odds_map = _effective_odds(lottery_teams + [td for td in team_data if td["status"] == STATUS_PLAYIN])
        for td in team_data:
            td["lottery_odds"] = odds_map.get(td["id"], 0.0)

        final_sorted = sorted(team_data, key=lambda t: t["final_wins"], reverse=True)
        for rank, td in enumerate(final_sorted):
            td["final_rank"] = rank + 1
            if rank < PLAYOFF_COUNT:
                td["playoff"] = True
                playoff_apps[td["id"]] += 1

        playoff_pool = [td for td in team_data if td["playoff"]]
        weights = [max(0.5, td["talent"]) for td in playoff_pool]
        total_w = sum(weights)
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
            season_num=season_idx + 1,
            teams=list(team_data),
            champion_id=champion_id,
            playoff_ids=[td["id"] for td in team_data if td["playoff"]],
        ))

        for i in range(30):
            talents[i] = max(8.0, min(92.0, talents[i] + rng.gauss(0, 1.5)))

    leaderboard = []
    for i in range(30):
        played = seasons
        avg_chips = round(total_chips_sum[i] / played, 1) if played > 0 else 0.0
        leaderboard.append({
            "id": i,
            "name": NBA_TEAM_NAMES[i],
            "titles": titles[i],
            "playoffs": playoff_apps[i],
            "avg_chips": avg_chips,
        })
    leaderboard.sort(key=lambda r: (r["titles"], r["playoffs"]), reverse=True)

    return SimResult(
        seasons=season_summaries,
        leaderboard=leaderboard,
        seed=seed,
        seasons_count=seasons,
        strategy=strategy,
    )


def result_to_json(result: SimResult) -> dict:
    seasons_json = []
    for s in result.seasons:
        teams_json = []
        for td in s.teams:
            teams_json.append({
                "id": td["id"],
                "name": td["name"],
                "talent": td["talent"],
                "wins_60": td["wins_60"],
                "losses_60": td["losses_60"],
                "status": td["status"],
                "in_chip_pool": td["in_chip_pool"],
                "chips_start": td["chips_start"],
                "chips_end": td["chips_end"],
                "chip_trajectory": td["chip_trajectory"],
                "chip_wins": td["chip_wins"],
                "chip_losses": td["chip_losses"],
                "doubled": td["doubled"],
                "final_wins": td["final_wins"],
                "final_losses": td["final_losses"],
                "final_rank": td.get("final_rank", 30),
                "playoff": td["playoff"],
                "lottery_odds": td["lottery_odds"],
                "strategy": td.get("strategy", "none"),
            })
        seasons_json.append({
            "season_num": s.season_num,
            "teams": teams_json,
            "champion_id": s.champion_id,
            "champion_name": NBA_TEAM_NAMES[s.champion_id],
            "playoff_ids": s.playoff_ids,
        })

    return {
        "seasons": seasons_json,
        "leaderboard": result.leaderboard,
        "seed": result.seed,
        "seasons_count": result.seasons_count,
        "strategy": result.strategy,
    }
