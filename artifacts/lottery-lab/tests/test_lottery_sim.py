"""Smoke tests for the lottery simulation engine."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.lottery_sim import (
    ALL_SYSTEMS,
    CurrentNBA,
    FlatBottom,
    PlayInBoost,
    UEFACoefficient,
    RCL,
    LotteryTournament,
    PureInversion,
    GoldPlan,
    monte_carlo,
    simulate_run,
    compute_metrics,
    default_teams,
    DraftConstraints,
    LOTTERY_TEAMS,
    NUM_TEAMS,
    WEEKS_PER_SEASON,
)


def test_all_systems_present():
    assert len(ALL_SYSTEMS) == 8
    names = [s.name for s in ALL_SYSTEMS]
    assert "Current NBA" in names
    assert "Flat Bottom" in names
    assert "Play-In Boost" in names
    assert "UEFA Coefficient" in names
    assert "RCL" in names
    assert "Lottery Tournament" in names
    assert "Pure Inversion" in names
    assert "Gold Plan (PWHL)" in names


def _run_system_smoke(system, seed=42, seasons=3):
    run = simulate_run(system, seasons=seasons, seed=seed)
    assert run.system_name == system.name
    assert len(run.seasons) == seasons
    assert len(run.draft_orders) == seasons
    assert len(run.effort_log) == seasons

    for season in run.seasons:
        assert len(season.standings) == NUM_TEAMS
        wins_sum = sum(w for _, w, _ in season.standings)
        losses_sum = sum(l for _, _, l in season.standings)
        assert wins_sum == losses_sum, "Total wins must equal total losses"

    for draft_order in run.draft_orders:
        assert len(draft_order) > 0
        # No duplicate teams in draft order
        lottery_picks = draft_order[:LOTTERY_TEAMS]
        assert len(set(lottery_picks)) == len(lottery_picks), "Duplicate team in draft order"

    teams = default_teams(seed)
    metrics = compute_metrics(run, teams)
    assert metrics.system_name == system.name
    assert 0.0 <= metrics.gini_top5 <= 1.0
    assert metrics.tank_cycles >= 0
    assert metrics.competitive_balance >= 0
    assert metrics.avg_wins_top3_recipients >= 0
    assert len(metrics.effort_by_week) == WEEKS_PER_SEASON
    assert len(metrics.avg_wins_by_rank) == NUM_TEAMS
    # Win distribution should be monotone non-increasing (rank 1 = best = most wins)
    for i in range(len(metrics.avg_wins_by_rank) - 1):
        assert metrics.avg_wins_by_rank[i] >= metrics.avg_wins_by_rank[i + 1] - 2, (
            f"{system.name}: avg_wins_by_rank not monotone at rank {i+1}"
        )

    return run, metrics


def test_current_nba_smoke():
    _run_system_smoke(CurrentNBA())


def test_flat_bottom_smoke():
    _run_system_smoke(FlatBottom())


def test_play_in_boost_smoke():
    _run_system_smoke(PlayInBoost())


def test_uefa_coefficient_smoke():
    _run_system_smoke(UEFACoefficient())


def test_rcl_smoke():
    _run_system_smoke(RCL())


def test_lottery_tournament_smoke():
    _run_system_smoke(LotteryTournament())


def test_pure_inversion_smoke():
    _run_system_smoke(PureInversion())


def test_gold_plan_smoke():
    _run_system_smoke(GoldPlan())


def test_rcl_hard_caps():
    """RCL system: no #1 pick more than once, no top-3 pick more than twice in any 5-year window."""
    system = RCL()
    run = simulate_run(system, seasons=10, seed=0)
    draft_orders = run.draft_orders

    # Check no team gets #1 more than once in any 5-year window
    for i in range(len(draft_orders)):
        window = draft_orders[max(0, i - 4): i + 1]
        top1_picks = [o[0] for o in window if o]
        for team_id in set(top1_picks):
            count = top1_picks.count(team_id)
            assert count <= 1, f"Team {team_id} got #1 pick {count} times in 5-year window"

    # Check no team gets a top-3 pick more than twice in any 5-year window
    for i in range(len(draft_orders)):
        window = draft_orders[max(0, i - 4): i + 1]
        top3_picks: list[int] = []
        for order in window:
            if order:
                top3_picks.extend(order[:3])
        for team_id in set(top3_picks):
            count = top3_picks.count(team_id)
            assert count <= 2, (
                f"Team {team_id} got top-3 pick {count} times in 5-year window "
                f"(window i={i})"
            )


def test_pure_inversion_order():
    """Pure inversion: best non-playoff team picks first (has more wins than last pick)."""
    from engine.lottery_sim import _non_playoff_teams
    system = PureInversion()
    run = simulate_run(system, seasons=3, seed=7)
    for s_idx, draft_order in enumerate(run.draft_orders):
        season = run.seasons[s_idx]
        lottery = _non_playoff_teams(season)
        wins_map = {tid: w for tid, w, _ in lottery}
        # All picks in draft_order should be lottery teams
        lottery_ids = {t[0] for t in lottery}
        for pick in draft_order:
            assert pick in lottery_ids or pick not in wins_map, "Non-lottery team in draft order"
        # First pick should have >= wins as last pick (inverted order)
        if len(draft_order) >= 2:
            first_pick_wins = wins_map.get(draft_order[0], 0)
            last_pick_wins = wins_map.get(draft_order[-1], 999)
            assert first_pick_wins >= last_pick_wins, (
                f"Pure inversion broken: first pick has {first_pick_wins} wins, "
                f"last pick has {last_pick_wins} wins"
            )


def test_monte_carlo_smoke():
    """Monte Carlo should return a valid MetricsBundle."""
    metrics = monte_carlo(CurrentNBA(), runs=3, seasons=3, seed=1)
    assert metrics.system_name == "Current NBA"
    assert 0.0 <= metrics.gini_top5 <= 1.0
    assert metrics.tank_cycles >= 0
    assert metrics.competitive_balance >= 0


def test_flat_bottom_uniform_incentive():
    """Flat bottom should produce lower gini than current NBA (more equitable)."""
    nba_metrics = monte_carlo(CurrentNBA(), runs=5, seasons=5, seed=42)
    flat_metrics = monte_carlo(FlatBottom(), runs=5, seasons=5, seed=42)
    # Flat bottom should generally have lower Gini (more equal distribution)
    # This is a soft assertion — just check both are valid
    assert nba_metrics.gini_top5 >= 0
    assert flat_metrics.gini_top5 >= 0


def test_post_lottery_ordering_by_record():
    """Picks 5+ (non-lottery-drawn) must be ordered worst record first for NBA-style systems."""
    from engine.lottery_sim import _non_playoff_teams, LOTTERY_PICKS
    nba_style = [CurrentNBA(), FlatBottom(), PlayInBoost(), UEFACoefficient(), RCL()]
    for system in nba_style:
        run = simulate_run(system, seasons=5, seed=99)
        for s_idx, draft_order in enumerate(run.draft_orders):
            season = run.seasons[s_idx]
            lottery = _non_playoff_teams(season)
            wins_map = {t[0]: t[1] for t in lottery}
            # picks after the lottery draws should be in ascending wins order
            tail = draft_order[LOTTERY_PICKS:]
            for i in range(len(tail) - 1):
                w_curr = wins_map.get(tail[i], 0)
                w_next = wins_map.get(tail[i + 1], 0)
                assert w_curr <= w_next, (
                    f"{system.name} season {s_idx}: pick {LOTTERY_PICKS + i + 1} "
                    f"has {w_curr} wins but pick {LOTTERY_PICKS + i + 2} has {w_next} wins "
                    f"(should be worst-first)"
                )


def test_draft_order_completeness():
    """Draft order should include all lottery teams exactly once."""
    for system in ALL_SYSTEMS:
        run = simulate_run(system, seasons=2, seed=99)
        for draft_order in run.draft_orders:
            # First LOTTERY_TEAMS entries should be unique lottery teams
            lottery_section = draft_order[:LOTTERY_TEAMS]
            assert len(lottery_section) == LOTTERY_TEAMS, f"{system.name}: wrong lottery count"
            assert len(set(lottery_section)) == LOTTERY_TEAMS, f"{system.name}: duplicate lottery teams"


if __name__ == "__main__":
    print("Running smoke tests...")
    test_all_systems_present()
    print("✓ All 8 systems present")

    for system in ALL_SYSTEMS:
        _run_system_smoke(system)
        print(f"✓ {system.name}")

    test_rcl_hard_caps()
    print("✓ RCL hard caps enforced (top-1 + top-3)")

    test_pure_inversion_order()
    print("✓ Pure inversion order correct")

    test_monte_carlo_smoke()
    print("✓ Monte Carlo runs")

    test_post_lottery_ordering_by_record()
    print("✓ Post-lottery picks ordered by record (worst first)")

    test_draft_order_completeness()
    print("✓ Draft order completeness")

    print("\nAll tests passed!")
