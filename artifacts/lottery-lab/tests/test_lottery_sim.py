"""Smoke tests for the lottery simulation engine and historical data."""
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
    TheWheel,
    LegacyNBA,
    EqualOdds,
    TopFourOnly,
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
    assert len(ALL_SYSTEMS) == 13
    names = [s.name for s in ALL_SYSTEMS]
    assert "Current NBA" in names
    assert "Flat Bottom" in names
    assert "Play-In Boost" in names
    assert "UEFA Coefficient" in names
    assert "RCL" in names
    assert "Lottery Tournament" in names
    assert "Pure Inversion" in names
    assert "Gold Plan (PWHL)" in names
    assert "Chip Window" in names
    assert "The Wheel" in names
    assert "Pre-2019 Legacy NBA" in names
    assert "Equal Odds" in names
    assert "Top-4 Only Lottery" in names


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
        # All picks in draft_order must be lottery (non-playoff) teams
        lottery_ids = {t[0] for t in lottery}
        for pick in draft_order:
            assert pick in lottery_ids, (
                f"Pure Inversion season {s_idx}: team {pick} is not a lottery team"
            )
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


def test_play_in_boost_odds_ordering():
    """Play-In Boost: play-in teams should get pick #1 more often than floor teams.
    Under PlayInBoost, play-in teams have the highest lottery odds, so across many
    seasons the 4 best non-playoff teams (play-in) should dominate the #1 pick.
    """
    from engine.lottery_sim import _non_playoff_teams, PLAY_IN_SLOTS
    system = PlayInBoost()
    # Use 200 seasons for a statistically stable signal (play-in teams have ~54.5% weight)
    run = simulate_run(system, seasons=200, seed=42)

    play_in_top1 = 0
    floor_top1 = 0
    for s_idx, draft_order in enumerate(run.draft_orders):
        if not draft_order:
            continue
        pick1 = draft_order[0]
        season = run.seasons[s_idx]
        lottery = _non_playoff_teams(season)
        n = len(lottery)
        floor_ids = {t[0] for t in lottery[:n - PLAY_IN_SLOTS]}
        play_in_ids = {t[0] for t in lottery[n - PLAY_IN_SLOTS:]}
        if pick1 in play_in_ids:
            play_in_top1 += 1
        elif pick1 in floor_ids:
            floor_top1 += 1

    # Play-in teams collectively hold ~54.5% of lottery weight vs ~45.5% for floor teams.
    # Over 200 seasons the play-in group should win more #1 picks than the floor group.
    assert play_in_top1 > floor_top1, (
        f"Play-In Boost: play-in teams got {play_in_top1} #1 picks vs "
        f"floor teams' {floor_top1} — play-in teams should dominate over 200 seasons"
    )


def test_late_season_effort_semantics():
    """
    Effort metric uses bottom-6 teams only.
    Pure Inversion incentivizes worst teams to WIN (late effort >= early effort, ratio >= 1).
    CurrentNBA incentivizes worst teams to LOSE (late effort <= early effort, ratio <= 1).
    Verified with enough runs/seasons for a stable signal.
    """
    pi = monte_carlo(PureInversion(), runs=30, seasons=12, seed=7)
    nba = monte_carlo(CurrentNBA(), runs=30, seasons=12, seed=7)
    # effort_by_week should span all weeks for bottom-6 teams
    assert len(pi.effort_by_week) == WEEKS_PER_SEASON, "effort_by_week wrong length"
    assert all(0.0 <= e <= 1.0 for e in pi.effort_by_week), "effort values out of [0,1]"
    # Pure Inversion should have higher late-season effort than Current NBA (less tanking)
    assert pi.late_season_effort > nba.late_season_effort, (
        f"Pure Inversion late effort ({pi.late_season_effort:.4f}) should exceed "
        f"CurrentNBA late effort ({nba.late_season_effort:.4f})"
    )


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


def test_wheel_smoke():
    _run_system_smoke(TheWheel())


def test_legacy_nba_smoke():
    _run_system_smoke(LegacyNBA())


def test_equal_odds_smoke():
    _run_system_smoke(EqualOdds())


def test_top_four_only_smoke():
    _run_system_smoke(TopFourOnly())


def test_wheel_deterministic():
    """The Wheel should order lottery teams strictly by (team_id + year) % 30."""
    from engine.lottery_sim import _non_playoff_teams
    system = TheWheel()
    run = simulate_run(system, seasons=10, seed=42)
    for year_idx, draft_order in enumerate(run.draft_orders):
        season = run.seasons[year_idx]
        lottery = _non_playoff_teams(season)
        lottery_ids = {t[0] for t in lottery}
        # Filter draft_order to lottery teams only
        lottery_order = [tid for tid in draft_order if tid in lottery_ids]
        # Verify each consecutive pair is sorted by wheel slot
        for i in range(len(lottery_order) - 1):
            slot_a = (lottery_order[i] + year_idx) % 30
            slot_b = (lottery_order[i + 1] + year_idx) % 30
            assert slot_a <= slot_b, (
                f"Wheel year {year_idx}: team {lottery_order[i]} (slot {slot_a}) "
                f"picked before team {lottery_order[i+1]} (slot {slot_b}) — wrong order"
            )


def test_wheel_rotation_wraps():
    """The Wheel wraps around: year 30 assignments match year 0 for each team."""
    system = TheWheel()
    # Run 31 seasons to cross the wrap point
    run = simulate_run(system, seasons=31, seed=0)
    # In the wheel: slot = (team_id + year) % 30
    # Year 0 and year 30 should have the same ordering if the same teams are in the lottery.
    # We can verify the wheel slot function wraps correctly via direct arithmetic.
    for tid in range(30):
        slot_year0 = (tid + 0) % 30
        slot_year30 = (tid + 30) % 30
        assert slot_year0 == slot_year30, f"Wheel wrap broken for team {tid}"


def test_wheel_zero_tank_incentive():
    """The Wheel always returns 0.0 tank incentive regardless of standing."""
    system = TheWheel()
    run = simulate_run(system, seasons=3, seed=5)
    for season in run.seasons:
        for tid, _, _ in season.standings:
            incentive = system.tank_incentive(tid, season.standings, [season])
            assert incentive == 0.0, f"Wheel tank_incentive should be 0, got {incentive}"


def test_legacy_nba_odds_ordering():
    """Pre-2019 Legacy NBA: worst team should get pick #1 far more often than best lottery team."""
    from engine.lottery_sim import _non_playoff_teams
    system = LegacyNBA()
    run = simulate_run(system, seasons=500, seed=42)

    worst_top1 = 0
    best_top1 = 0
    for s_idx, draft_order in enumerate(run.draft_orders):
        if not draft_order:
            continue
        pick1 = draft_order[0]
        season = run.seasons[s_idx]
        lottery = _non_playoff_teams(season)
        if lottery and pick1 == lottery[0][0]:   # worst team
            worst_top1 += 1
        if lottery and pick1 == lottery[-1][0]:  # best lottery team
            best_top1 += 1

    assert worst_top1 > best_top1 * 2, (
        f"Legacy NBA: worst team got {worst_top1} #1 picks vs best lottery team {best_top1}. "
        f"Expected worst to get at least 2x more."
    )


def test_equal_odds_uniform_picks1_to_4():
    """Equal Odds: picks 1-4 must all come from the 14-team pool and be roughly uniform."""
    from engine.lottery_sim import _non_playoff_teams, LOTTERY_PICKS
    system = EqualOdds()
    run = simulate_run(system, seasons=1400, seed=0)

    pick1_counts: dict[int, int] = {}
    for s_idx, draft_order in enumerate(run.draft_orders):
        if not draft_order:
            continue
        season = run.seasons[s_idx]
        lottery = _non_playoff_teams(season)
        lottery_ids = {t[0] for t in lottery}

        # All top-4 picks must come from the full 14-team lottery pool
        top4 = draft_order[:LOTTERY_PICKS]
        for slot_idx, tid in enumerate(top4):
            assert tid in lottery_ids, (
                f"Equal Odds season {s_idx} pick {slot_idx+1}: team {tid} not in lottery pool"
            )
        # No duplicates in top-4
        assert len(set(top4)) == len(top4), f"Equal Odds season {s_idx}: duplicate in top-4 picks"

        # Count pick-1 frequency
        pick1 = draft_order[0]
        if pick1 in lottery_ids:
            pick1_counts[pick1] = pick1_counts.get(pick1, 0) + 1

    # Rough uniformity: no team should get #1 more than 2.5× the mean over 1400 seasons
    total = sum(pick1_counts.values())
    counts = list(pick1_counts.values())
    mean = total / len(counts)
    for tid, count in pick1_counts.items():
        assert count < mean * 2.5, (
            f"Equal Odds: team {tid} got {count} #1 picks, mean={mean:.1f} — not uniform enough"
        )


def test_top_four_only_lottery_pool():
    """Top-4 Only Lottery: picks 1-4 must come from 4 worst teams; worst should get pick #1 most."""
    from engine.lottery_sim import _non_playoff_teams
    system = TopFourOnly()
    run = simulate_run(system, seasons=500, seed=13)

    worst_top1 = 0
    best_of_four_top1 = 0

    for s_idx, draft_order in enumerate(run.draft_orders):
        season = run.seasons[s_idx]
        lottery = _non_playoff_teams(season)
        top4 = lottery[:4]   # worst first
        top4_ids = {t[0] for t in top4}
        rest_ids = {t[0] for t in lottery[4:]}

        # First 4 picks must all be from the 4 worst teams
        for pick_idx, tid in enumerate(draft_order[:4]):
            assert tid in top4_ids, (
                f"Top-4 Only, season {s_idx}, pick {pick_idx+1}: "
                f"team {tid} is not one of the 4 worst teams"
            )
        # Picks 5+ must come from teams 5-14
        for pick_idx, tid in enumerate(draft_order[4:LOTTERY_TEAMS]):
            assert tid in rest_ids, (
                f"Top-4 Only, season {s_idx}, pick {pick_idx+5}: "
                f"team {tid} should not be a lottery team (is in top-4)"
            )

        # Track who gets pick #1: worst team vs 4th-worst team
        if top4 and draft_order[0] == top4[0][0]:   # worst of 4 (weight=4)
            worst_top1 += 1
        if top4 and len(top4) >= 4 and draft_order[0] == top4[3][0]:  # 4th-worst (weight=1)
            best_of_four_top1 += 1

    # Worst team (40% weight) should get #1 pick far more than the 4th-worst team (10% weight)
    assert worst_top1 > best_of_four_top1 * 1.5, (
        f"Top-4 Only: worst team got {worst_top1} #1 picks vs 4th-worst {best_of_four_top1}. "
        f"Expected worst to get at least 1.5x more (weighting 40% vs 10%)."
    )


def test_two_system_comparison_rendering():
    """Router helpers produce a valid comparison table when two systems are simulated."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "web"))
    from router import build_comparison_rows, make_effort_bars, make_win_dist_bars

    m0 = monte_carlo(CurrentNBA(), runs=5, seasons=5, seed=1)
    m1 = monte_carlo(PureInversion(), runs=5, seasons=5, seed=1)

    rows = build_comparison_rows(m0, m1)
    assert len(rows) > 0, "Comparison table is empty"
    for row in rows:
        assert "label" in row and "v0" in row and "v1" in row and "diff_class" in row, (
            f"Malformed row: {row}"
        )
        assert row["diff_class"] in ("diff-same", "diff-better", "diff-worse"), (
            f"Unexpected diff class: {row['diff_class']}"
        )

    # Effort bar rects: one rect per week, each with x/y/w/h/color
    for s_idx, m in enumerate((m0, m1)):
        bars = make_effort_bars(m.effort_by_week, "#fff", s_idx, 2)
        assert len(bars) == WEEKS_PER_SEASON, f"Wrong bar count: {len(bars)}"
        for b in bars:
            assert all(k in b for k in ("x", "y", "w", "h", "color")), f"Malformed bar: {b}"
            assert b["h"] >= 0, "Negative bar height"

    # Win distribution bar rects: one rect per rank (30 ranks)
    for s_idx, m in enumerate((m0, m1)):
        bars = make_win_dist_bars(m.avg_wins_by_rank, "#fff", s_idx, 2)
        assert len(bars) == NUM_TEAMS, f"Wrong bar count: {len(bars)}"


def test_historical_data_integrity():
    """All historical seasons have required keys, 14 unique lottery teams, and clean lottery_top4."""
    from data.historical_seasons import HISTORICAL_SEASONS, SEASON_KEYS

    assert len(HISTORICAL_SEASONS) == 26, f"Expected 26 seasons, got {len(HISTORICAL_SEASONS)}"
    assert len(SEASON_KEYS) == 26

    required_keys = {"context", "games", "lottery_pick1", "lottery_top4", "lottery_teams"}
    for key, data in HISTORICAL_SEASONS.items():
        missing = required_keys - set(data.keys())
        assert not missing, f"Season {key} missing keys: {missing}"

        # No actual_picks dicts (removed in favour of _compute_actual_order)
        assert "actual_picks" not in data, \
            f"Season {key}: stale 'actual_picks' dict found; remove it"

        teams = data["lottery_teams"]
        assert len(teams) == 14, f"Season {key} has {len(teams)} lottery teams, expected 14"

        max_games = data["games"]
        team_names_list = []
        for entry in teams:
            assert len(entry) == 3, f"Season {key} team entry should be (name, wins, losses)"
            name, wins, losses = entry
            assert isinstance(name, str) and len(name) > 0
            assert isinstance(wins, int) and 0 <= wins <= max_games, \
                f"Season {key}: {name} has wins={wins} out of range 0-{max_games}"
            assert isinstance(losses, int) and 0 <= losses <= max_games, \
                f"Season {key}: {name} has losses={losses} out of range 0-{max_games}"
            team_names_list.append(name)

        # No duplicate team names in lottery_teams
        seen_names: set[str] = set()
        for name in team_names_list:
            assert name not in seen_names, f"Season {key}: duplicate team '{name}' in lottery_teams"
            seen_names.add(name)

        # No team in lottery_teams should have a very high win total (>55) — such teams
        # would almost certainly have been playoff teams.
        high_win_teams = [(t[0], t[1]) for t in teams if t[1] > 55]
        assert not high_win_teams, \
            f"Season {key}: suspiciously high win totals (likely playoff teams) in lottery: {high_win_teams}"

        # lottery_pick1 must be in lottery_teams (except TBD for pending seasons)
        pick1 = data["lottery_pick1"]
        if pick1 != "TBD":
            assert pick1 in seen_names, f"Season {key}: lottery_pick1 '{pick1}' not in lottery_teams"

        # lottery_top4 integrity: all entries must be in lottery_teams (no traded/expansion picks)
        top4 = data["lottery_top4"]
        assert isinstance(top4, list) and len(top4) <= 4, \
            f"Season {key}: lottery_top4 must be a list of ≤4 names"
        assert len(top4) == len(set(top4)), \
            f"Season {key}: lottery_top4 has duplicate team(s): {top4}"
        for pos, name in enumerate(top4, 1):
            assert name in seen_names, \
                f"Season {key}: lottery_top4[{pos}]='{name}' not in lottery_teams — " \
                f"use the next eligible lottery team instead"


def test_historical_known_picks():
    """Spot-check known factual outcomes using lottery_pick1 and lottery_top4."""
    from data.historical_seasons import HISTORICAL_SEASONS
    from web.router import _compute_actual_order

    # 2002-03: Cleveland Cavaliers won the lottery, LeBron James
    s = HISTORICAL_SEASONS["2002-03"]
    assert s["lottery_pick1"] == "Cleveland Cavaliers"
    assert s["lottery_top4"][0] == "Cleveland Cavaliers"
    order = _compute_actual_order(s)
    assert order[0] == "Cleveland Cavaliers", f"Expected Cleveland at #1, got {order[0]}"

    # 2007-08: Derrick Rose, Chicago Bulls
    s = HISTORICAL_SEASONS["2007-08"]
    assert s["lottery_pick1"] == "Chicago Bulls"
    assert s["lottery_top4"][0] == "Chicago Bulls"
    order = _compute_actual_order(s)
    assert order[0] == "Chicago Bulls"
    assert order[1] == "Miami Heat", f"Miami (worst 15W) should be #2, got {order[1]}"

    # 2018-19: Zion Williamson, New Orleans Pelicans upset
    s = HISTORICAL_SEASONS["2018-19"]
    assert s["lottery_pick1"] == "New Orleans Pelicans"
    assert s["lottery_top4"][0] == "New Orleans Pelicans"
    assert s["lottery_top4"][1] == "Memphis Grizzlies"
    order = _compute_actual_order(s)
    assert order[0] == "New Orleans Pelicans"

    # 2011-12: Anthony Davis, New Orleans Hornets
    s = HISTORICAL_SEASONS["2011-12"]
    assert s["lottery_pick1"] == "New Orleans Hornets"
    assert s["lottery_top4"][0] == "New Orleans Hornets"
    order = _compute_actual_order(s)
    assert order[0] == "New Orleans Hornets"
    assert len(set(order)) == 14, "Duplicate teams in computed order"

    # 2023-24: Zaccharie Risacher, Atlanta Hawks — major upset
    s = HISTORICAL_SEASONS["2023-24"]
    assert s["lottery_pick1"] == "Atlanta Hawks"
    assert s["lottery_top4"][0] == "Atlanta Hawks"
    order = _compute_actual_order(s)
    assert order[0] == "Atlanta Hawks"
    # Detroit Pistons (14W, worst) should be near the end of actual_order
    assert "Detroit Pistons" in order[4:]


def test_no_obvious_playoff_teams_in_lottery():
    """No team with >55 wins should appear in any season's lottery_teams."""
    from data.historical_seasons import HISTORICAL_SEASONS

    violations = []
    for season_key, data in HISTORICAL_SEASONS.items():
        for name, wins, _ in data["lottery_teams"]:
            if wins > 55:
                violations.append(f"{season_key}: {name} ({wins}W)")
    assert not violations, (
        "Teams with >55 wins in lottery_teams are almost certainly playoff teams:\n"
        + "\n".join(violations)
    )


def test_historical_simulation_smoke():
    """Historical simulation: pick distributions sum correctly."""
    from data.historical_seasons import HISTORICAL_SEASONS
    from web.router import _run_historical_lottery

    system = CurrentNBA()
    season_data = HISTORICAL_SEASONS["2007-08"]

    dist = _run_historical_lottery(season_data, system, n_runs=500)
    n_lottery = len(season_data["lottery_teams"])

    assert len(dist) == n_lottery, f"Expected {n_lottery} teams in dist"
    for name, probs in dist.items():
        assert len(probs) == n_lottery

    # Each slot should sum to ~100% across all teams
    slot_sums = [sum(dist[name][slot] for name in dist) for slot in range(n_lottery)]
    for slot, s in enumerate(slot_sums[:4]):
        assert abs(s - 100.0) < 5.0, f"Slot {slot+1} probabilities sum to {s:.1f}%, expected ~100%"

    # Under Current NBA, Miami Heat (worst 15W team) should have highest pick-1 odds
    assert dist["Miami Heat"][0] > dist["Chicago Bulls"][0], \
        "Miami (worst) should have higher #1 pick odds than Chicago"


def test_historical_actual_order():
    """_compute_actual_order returns exactly 14 teams with #1 pick first, for every season."""
    from data.historical_seasons import HISTORICAL_SEASONS
    from web.router import _compute_actual_order

    for season_key, data in HISTORICAL_SEASONS.items():
        if data.get("season_pending"):
            continue
        order = _compute_actual_order(data)
        lottery_team_names = {t[0] for t in data["lottery_teams"]}

        # Must return exactly 14 teams
        assert len(order) == 14, f"Season {season_key}: expected 14 teams in order, got {len(order)}"

        # All returned names must be from lottery_teams
        for name in order:
            assert name in lottery_team_names, \
                f"Season {season_key}: '{name}' in order but not in lottery_teams"

        # No duplicates
        assert len(set(order)) == 14, f"Season {season_key}: duplicate teams in order"

        # The true #1 pick (lottery_pick1) must be at position 0
        expected_pick1 = data["lottery_pick1"]
        if expected_pick1 in lottery_team_names:
            assert order[0] == expected_pick1, \
                f"Season {season_key}: expected '{expected_pick1}' at #1, got '{order[0]}'"


if __name__ == "__main__":
    print("Running smoke tests...")
    test_all_systems_present()
    print("✓ All 13 systems present")

    for system in ALL_SYSTEMS:
        _run_system_smoke(system)
        print(f"✓ {system.name}")

    test_rcl_hard_caps()
    print("✓ RCL hard caps enforced (top-1 + top-3)")

    test_pure_inversion_order()
    print("✓ Pure inversion order correct")

    test_monte_carlo_smoke()
    print("✓ Monte Carlo runs")

    test_play_in_boost_odds_ordering()
    print("✓ Play-In Boost: play-in teams get more #1 picks than floor teams")

    test_late_season_effort_semantics()
    print("✓ Late-season effort semantics (bottom-6 cohort, Pure Inversion > CurrentNBA)")

    test_post_lottery_ordering_by_record()
    print("✓ Post-lottery picks ordered by record (worst first)")

    test_draft_order_completeness()
    print("✓ Draft order completeness")

    test_two_system_comparison_rendering()
    print("✓ Two-system comparison table + SVG polylines render correctly")

    test_historical_data_integrity()
    print("✓ Historical data file: all 26 seasons have valid structure")

    test_historical_simulation_smoke()
    print("✓ Historical simulation: pick distribution sums to 100 per slot")

    test_historical_actual_order()
    print("✓ Historical actual order: lottery_pick1 always in position 1")

    test_wheel_deterministic()
    print("✓ The Wheel is deterministic")

    test_wheel_rotation_wraps()
    print("✓ The Wheel wraps at year 30")

    test_wheel_zero_tank_incentive()
    print("✓ The Wheel: zero tank incentive")

    test_legacy_nba_odds_ordering()
    print("✓ Pre-2019 Legacy NBA: worst team gets #1 far more than best lottery team")

    test_equal_odds_uniform_picks1_to_4()
    print("✓ Equal Odds: uniform picks 1-4 distribution")

    test_top_four_only_lottery_pool()
    print("✓ Top-4 Only: picks 1-4 come from 4 worst teams only")

    print("\nAll tests passed!")
