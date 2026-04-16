from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


NUM_TEAMS = 30
PLAYOFF_SPOTS = 16
LOTTERY_TEAMS = NUM_TEAMS - PLAYOFF_SPOTS  # 14
LOTTERY_PICKS = 4  # number of picks drawn by weighted lottery (remaining go by record)
GAMES_PER_SEASON = 82
WEEKS_PER_SEASON = 26
PLAY_IN_SLOTS = 4  # teams 13-16 in standings compete in play-in


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Team:
    id: int
    name: str
    true_talent: float   # 0-100; 50 = average
    tank_propensity: float  # 0-1


@dataclass
class SeasonResult:
    standings: list[tuple[int, int, int]]  # (team_id, wins, losses)
    head_to_head: dict[tuple[int, int], tuple[int, int]]  # (a,b) -> (a_wins, b_wins)
    eliminated_week: dict[int, int]  # team_id -> week they were mathematically eliminated


@dataclass
class DraftConstraints:
    top1_history: dict[int, list[int]] = field(default_factory=dict)   # team_id -> [years since pick]
    top3_history: dict[int, list[int]] = field(default_factory=dict)   # team_id -> [years since pick]
    current_year: int = 0


@dataclass
class MetricsBundle:
    system_name: str
    late_season_effort: float          # effort-multiplier ratio (bottom-6 teams): last ~20 games / first ~62
    repeat_top1_frequency: float       # fraction of seasons where same team got #1 again within 5 years
    gini_top5: float                   # Gini coefficient of top-5 pick distribution across teams
    tank_cycles: float                 # avg number of teams tanking per season
    competitive_balance: float         # avg stddev of wins year over year
    avg_wins_top3_recipients: float    # avg wins of teams that received top-3 picks
    pick_distribution: dict[int, list[float]]  # team_id -> [pct of top-5 picks received]
    effort_by_week: list[float]        # avg effort multiplier per week (bottom-6 teams across all seasons)
    avg_wins_by_rank: list[float]      # avg wins for rank-1..NUM_TEAMS (best to worst)
    avg_wins_by_team: dict[int, float] = field(default_factory=dict)  # team_id -> avg wins/season
    pick1_by_team: dict[int, float] = field(default_factory=dict)     # team_id -> % of #1 picks


@dataclass
class RunResult:
    system_name: str
    seasons: list[SeasonResult]
    draft_orders: list[list[int]]       # per season: [team_id in draft order]
    effort_log: list[list[list[float]]] # [season][week][team_idx]
    team_ids: list[int]


# ---------------------------------------------------------------------------
# Lottery system protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class LotterySystem(Protocol):
    name: str

    def draft_order(
        self,
        history: list[SeasonResult],
        constraints: DraftConstraints,
        rng: random.Random,
    ) -> list[int]:
        ...

    def tank_incentive(
        self,
        team_id: int,
        standings: list[tuple[int, int, int]],
        history: list[SeasonResult],
    ) -> float:
        """Return a 0-1 value: how much does losing improve lottery position for this team?"""
        ...


# ---------------------------------------------------------------------------
# Helper: NBA-style weighted lottery draw
# ---------------------------------------------------------------------------

def weighted_lottery_draw(
    weights: dict[int, float],
    num_picks: int,
    rng: random.Random,
) -> list[int]:
    """
    Draw `num_picks` teams without replacement using weighted sampling.
    Returns list of team_ids in draft order.
    """
    remaining = dict(weights)
    order = []
    for _ in range(num_picks):
        if not remaining:
            break
        ids = list(remaining.keys())
        w = [remaining[i] for i in ids]
        total = sum(w)
        if total <= 0:
            chosen = rng.choice(ids)
        else:
            r = rng.uniform(0, total)
            cumulative = 0.0
            chosen = ids[-1]
            for tid, wt in zip(ids, w):
                cumulative += wt
                if r <= cumulative:
                    chosen = tid
                    break
        order.append(chosen)
        del remaining[chosen]
    return order


def _non_playoff_teams(season: SeasonResult, num_playoff: int = PLAYOFF_SPOTS) -> list[tuple[int, int, int]]:
    """Return lottery teams sorted worst-to-best (worst record first)."""
    sorted_standings = sorted(season.standings, key=lambda x: x[1])  # ascending wins
    return sorted_standings[:NUM_TEAMS - num_playoff]


def _rank_by_wins_asc(season: SeasonResult, team_id: int) -> int:
    """Return lottery rank of team_id (1 = worst record, 14 = best non-playoff)."""
    lottery = _non_playoff_teams(season)
    for rank, (tid, _, _) in enumerate(lottery, start=1):
        if tid == team_id:
            return rank
    return LOTTERY_TEAMS  # fallback


# ---------------------------------------------------------------------------
# System 1: Current NBA
# ---------------------------------------------------------------------------

# Standard NBA lottery odds for 14 teams (worst to best)
NBA_ODDS = [14.0, 14.0, 14.0, 12.5, 10.5, 9.0, 7.5, 6.0, 4.5, 3.0, 2.0, 1.5, 1.0, 0.5]


class CurrentNBA:
    name = "Current NBA"

    def draft_order(self, history, constraints, rng):
        season = history[-1]
        lottery = _non_playoff_teams(season)  # worst first
        weights = {lottery[i][0]: NBA_ODDS[i] for i in range(len(lottery))}
        lottery_picks = weighted_lottery_draw(weights, min(4, len(weights)), rng)
        remaining = [t[0] for t in lottery if t[0] not in lottery_picks]
        wins_map = {t[0]: t[1] for t in lottery}
        remaining_sorted = sorted(remaining, key=lambda tid: wins_map[tid])  # worst record first (picks 5+)
        return lottery_picks + remaining_sorted

    def tank_incentive(self, team_id, standings, history):
        if not history:
            return 0.5
        rank = _rank_by_wins_asc(history[-1], team_id)
        # Higher incentive for teams near the bottom who can move up in the odds
        # Rank 1-3: huge incentive (14%), rank 4+: diminishing
        if rank <= 3:
            return 0.9
        elif rank <= 6:
            return 0.6
        elif rank <= 10:
            return 0.3
        return 0.1


# ---------------------------------------------------------------------------
# System 2: Flat Bottom
# ---------------------------------------------------------------------------

class FlatBottom:
    name = "Flat Bottom"

    def draft_order(self, history, constraints, rng):
        season = history[-1]
        lottery = _non_playoff_teams(season)
        weights = {t[0]: 1.0 for t in lottery}
        lottery_picks = weighted_lottery_draw(weights, min(4, len(weights)), rng)
        remaining = [t[0] for t in lottery if t[0] not in lottery_picks]
        wins_map = {t[0]: t[1] for t in lottery}
        remaining_sorted = sorted(remaining, key=lambda tid: wins_map[tid])  # worst record first
        return lottery_picks + remaining_sorted

    def tank_incentive(self, team_id, standings, history):
        # Equal odds for all — very little incentive to tank
        return 0.15


# ---------------------------------------------------------------------------
# System 3: Play-In Boost
# ---------------------------------------------------------------------------

class PlayInBoost:
    name = "Play-In Boost"

    def draft_order(self, history, constraints, rng):
        season = history[-1]
        lottery = _non_playoff_teams(season)  # worst first
        n = len(lottery)
        play_in_count = min(PLAY_IN_SLOTS, n)
        floor_count = n - play_in_count
        # Play-in teams (best non-playoff, indices floor_count..n-1) get the TOP odds.
        # Floor teams (worst non-playoff, indices 0..floor_count-1) get the LOWER odds.
        # This ensures play-in teams have equal-or-better odds than any floor team.
        weights = {}
        for i, (tid, wins, _) in enumerate(lottery):
            if i >= floor_count:  # play-in team
                # Within play-in: best team gets highest odds (reverse within group)
                within = (n - 1 - i)          # 0 = best play-in, play_in_count-1 = worst play-in
                weights[tid] = NBA_ODDS[min(within, len(NBA_ODDS) - 1)]
            else:  # floor team: gets odds starting at play_in_count offset
                within = floor_count - 1 - i  # 0 = best floor, floor_count-1 = worst floor
                weights[tid] = NBA_ODDS[min(play_in_count + within, len(NBA_ODDS) - 1)]
        lottery_picks = weighted_lottery_draw(weights, min(4, len(weights)), rng)
        remaining = [t[0] for t in lottery if t[0] not in lottery_picks]
        wins_map = {t[0]: t[1] for t in lottery}
        remaining_sorted = sorted(remaining, key=lambda tid: wins_map[tid])  # worst record first
        return lottery_picks + remaining_sorted

    def tank_incentive(self, team_id, standings, history):
        if not history:
            return 0.4
        rank = _rank_by_wins_asc(history[-1], team_id)
        # Play-in teams don't benefit from losing, others do somewhat
        if rank >= LOTTERY_TEAMS - 3:
            return 0.05  # play-in team: little incentive to tank
        elif rank <= 3:
            return 0.8
        return 0.4


# ---------------------------------------------------------------------------
# System 4: UEFA Coefficient
# ---------------------------------------------------------------------------

def _uefa_coefficient(team_id: int, history: list[SeasonResult]) -> float:
    """Rolling 3-year weighted performance score."""
    scores = []
    for season in history[-3:]:
        lottery = _non_playoff_teams(season)
        lottery_ids = [t[0] for t in lottery]
        if team_id not in lottery_ids:
            # Made playoffs — high score
            scores.append(10.0)
            continue
        rank = _rank_by_wins_asc(season, team_id)
        # Best non-playoff = 1 pt (rank 14), worst = 10 pts (rank 1)
        base = LOTTERY_TEAMS + 1 - rank

        # Tier performance: wins vs lottery teams - losses vs lottery teams
        h2h_diff = 0
        for other_id in lottery_ids:
            if other_id == team_id:
                continue
            key = (min(team_id, other_id), max(team_id, other_id))
            if key in season.head_to_head:
                a_wins, b_wins = season.head_to_head[key]
                if key[0] == team_id:
                    h2h_diff += a_wins - b_wins
                else:
                    h2h_diff += b_wins - a_wins
        scores.append(base + h2h_diff * 0.1)

    weights_3yr = [0.5, 0.3, 0.2]
    weights_used = weights_3yr[-len(scores):]
    total_weight = sum(weights_used)
    weighted = sum(s * w for s, w in zip(scores, weights_used)) / total_weight if total_weight > 0 else 5.0
    return max(0.5, weighted)


class UEFACoefficient:
    name = "UEFA Coefficient"

    def draft_order(self, history, constraints, rng):
        season = history[-1]
        lottery = _non_playoff_teams(season)
        weights = {}
        for tid, _, _ in lottery:
            coeff = _uefa_coefficient(tid, history)
            # Higher coeff (worse historical team) = better lottery odds
            weights[tid] = coeff
        lottery_picks = weighted_lottery_draw(weights, min(4, len(weights)), rng)
        remaining = [t[0] for t in lottery if t[0] not in lottery_picks]
        wins_map = {t[0]: t[1] for t in lottery}
        remaining_sorted = sorted(remaining, key=lambda tid: wins_map[tid])  # worst record first
        return lottery_picks + remaining_sorted

    def tank_incentive(self, team_id, standings, history):
        if len(history) < 2:
            return 0.5
        # Losing in year 1 helps in years 2-4; diminishing returns
        # Less acute incentive than current NBA (multi-year coefficient smooths it)
        coeff = _uefa_coefficient(team_id, history)
        # Higher coeff = they're already getting good odds, less incentive to tank more
        return min(0.7, coeff / 15.0)


# ---------------------------------------------------------------------------
# System 5: RCL (Rolling Competitive Lottery)
# ---------------------------------------------------------------------------

def _rcl_coefficient(team_id: int, history: list[SeasonResult]) -> float:
    """LC = (Y1 * 0.5) + (Y2 * 0.3) + (Y3 * 0.2)"""
    scores = []
    for season in history[-3:]:
        lottery = _non_playoff_teams(season)
        lottery_ids = [t[0] for t in lottery]
        if team_id not in lottery_ids:
            scores.append(0.0)  # playoff team gets 0 coefficient
            continue
        rank = _rank_by_wins_asc(season, team_id)
        base = LOTTERY_TEAMS + 1 - rank  # 1-14

        h2h_diff = 0
        for other_id in lottery_ids:
            if other_id == team_id:
                continue
            key = (min(team_id, other_id), max(team_id, other_id))
            if key in season.head_to_head:
                a_wins, b_wins = season.head_to_head[key]
                if key[0] == team_id:
                    h2h_diff += a_wins - b_wins
                else:
                    h2h_diff += b_wins - a_wins
        scores.append(base + h2h_diff * 0.05)

    weights_yr = [0.5, 0.3, 0.2]
    if len(scores) == 0:
        return 5.0
    weights_used = weights_yr[-len(scores):]
    total_w = sum(weights_used)
    return max(0.1, sum(s * w for s, w in zip(scores, weights_used)) / total_w)


def _rcl_apply_caps(weights: dict[int, float], constraints: DraftConstraints) -> tuple[dict[int, float], dict[int, float]]:
    """
    Apply hard caps: no #1 more than once in 5 years, no top-3 more than twice in 5 years.
    Returns (weights_for_top1, weights_for_top3) — separate pools for different picks.
    """
    top1_eligible: dict[int, float] = {}
    top3_eligible: dict[int, float] = {}

    for team_id, w in weights.items():
        top1_years = constraints.top1_history.get(team_id, [])
        recent_top1 = [y for y in top1_years if constraints.current_year - y < 5]
        cap_top1 = len(recent_top1) >= 1

        top3_years = constraints.top3_history.get(team_id, [])
        recent_top3 = [y for y in top3_years if constraints.current_year - y < 5]
        cap_top3 = len(recent_top3) >= 2

        # Pick #1 is also a top-3 pick, so both caps apply to the #1 slot
        if not cap_top1 and not cap_top3:
            top1_eligible[team_id] = w
        if not cap_top3:
            top3_eligible[team_id] = w

    return top1_eligible, top3_eligible


class RCL:
    name = "RCL"

    def draft_order(self, history, constraints, rng):
        season = history[-1]
        lottery = _non_playoff_teams(season)
        base_weights: dict[int, float] = {}
        for tid, wins, _ in lottery:
            coeff = _rcl_coefficient(tid, history)
            if wins < 20:
                coeff *= 0.85
            base_weights[tid] = coeff

        top1_pool, top3_pool = _rcl_apply_caps(base_weights, constraints)

        # If no team is eligible for #1, fall back to all lottery teams
        if not top1_pool:
            top1_pool = base_weights

        # Draw #1 pick from cap-eligible pool
        pick1 = weighted_lottery_draw(top1_pool, 1, rng)

        # Draw picks #2-#3 from top3-eligible pool (excluding already drawn)
        remaining_top3 = {k: v for k, v in top3_pool.items() if k not in pick1}
        if not remaining_top3:
            remaining_top3 = {k: v for k, v in base_weights.items() if k not in pick1}
        picks23 = weighted_lottery_draw(remaining_top3, min(2, len(remaining_top3)), rng)

        # Draw pick #4 from all remaining
        drawn_so_far = set(pick1 + picks23)
        remaining_all = {k: v for k, v in base_weights.items() if k not in drawn_so_far}
        pick4 = weighted_lottery_draw(remaining_all, min(1, len(remaining_all)), rng)

        lottery_picks = pick1 + picks23 + pick4

        # Update constraints
        if pick1:
            constraints.top1_history.setdefault(pick1[0], []).append(constraints.current_year)
        for pick in lottery_picks[:3]:
            constraints.top3_history.setdefault(pick, []).append(constraints.current_year)

        remaining = [t[0] for t in lottery if t[0] not in lottery_picks]
        wins_map = {t[0]: t[1] for t in lottery}
        remaining_sorted = sorted(remaining, key=lambda tid: wins_map[tid])  # worst record first
        return lottery_picks + remaining_sorted

    def tank_incentive(self, team_id, standings, history):
        if len(history) < 1:
            return 0.4
        coeff = _rcl_coefficient(team_id, history)
        # Multi-year smoothing reduces acute tanking; hard caps reduce incentive for repeat tankers
        return min(0.6, coeff / 18.0)


# ---------------------------------------------------------------------------
# System 6: Lottery Tournament
# ---------------------------------------------------------------------------

class LotteryTournament:
    name = "Lottery Tournament"

    def draft_order(self, history, constraints, rng):
        season = history[-1]
        lottery = _non_playoff_teams(season)
        # Bottom 8 play single-elim tournament; winner gets #1 pick
        bottom8 = lottery[:8]  # worst 8
        top6 = lottery[8:]     # best 6 non-playoff teams

        # Simulate tournament: each matchup won probabilistically
        # Teams with better records are slightly more likely to win
        tournament_bracket = [t[0] for t in bottom8]
        rng.shuffle(tournament_bracket)

        def get_wins(tid):
            for t_id, wins, _ in lottery:
                if t_id == tid:
                    return wins
            return 20

        def play_game(a, b):
            wa, wb = get_wins(a), get_wins(b)
            # Better team wins slightly more often but upset is possible
            p_a = 0.5 + (wa - wb) * 0.01
            p_a = max(0.2, min(0.8, p_a))
            return a if rng.random() < p_a else b

        # Round 1: 8 -> 4
        r1 = [play_game(tournament_bracket[i], tournament_bracket[i + 1])
              for i in range(0, 8, 2)]
        # Round 2: 4 -> 2
        r2 = [play_game(r1[i], r1[i + 1]) for i in range(0, 4, 2)]
        # Final: 2 -> 1
        champion = play_game(r2[0], r2[1])

        # #1 pick = tournament champion
        # #2-#8 picks by record (worst first) among other bottom-8 teams
        losers = [t for t in tournament_bracket if t != champion]
        losers_sorted = sorted(losers, key=get_wins)  # worst record first

        # top6 get picks 9-14 by record (worst first)
        top6_sorted = sorted([t[0] for t in top6], key=get_wins)

        return [champion] + losers_sorted + top6_sorted

    def tank_incentive(self, team_id, standings, history):
        if not history:
            return 0.4
        rank = _rank_by_wins_asc(history[-1], team_id)
        # To get into bottom-8 tournament, need to be in bottom 8 of lottery
        # But within tournament, winning requires some talent — tanking isn't as clean
        if rank <= 8:
            return 0.5  # want to be in tournament but also need to win it
        return 0.2


# ---------------------------------------------------------------------------
# System 7: Pure Inversion
# ---------------------------------------------------------------------------

class PureInversion:
    name = "Pure Inversion"

    def draft_order(self, history, constraints, rng):
        season = history[-1]
        lottery = _non_playoff_teams(season)
        # Best non-playoff team picks first, worst picks last
        # Sort by wins descending (best first)
        sorted_best_first = sorted(lottery, key=lambda t: t[1], reverse=True)
        return [t[0] for t in sorted_best_first]

    def tank_incentive(self, team_id, standings, history):
        # Tanking HURTS you — losing means picking later
        # Teams with this system should try hard
        return -0.5  # negative: incentive is to WIN


# ---------------------------------------------------------------------------
# System 8: Gold Plan (PWHL)
# ---------------------------------------------------------------------------

class GoldPlan:
    name = "Gold Plan (PWHL)"

    def draft_order(self, history, constraints, rng):
        season = history[-1]
        # Draft order based on wins AFTER elimination from playoff contention
        # Teams with most post-elimination wins pick first
        sorted_standings = sorted(season.standings, key=lambda x: x[1])
        lottery = sorted_standings[:LOTTERY_TEAMS]

        def post_elim_wins(tid):
            elim_week = season.eliminated_week.get(tid, WEEKS_PER_SEASON)
            # Wins per week estimation from total wins
            total_wins = next(w for t_id, w, _ in lottery if t_id == tid)
            games_per_week = GAMES_PER_SEASON / WEEKS_PER_SEASON
            wins_before_elim = total_wins * (elim_week / WEEKS_PER_SEASON)
            post_wins = max(0, total_wins - wins_before_elim)
            return post_wins

        sorted_by_post_wins = sorted(
            [t[0] for t in lottery],
            key=post_elim_wins,
            reverse=True  # most post-elimination wins picks first
        )
        return sorted_by_post_wins

    def tank_incentive(self, team_id, standings, history):
        if not history:
            return 0.3
        rank = _rank_by_wins_asc(history[-1], team_id)
        # After elimination, winning helps you — complex incentive
        # Before elimination: try to make playoffs; after: try to win for better pick
        # Net effect: moderate anti-tanking incentive
        return 0.1  # mostly don't tank; post-elim wins reward playing hard


# ---------------------------------------------------------------------------
# Default teams
# ---------------------------------------------------------------------------

NBA_TEAM_NAMES = [
    "Atlanta", "Boston", "Brooklyn", "Charlotte", "Chicago",
    "Cleveland", "Dallas", "Denver", "Detroit", "Golden State",
    "Houston", "Indiana", "LA Clippers", "LA Lakers", "Memphis",
    "Miami", "Milwaukee", "Minnesota", "New Orleans", "New York",
    "Oklahoma City", "Orlando", "Philadelphia", "Phoenix", "Portland",
    "Sacramento", "San Antonio", "Toronto", "Utah", "Washington",
]


def default_teams(seed: int | None = None) -> list[Team]:
    rng = random.Random(seed)
    teams = []
    for i, name in enumerate(NBA_TEAM_NAMES):
        # true_talent: normal distribution around 50
        talent = rng.gauss(50, 15)
        talent = max(10, min(90, talent))
        # tank_propensity: skewed; most teams moderate, some high tankers
        propensity = rng.betavariate(1.5, 3.0)
        teams.append(Team(id=i, name=name, true_talent=talent, tank_propensity=propensity))
    return teams


# ---------------------------------------------------------------------------
# Season simulation
# ---------------------------------------------------------------------------

def _win_probability(talent_a: float, talent_b: float) -> float:
    """Logistic win probability for team A vs team B."""
    diff = talent_a - talent_b
    return 1.0 / (1.0 + math.exp(-diff / 8.0))


def _playoff_probability(team_id: int, standings: list[tuple[int, int, int]], week: int) -> float:
    """Sigmoid estimate of making playoffs based on current standing."""
    sorted_by_wins = sorted(standings, key=lambda x: x[1], reverse=True)
    rank = next(i + 1 for i, (tid, _, _) in enumerate(sorted_by_wins) if tid == team_id)
    # At midseason, rank 16 has ~50% playoff odds; rank 12 ~90%, rank 20 ~10%
    progress = week / WEEKS_PER_SEASON
    cutoff = PLAYOFF_SPOTS
    # As season progresses, standings solidify
    sharpness = 1.0 + progress * 3.0
    logit = (cutoff - rank + 0.5) * sharpness * 0.4
    return 1.0 / (1.0 + math.exp(-logit))


def _compute_effort_multiplier(
    team: Team,
    system: LotterySystem,
    standings: list[tuple[int, int, int]],
    history: list[SeasonResult],
    week: int,
) -> float:
    """
    Effort multiplier for a team this week.
    1.0 = full effort; < 1.0 = tanking.
    """
    playoff_p = _playoff_probability(team.id, standings, week)

    # Tank incentive: how much does losing help their lottery position?
    raw_incentive = system.tank_incentive(team.id, standings, history)

    # If system has negative incentive (pure inversion), never tank
    if raw_incentive <= 0:
        return 1.0

    # Teams with high playoff odds play hard regardless
    # Teams with low playoff odds and high tank incentive may tank
    tank_desire = team.tank_propensity * raw_incentive * (1.0 - playoff_p)

    # Effort = 1 - tank_desire, clipped to [0.3, 1.0]
    effort = 1.0 - tank_desire
    return max(0.3, min(1.0, effort))


def _is_mathematically_eliminated(
    team_id: int,
    standings: list[tuple[int, int, int]],
    week: int,
) -> bool:
    """Simple playoff elimination check."""
    games_remaining = int((GAMES_PER_SEASON / WEEKS_PER_SEASON) * (WEEKS_PER_SEASON - week))
    current_wins = next(w for tid, w, _ in standings if tid == team_id)
    max_possible_wins = current_wins + games_remaining

    sorted_by_wins = sorted(standings, key=lambda x: x[1], reverse=True)
    cutoff_wins = sorted_by_wins[PLAYOFF_SPOTS - 1][1] if len(sorted_by_wins) >= PLAYOFF_SPOTS else 0

    return max_possible_wins < cutoff_wins


def simulate_season(
    teams: list[Team],
    system: LotterySystem,
    history: list[SeasonResult],
    rng: random.Random,
) -> tuple[SeasonResult, list[list[float]]]:
    """
    Simulate one NBA season. Returns (SeasonResult, effort_log[week][team_idx]).
    """
    wins = {t.id: 0 for t in teams}
    losses = {t.id: 0 for t in teams}
    h2h: dict[tuple[int, int], tuple[int, int]] = {}
    eliminated_week: dict[int, int] = {}
    effort_log: list[list[float]] = []

    games_per_week = GAMES_PER_SEASON // WEEKS_PER_SEASON
    extra_games = GAMES_PER_SEASON % WEEKS_PER_SEASON

    for week in range(1, WEEKS_PER_SEASON + 1):
        # Build current standings
        standings = [(t.id, wins[t.id], losses[t.id]) for t in teams]

        # Compute effort multipliers
        efforts = {}
        for t in teams:
            efforts[t.id] = _compute_effort_multiplier(t, system, standings, history, week)

        effort_log.append([efforts[t.id] for t in teams])

        # Check eliminations
        for t in teams:
            if t.id not in eliminated_week and _is_mathematically_eliminated(t.id, standings, week):
                eliminated_week[t.id] = week

        # Simulate games this week
        week_games = games_per_week + (1 if week <= extra_games else 0)

        # Create matchups: random round-robin subset
        team_ids = [t.id for t in teams]
        rng.shuffle(team_ids)
        matchups = []
        for i in range(0, len(team_ids) - 1, 2):
            matchups.append((team_ids[i], team_ids[i + 1]))
        # Each round gives every team exactly one game; need week_games rounds
        rounds = week_games if matchups else 0

        for _ in range(rounds):
            for a_id, b_id in matchups:
                team_a = next(t for t in teams if t.id == a_id)
                team_b = next(t for t in teams if t.id == b_id)

                effective_a = team_a.true_talent * efforts[a_id]
                effective_b = team_b.true_talent * efforts[b_id]

                p_a = _win_probability(effective_a, effective_b)
                if rng.random() < p_a:
                    wins[a_id] += 1
                    losses[b_id] += 1
                    key = (min(a_id, b_id), max(a_id, b_id))
                    a_w, b_w = h2h.get(key, (0, 0))
                    if key[0] == a_id:
                        h2h[key] = (a_w + 1, b_w)
                    else:
                        h2h[key] = (a_w, b_w + 1)
                else:
                    wins[b_id] += 1
                    losses[a_id] += 1
                    key = (min(a_id, b_id), max(a_id, b_id))
                    a_w, b_w = h2h.get(key, (0, 0))
                    if key[0] == a_id:
                        h2h[key] = (a_w, b_w + 1)
                    else:
                        h2h[key] = (a_w + 1, b_w)

    standings = sorted(
        [(t.id, wins[t.id], losses[t.id]) for t in teams],
        key=lambda x: x[1],
        reverse=True,
    )
    return SeasonResult(standings=standings, head_to_head=h2h, eliminated_week=eliminated_week), effort_log


# ---------------------------------------------------------------------------
# Multi-season run
# ---------------------------------------------------------------------------

def simulate_run(
    system: LotterySystem,
    seasons: int = 15,
    seed: int | None = None,
) -> RunResult:
    rng = random.Random(seed)
    teams = default_teams(seed)
    history: list[SeasonResult] = []
    draft_orders: list[list[int]] = []
    all_effort_logs: list[list[list[float]]] = []
    constraints = DraftConstraints()

    # Slowly evolve team talents over years (player development / free agency)
    for year in range(seasons):
        constraints.current_year = year
        season_result, effort_log = simulate_season(teams, system, history, rng)
        history.append(season_result)
        all_effort_logs.append(effort_log)

        draft_order = system.draft_order(history, constraints, rng)
        draft_orders.append(draft_order)

        # Slight talent evolution: top pick improves worst team
        if draft_order:
            top_pick_team_id = draft_order[0]
            for t in teams:
                if t.id == top_pick_team_id:
                    t.true_talent = min(90, t.true_talent + rng.uniform(3, 8))
                    break

        # Random talent drift for all teams
        for t in teams:
            drift = rng.gauss(0, 1.5)
            t.true_talent = max(10, min(90, t.true_talent + drift))

    return RunResult(
        system_name=system.name,
        seasons=history,
        draft_orders=draft_orders,
        effort_log=all_effort_logs,
        team_ids=[t.id for t in teams],
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _gini(values: list[float]) -> float:
    """Gini coefficient for a list of values. Returns value in [0, 1)."""
    if not values or sum(values) == 0:
        return 0.0
    sorted_v = sorted(values)
    n = len(sorted_v)
    height = 0.0
    area = 0.0
    for v in sorted_v:
        height += v
        area += height - v / 2.0
    fair_area = height * n / 2.0
    return (fair_area - area) / fair_area if fair_area > 0 else 0.0


def compute_metrics(run: RunResult, teams: list[Team]) -> MetricsBundle:
    seasons = run.seasons
    draft_orders = run.draft_orders
    team_ids = run.team_ids

    # --- Late-season effort ---
    late_effort_vals = []
    early_effort_vals = []
    for s_idx, effort_log in enumerate(run.effort_log):
        season = seasons[s_idx]
        # Bottom 6 teams by wins
        sorted_stands = sorted(season.standings, key=lambda x: x[1])
        bottom6_ids = {t[0] for t in sorted_stands[:6]}

        for week_idx, week_efforts in enumerate(effort_log):
            for t_idx, eff in enumerate(week_efforts):
                tid = team_ids[t_idx]
                if tid not in bottom6_ids:
                    continue
                week_num = week_idx + 1
                if week_num >= WEEKS_PER_SEASON - 7:  # last ~20 games
                    late_effort_vals.append(eff)
                elif week_num <= 19:  # first ~62 games
                    early_effort_vals.append(eff)

    late_avg = sum(late_effort_vals) / len(late_effort_vals) if late_effort_vals else 0.5
    early_avg = sum(early_effort_vals) / len(early_effort_vals) if early_effort_vals else 0.5
    late_season_effort = late_avg / early_avg if early_avg > 0 else 1.0

    # --- Repeat #1 pick frequency ---
    top1_by_year: list[int] = []
    for order in draft_orders:
        if order:
            top1_by_year.append(order[0])

    repeat_count = 0
    for i in range(len(top1_by_year)):
        for j in range(max(0, i - 4), i):
            if top1_by_year[j] == top1_by_year[i]:
                repeat_count += 1
                break
    repeat_freq = repeat_count / len(top1_by_year) if top1_by_year else 0.0

    # --- Gini of top-5 pick distribution ---
    top5_counts: dict[int, int] = {tid: 0 for tid in team_ids}
    for order in draft_orders:
        for pick in order[:5]:
            if pick in top5_counts:
                top5_counts[pick] += 1
    gini_val = _gini(list(top5_counts.values()))

    # --- Per-slot pick distribution (picks 1-5) ---
    pick_counts_per_slot: dict[int, list[int]] = {tid: [0, 0, 0, 0, 0] for tid in team_ids}
    for order in draft_orders:
        for slot_idx in range(min(5, len(order))):
            pick_tid = order[slot_idx]
            if pick_tid in pick_counts_per_slot:
                pick_counts_per_slot[pick_tid][slot_idx] += 1

    # --- Tank cycles ---
    tank_threshold = 0.7
    tank_cycles_per_season = []
    for effort_log in run.effort_log:
        tanking_teams = set()
        for week_efforts in effort_log[-8:]:  # last 8 weeks
            for t_idx, eff in enumerate(week_efforts):
                if eff < tank_threshold:
                    tanking_teams.add(t_idx)
        tank_cycles_per_season.append(len(tanking_teams))
    avg_tank_cycles = sum(tank_cycles_per_season) / len(tank_cycles_per_season) if tank_cycles_per_season else 0.0

    # --- Competitive balance ---
    win_stddevs = []
    for season in seasons:
        wins_list = [w for _, w, _ in season.standings]
        if len(wins_list) > 1:
            mean = sum(wins_list) / len(wins_list)
            variance = sum((w - mean) ** 2 for w in wins_list) / len(wins_list)
            win_stddevs.append(math.sqrt(variance))
    comp_balance = sum(win_stddevs) / len(win_stddevs) if win_stddevs else 0.0

    # --- Avg wins of top-3 pick recipients ---
    top3_wins = []
    for s_idx, order in enumerate(draft_orders):
        season = seasons[s_idx]
        for pick in order[:3]:
            for tid, wins, _ in season.standings:
                if tid == pick:
                    top3_wins.append(wins)
                    break
    avg_top3_wins = sum(top3_wins) / len(top3_wins) if top3_wins else 0.0

    # --- Pick distribution per slot (% of seasons where team got picks 1-5) ---
    total_seasons_slots = max(len(draft_orders), 1)
    pick_dist = {
        tid: [round(pick_counts_per_slot[tid][i] / total_seasons_slots * 100, 2) for i in range(5)]
        for tid in team_ids
    }

    # --- Effort by week (avg across all seasons, bottom-6 teams only) ---
    effort_by_week: list[float] = []
    for week_idx in range(WEEKS_PER_SEASON):
        week_effs = []
        for s_idx2, effort_log in enumerate(run.effort_log):
            if week_idx < len(effort_log):
                # Identify bottom-6 teams for this specific season
                season_b6 = {
                    t[0] for t in sorted(seasons[s_idx2].standings, key=lambda x: x[1])[:6]
                }
                for t_idx, eff in enumerate(effort_log[week_idx]):
                    if team_ids[t_idx] in season_b6:
                        week_effs.append(eff)
        effort_by_week.append(sum(week_effs) / len(week_effs) if week_effs else 1.0)

    # --- Win distribution by rank (avg wins of rank-1..NUM_TEAMS teams) ---
    rank_wins: list[list[float]] = [[] for _ in range(NUM_TEAMS)]
    for season in seasons:
        sorted_wins = sorted([w for _, w, _ in season.standings], reverse=True)
        for rank, wins in enumerate(sorted_wins):
            rank_wins[rank].append(float(wins))
    avg_wins_by_rank = [round(sum(r) / len(r), 1) if r else 0.0 for r in rank_wins]

    # --- Avg wins per team across all seasons ---
    avg_wins_per_team: dict[int, float] = {}
    for tid in team_ids:
        wins_list = [w for season in seasons for t_id, w, _ in season.standings if t_id == tid]
        avg_wins_per_team[tid] = round(sum(wins_list) / len(wins_list), 1) if wins_list else 0.0

    # --- #1 pick distribution per team ---
    pick1_counts: dict[int, int] = {tid: 0 for tid in team_ids}
    for order in draft_orders:
        if order:
            pick1_counts[order[0]] = pick1_counts.get(order[0], 0) + 1
    total_seasons_n = max(len(draft_orders), 1)
    pick1_by_team = {
        tid: round(pick1_counts.get(tid, 0) / total_seasons_n * 100, 2)
        for tid in team_ids
    }

    return MetricsBundle(
        system_name=run.system_name,
        late_season_effort=round(late_season_effort, 4),
        repeat_top1_frequency=round(repeat_freq, 4),
        gini_top5=round(gini_val, 4),
        tank_cycles=round(avg_tank_cycles, 2),
        competitive_balance=round(comp_balance, 2),
        avg_wins_top3_recipients=round(avg_top3_wins, 2),
        pick_distribution=pick_dist,
        effort_by_week=[round(e, 4) for e in effort_by_week],
        avg_wins_by_rank=avg_wins_by_rank,
        avg_wins_by_team=avg_wins_per_team,
        pick1_by_team=pick1_by_team,
    )


# ---------------------------------------------------------------------------
# Monte Carlo
# ---------------------------------------------------------------------------

def monte_carlo(
    system: LotterySystem,
    runs: int = 100,
    seasons: int = 15,
    seed: int | None = None,
) -> MetricsBundle:
    """
    Run Monte Carlo simulation and average the MetricsBundles.
    """
    rng_seed = seed

    all_metrics: list[MetricsBundle] = []
    for run_idx in range(runs):
        run_seed = (rng_seed + run_idx) if rng_seed is not None else None
        run_result = simulate_run(system, seasons=seasons, seed=run_seed)
        teams = default_teams(run_seed)
        metrics = compute_metrics(run_result, teams)
        all_metrics.append(metrics)

    def avg(key):
        return sum(getattr(m, key) for m in all_metrics) / len(all_metrics)

    # Average effort_by_week
    avg_effort_by_week = []
    for week_idx in range(WEEKS_PER_SEASON):
        week_vals = [m.effort_by_week[week_idx] for m in all_metrics if week_idx < len(m.effort_by_week)]
        avg_effort_by_week.append(sum(week_vals) / len(week_vals) if week_vals else 1.0)

    # Average pick_distribution per slot (5 slots per team)
    avg_pick_dist: dict[int, list[float]] = {}
    for i in range(NUM_TEAMS):
        slot_avgs = []
        for slot_idx in range(5):
            pcts = [m.pick_distribution.get(i, [0.0] * 5)[slot_idx] for m in all_metrics]
            slot_avgs.append(round(sum(pcts) / len(pcts), 2) if pcts else 0.0)
        avg_pick_dist[i] = slot_avgs

    # Average avg_wins_by_rank
    avg_wins_by_rank: list[float] = []
    for rank in range(NUM_TEAMS):
        vals = [m.avg_wins_by_rank[rank] for m in all_metrics if rank < len(m.avg_wins_by_rank)]
        avg_wins_by_rank.append(round(sum(vals) / len(vals), 1) if vals else 0.0)

    # Average avg_wins_by_team
    avg_wins_by_team_mc: dict[int, float] = {}
    for i in range(NUM_TEAMS):
        vals = [m.avg_wins_by_team.get(i, 0.0) for m in all_metrics]
        avg_wins_by_team_mc[i] = round(sum(vals) / len(vals), 1) if vals else 0.0

    # Average pick1_by_team
    avg_pick1_by_team: dict[int, float] = {}
    for i in range(NUM_TEAMS):
        vals = [m.pick1_by_team.get(i, 0.0) for m in all_metrics]
        avg_pick1_by_team[i] = round(sum(vals) / len(vals), 2) if vals else 0.0

    return MetricsBundle(
        system_name=system.name,
        late_season_effort=round(avg("late_season_effort"), 4),
        repeat_top1_frequency=round(avg("repeat_top1_frequency"), 4),
        gini_top5=round(avg("gini_top5"), 4),
        tank_cycles=round(avg("tank_cycles"), 2),
        competitive_balance=round(avg("competitive_balance"), 2),
        avg_wins_top3_recipients=round(avg("avg_wins_top3_recipients"), 2),
        pick_distribution=avg_pick_dist,
        effort_by_week=[round(e, 4) for e in avg_effort_by_week],
        avg_wins_by_rank=avg_wins_by_rank,
        avg_wins_by_team=avg_wins_by_team_mc,
        pick1_by_team=avg_pick1_by_team,
    )


# ---------------------------------------------------------------------------
# System 9: Chip Window (Bid Standardization)
# ---------------------------------------------------------------------------

class ChipWindow:
    """
    Bid Standardization / Chip Window — proposed anti-tanking system.

    Activates at game 60 for all 30 teams. Starting chips are assigned by quintile:
    worst 6 teams → 100 chips, next 6 → 80, middle 6 → 60, next 6 → 40, best 6 → 20.
    Chips are clamped at MIN_BET (10) — never drop below the minimum bid.
    Winner gains the opponent's wager; loser loses their own wager (floored at 10).

    Draft order is fully deterministic: the 14 lottery teams are sorted by final
    chip total (DESC). Most chips = Pick 1, fewest chips = Pick 14. No lottery draw.
    Ties are broken by worse record (fewer wins). Picks 15–30 go to playoff teams
    by record order.

    Tanking is structurally impossible — losing depletes chips regardless of intent,
    and no chip result can improve a team's standing through losing.

    Reference: "The Chip Window" by Ron Bronson (April 2026).
    """

    name = "Chip Window"

    GAMES_IN_WINDOW = 22    # games 60–82
    MIN_BET = 10.0
    BIG_BET = 25.0
    DOUBLE_THRESHOLD = 100.0  # finish with > starting chips to unlock double

    # Quintile starting chips (worst 6 → 100, next 6 → 80, … best 6 → 20)
    QUINTILE_CHIPS = [100.0, 80.0, 60.0, 40.0, 20.0]

    def _simulate_chips(self, win_prob: float, rng: random.Random,
                        starting_chips: float = 100.0) -> float:
        """
        One chip-window simulation from a given starting chip total.
        Chips are clamped at MIN_BET (10) — never drop below the minimum bet.
        """
        chips = starting_chips
        for _ in range(self.GAMES_IN_WINDOW):
            bet = self.BIG_BET if chips >= 50.0 else self.MIN_BET
            if rng.random() < win_prob:
                chips += bet
            else:
                chips = max(self.MIN_BET, chips - bet)
        if chips > self.DOUBLE_THRESHOLD:
            chips *= 2.0
        return chips

    def chip_leaderboard(
        self,
        lottery_teams: list,
        n_scenarios: int,
        rng: random.Random,
    ) -> list[dict]:
        """
        Run N chip-window scenarios for each lottery team. Returns a leaderboard
        (sorted highest median chips first) with per-team statistics and a median
        chip-count trajectory over the 22-game window.

        Quintile starting chips are assigned by record rank within the 14 lottery
        teams (worst 6 → 100, next 6 → 80, remaining 2 → 60).
        """
        import statistics as _stats

        # Assign quintile starting chips by record rank (worst first)
        sorted_by_record = sorted(
            lottery_teams,
            key=lambda t: t[1] / (t[1] + t[2]) if (t[1] + t[2]) > 0 else 0.0,
        )
        start_chips_map: dict[str, float] = {}
        for rank_0, (name, wins, losses) in enumerate(sorted_by_record):
            quintile_idx = min(rank_0 // 6, 4)
            start_chips_map[name] = self.QUINTILE_CHIPS[quintile_idx]

        results = []
        for name, wins, losses in lottery_teams:
            total = wins + losses
            win_prob = wins / total if total > 0 else 0.30
            starting_chips = start_chips_map.get(name, 100.0)

            trajectories: list[list[float]] = []
            pre_double: list[float] = []
            final_all: list[float] = []

            for _ in range(n_scenarios):
                chips = starting_chips
                traj: list[float] = [chips]
                for _ in range(self.GAMES_IN_WINDOW):
                    bet = self.BIG_BET if chips >= 50.0 else self.MIN_BET
                    if rng.random() < win_prob:
                        chips += bet
                    else:
                        chips = max(self.MIN_BET, chips - bet)
                    traj.append(chips)
                trajectories.append(traj)
                pre_double.append(chips)
                if chips > self.DOUBLE_THRESHOLD:
                    chips *= 2.0
                final_all.append(chips)

            sorted_final = sorted(final_all)
            n = len(sorted_final)
            prob_double = sum(1 for c in pre_double if c > self.DOUBLE_THRESHOLD) / n

            # Median trajectory: chip count at each game step across all scenarios
            median_traj = [
                round(_stats.median(t[g] for t in trajectories), 1)
                for g in range(self.GAMES_IN_WINDOW + 1)
            ]

            results.append({
                "name": name,
                "wins": wins,
                "losses": losses,
                "win_prob": win_prob,
                "win_pct": round(win_prob * 100, 1),
                "starting_chips": starting_chips,
                "median_chips": round(_stats.median(sorted_final), 1),
                "p25_chips":    round(sorted_final[n // 4], 1),
                "p75_chips":    round(sorted_final[3 * n // 4], 1),
                "max_chips":    round(sorted_final[-1], 1),
                "prob_double":  round(prob_double * 100, 1),
                "median_traj":  median_traj,
            })

        results.sort(key=lambda r: r["median_chips"], reverse=True)
        return results

    def draft_order(self, history, constraints, rng):
        season = history[-1]
        lottery = _non_playoff_teams(season)  # worst first (rank 0 = worst record)
        n = len(lottery)

        # Quintile starting chips by record rank (lottery list is worst-first)
        start_chips: dict[int, float] = {}
        for rank_0, (tid, wins, losses) in enumerate(lottery):
            quintile_idx = min(rank_0 // 6, 4)
            start_chips[tid] = self.QUINTILE_CHIPS[quintile_idx]

        # Simulate the chip window for each team from their quintile start
        raw_chips: dict[int, float] = {}
        for tid, wins, losses in lottery:
            total = wins + losses
            win_prob = wins / total if total > 0 else 0.30
            raw_chips[tid] = self._simulate_chips(win_prob, rng, start_chips[tid])

        # Deterministic draft order: most chips = Pick 1 … fewest chips = Pick 14.
        # Tie-break: worse record (fewer wins) gets the higher pick.
        wins_map = {t[0]: t[1] for t in lottery}
        lottery_sorted = sorted(
            raw_chips.keys(),
            key=lambda tid: (-raw_chips[tid], wins_map[tid]),
        )
        return lottery_sorted

    def tank_incentive(self, team_id, standings, history):
        # Losing depletes chips at the same rate regardless of intent — structural anti-tank
        # Worst teams still hold their floor, but chips are the upside; tanking forfeits it
        if not history:
            return 0.2
        rank = _rank_by_wins_asc(history[-1], team_id)
        if rank <= 3:
            return 0.2   # floor protects them but chips are destroyed by tanking
        elif rank <= 7:
            return 0.12
        return 0.08


# ---------------------------------------------------------------------------
# System 10: The Wheel
# ---------------------------------------------------------------------------

class TheWheel:
    name = "The Wheel"

    def draft_order(self, history, constraints, rng):
        season = history[-1]
        lottery = _non_playoff_teams(season)  # worst first
        year = constraints.current_year

        # Each team's wheel slot for this year: (team_id + year) % 30
        # Lower slot = earlier pick
        def wheel_slot(tid):
            return (tid + year) % 30

        # Sort lottery teams by wheel slot ascending (lowest slot = pick 1)
        sorted_by_slot = sorted(lottery, key=lambda t: wheel_slot(t[0]))
        return [t[0] for t in sorted_by_slot]

    def tank_incentive(self, team_id, standings, history):
        # Completely deterministic — record has zero effect on draft position
        return 0.0


# ---------------------------------------------------------------------------
# System 11: Pre-2019 Legacy NBA
# ---------------------------------------------------------------------------

# Original NBA lottery odds table (worst to best, 14 slots)
LEGACY_NBA_ODDS = [25.0, 19.9, 15.6, 11.9, 8.8, 6.3, 4.3, 2.8, 1.7, 1.1, 0.8, 0.7, 0.6, 0.5]
LEGACY_LOTTERY_PICKS = 3  # pre-2019 drew only 3 lottery picks


class LegacyNBA:
    name = "Pre-2019 Legacy NBA"

    def draft_order(self, history, constraints, rng):
        season = history[-1]
        lottery = _non_playoff_teams(season)  # worst first
        weights = {lottery[i][0]: LEGACY_NBA_ODDS[i] for i in range(len(lottery))}
        lottery_picks = weighted_lottery_draw(weights, min(LEGACY_LOTTERY_PICKS, len(weights)), rng)
        remaining = [t[0] for t in lottery if t[0] not in lottery_picks]
        wins_map = {t[0]: t[1] for t in lottery}
        remaining_sorted = sorted(remaining, key=lambda tid: wins_map[tid])  # worst first (picks 4+)
        return lottery_picks + remaining_sorted

    def tank_incentive(self, team_id, standings, history):
        if not history:
            return 0.6
        rank = _rank_by_wins_asc(history[-1], team_id)
        # 25% vs 19.9% vs 15.6% — big spread at top, huge incentive for #1 slot
        if rank == 1:
            return 0.95
        elif rank <= 3:
            return 0.85
        elif rank <= 6:
            return 0.55
        elif rank <= 10:
            return 0.25
        return 0.1


# ---------------------------------------------------------------------------
# System 12: Equal Odds
# ---------------------------------------------------------------------------

class EqualOdds:
    name = "Equal Odds"

    def draft_order(self, history, constraints, rng):
        season = history[-1]
        lottery = _non_playoff_teams(season)  # worst first
        # Picks 1-4 drawn by equal-weight lottery from all 14 teams.
        # Picks 5-14 go strictly by record (worst first).
        weights = {t[0]: 1.0 for t in lottery}
        lottery_picks = weighted_lottery_draw(weights, min(4, len(weights)), rng)
        remaining = [t[0] for t in lottery if t[0] not in lottery_picks]
        wins_map = {t[0]: t[1] for t in lottery}
        remaining_sorted = sorted(remaining, key=lambda tid: wins_map[tid])  # worst first
        return lottery_picks + remaining_sorted

    def tank_incentive(self, team_id, standings, history):
        # Equal odds for all 14 teams — no benefit from losing
        return 0.05


# ---------------------------------------------------------------------------
# System 13: Top-4 Only Lottery
# ---------------------------------------------------------------------------

class TopFourOnly:
    name = "Top-4 Only Lottery"

    def draft_order(self, history, constraints, rng):
        season = history[-1]
        lottery = _non_playoff_teams(season)  # worst first
        # Only the 4 worst teams enter a weighted lottery for picks 1-4.
        # Worst team gets the highest weight (rank 1=4pts, rank 2=3pts, rank 3=2pts, rank 4=1pt).
        # Teams 5-14 receive picks 5-14 strictly by record.
        top4 = lottery[:4]   # 4 worst teams (worst first)
        rest = lottery[4:]   # remaining 10 teams

        # Rank-based weights: worst team gets largest weight
        weights = {top4[i][0]: float(4 - i) for i in range(len(top4))}
        lottery_picks = weighted_lottery_draw(weights, min(4, len(weights)), rng)

        wins_map = {t[0]: t[1] for t in lottery}
        rest_sorted = sorted([t[0] for t in rest], key=lambda tid: wins_map[tid])  # worst first
        return lottery_picks + rest_sorted

    def tank_incentive(self, team_id, standings, history):
        if not history:
            return 0.4
        rank = _rank_by_wins_asc(history[-1], team_id)
        # Within pool: worst team has the best odds (40%), so there is incentive to be #1 worst.
        # Teams 5-6 on the bubble have strong incentive to tank into the pool.
        if rank == 1:
            return 0.85  # best odds in pool (40%)
        elif rank <= 4:
            return 0.65  # in the pool, decreasing benefit
        elif rank <= 6:
            return 0.75  # on the bubble — strong incentive to tank in
        return 0.05  # no benefit once outside top-4


# ---------------------------------------------------------------------------
# All systems registry
# ---------------------------------------------------------------------------

ALL_SYSTEMS: list[LotterySystem] = [
    CurrentNBA(),
    FlatBottom(),
    PlayInBoost(),
    UEFACoefficient(),
    RCL(),
    LotteryTournament(),
    PureInversion(),
    GoldPlan(),
    ChipWindow(),
    TheWheel(),
    LegacyNBA(),
    EqualOdds(),
    TopFourOnly(),
]

SYSTEM_MAP: dict[str, LotterySystem] = {s.name: s for s in ALL_SYSTEMS}
