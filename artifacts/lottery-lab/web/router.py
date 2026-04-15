from __future__ import annotations

import json
import random
import time
from pathlib import Path
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from engine.chip_window_sim import simulate_chip_window_league, result_to_json
from engine.lottery_sim import (
    ALL_SYSTEMS,
    SYSTEM_MAP,
    monte_carlo,
    MetricsBundle,
    SeasonResult,
    DraftConstraints,
    NBA_TEAM_NAMES,
    NUM_TEAMS,
    WEEKS_PER_SEASON,
    GAMES_PER_SEASON,
    PLAYOFF_SPOTS,
)
from data.historical_seasons import HISTORICAL_SEASONS, SEASON_KEYS

router = APIRouter()
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

CHART_COLORS = ["#ff8c00", "#4ade80"]

# ── System explainers ───────────────────────────────────────────────────────
# odds: list of 14 floats (slot 1=worst record → slot 14=best non-playoff), or None if variable

SYSTEM_EXPLAINERS: dict[str, dict] = {
    "Current NBA": {
        "desc": (
            "The three worst teams each receive 14% odds for pick #1. "
            "Odds taper to 0.5% at the 14th slot. Picks 1–4 are drawn by weighted lottery; "
            "picks 5–14 follow record order (worst first)."
        ),
        "odds": [14.0, 14.0, 14.0, 12.5, 10.5, 9.0, 7.5, 6.0, 4.5, 3.0, 2.0, 1.5, 1.0, 0.5],
        "odds_note": None,
    },
    "Flat Bottom": {
        "desc": (
            "Every one of the 14 lottery teams gets exactly equal odds (~7.1% each) for pick #1. "
            "The lottery still applies to picks 1–4; picks 5–14 go by record. "
            "Losing an extra game gives no lottery advantage whatsoever."
        ),
        "odds": [round(100 / 14, 1)] * 14,
        "odds_note": None,
    },
    "Play-In Boost": {
        "desc": (
            "The 4 teams that just missed the playoffs (play-in zone) receive the highest lottery odds "
            "— equal to or better than any floor team. "
            "Being competitive enough for the play-in is the reward; bottoming out is not."
        ),
        "odds": [0.5, 1.0, 1.5, 2.0, 3.0, 4.5, 6.0, 7.5, 9.0, 10.5, 12.5, 14.0, 14.0, 14.0],
        "odds_note": "Slots 11–14 are play-in teams (closest to the playoff cut)",
    },
    "UEFA Coefficient": {
        "desc": (
            "A rolling 3-year weighted score (50% current / 30% prior / 20% two years ago) determines "
            "each team's lottery weight. One bad season barely moves the needle — you need sustained "
            "futility to earn top odds. This kills one-year tanking but rewards genuine rebuilds."
        ),
        # Representative after 3+ seasons of team divergence (approximately)
        "odds": [17.5, 16.5, 14.5, 12.0, 9.5, 7.5, 5.5, 4.0, 3.0, 2.5, 2.0, 2.0, 1.5, 2.0],
        "odds_note": "Approximate — actual odds vary by each team's 3-year performance history.",
    },
    "RCL": {
        "desc": (
            "Multi-year coefficient (similar to UEFA) plus head-to-head record versus other lottery "
            "teams. Hard caps enforce fairness: no team can receive the #1 pick more than once in "
            "5 years, or a top-3 pick more than twice in 5 years."
        ),
        # Representative; capped teams have weight redistributed
        "odds": [16.0, 15.0, 13.5, 11.5, 9.5, 7.5, 6.0, 4.5, 3.5, 2.5, 2.0, 2.0, 2.0, 4.5],
        "odds_note": "Approximate — teams capped on #1 or top-3 picks are excluded from those slots and their weight is redistributed.",
    },
    "Lottery Tournament": {
        "desc": (
            "The 8 worst teams by record play a single-elimination tournament. "
            "The tournament winner earns pick #1. Teams 9–14 get picks 9–14 by record. "
            "You need to be in the bottom 8 AND win games to land the top pick."
        ),
        # Approximate tournament win probabilities (slightly favors worse records)
        "odds": [18.0, 16.0, 14.0, 13.0, 12.0, 11.0, 9.0, 7.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "odds_note": "Slots 1–8 enter the tournament. Slots 9–14 cannot win pick #1. Values are approximate win-probability estimates.",
    },
    "Pure Inversion": {
        "desc": (
            "No lottery at all. The best non-playoff team picks #1; the worst non-playoff team picks "
            "last. This completely inverts the tanking incentive — losing hurts your draft position. "
            "Every team should try hard all season."
        ),
        # Fully deterministic: only slot 14 (best non-playoff) gets pick 1
        "odds": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 100.0],
        "odds_note": "Deterministic. Only the best non-playoff team (slot 14) gets pick #1.",
    },
    "Gold Plan (PWHL)": {
        "desc": (
            "Draft order is determined by wins accumulated after a team is mathematically eliminated "
            "from playoff contention. Teams that keep competing hard after elimination are rewarded. "
            "This system is used in real life by the PWHL."
        ),
        # Approximate: mid-table lottery teams eliminated mid-season often accumulate the most post-elim wins
        "odds": [5.5, 6.5, 8.0, 9.0, 9.0, 9.0, 8.5, 8.0, 7.5, 6.5, 6.0, 5.5, 5.0, 4.5],
        "odds_note": "Approximate — actual odds depend on when each team is eliminated and post-elimination performance, not record directly.",
    },
    "Chip Window": {
        "desc": (
            "Proposed by Ron Bronson (2026). Activates at game 60 for all non-top-6-seed teams. "
            "Each team starts with 100 chips and must wager at least 10 per game (options: 10 or 25). "
            "A win returns the wager; a loss permanently deducts it. Teams with ≥ 100 chips at "
            "season's end may double once — forfeit 100 chips to double the remainder. "
            "Final lottery odds are proportional to chip totals, floored at what the Current NBA "
            "system would give each team. Tanking is structurally impossible: losing depletes chips "
            "at the same rate regardless of intent, and the floor prevents double punishment for "
            "genuinely bad teams. Every late-season game carries chip stakes — a public chip "
            "leaderboard alongside the standings turns garbage time into must-watch TV."
        ),
        "odds": [14.0, 14.0, 13.5, 12.0, 10.0, 8.5, 7.0, 5.5, 4.0, 3.0, 2.5, 2.0, 1.5, 2.5],
        "odds_note": (
            "Dynamic — odds depend on each team's chip total after the game-60 window, not just "
            "their record. Worst teams fall to their Current NBA floor when chips are depleted; "
            "teams that win during the window can exceed their floor and climb the odds board. "
            "The double mechanic (≥ 100 chips) can further amplify a strong window performance."
        ),
    },
    "The Wheel": {
        "desc": (
            "Every team cycles through all 30 pick positions on a fixed 30-year rotation. "
            "No randomness — each team's draft slot is known years in advance. "
            "Tanking is completely pointless because record has zero impact on draft position."
        ),
        "odds": None,
        "odds_note": "Deterministic. Draft slot is pre-assigned by rotation; all teams pick 1st exactly once every 30 years.",
    },
    "Pre-2019 Legacy NBA": {
        "desc": (
            "The original NBA lottery system in use before 2019. The worst team receives 25% odds for pick #1, "
            "the 2nd-worst 19.9%, the 3rd-worst 15.6%, tapering sharply to 0.5% at slot 14. "
            "Only picks 1–3 are drawn by lottery; picks 4–14 follow record order."
        ),
        "odds": [25.0, 19.9, 15.6, 11.9, 8.8, 6.3, 4.3, 2.8, 1.7, 1.1, 0.8, 0.7, 0.6, 0.5],
        "odds_note": "Authentic pre-2019 odds. Only the top 3 picks are drawn by lottery; pick 4+ go strictly by record.",
    },
    "Equal Odds": {
        "desc": (
            "All 14 lottery teams have exactly equal 7.14% odds for the #1 pick. "
            "Picks 1–4 are drawn by equal-weight lottery; picks 5–14 go strictly by record (worst first). "
            "Maximally random — record has no bearing whatsoever on landing a top-4 pick."
        ),
        "odds": [round(100 / 14, 1)] * 14,
        "odds_note": "Picks 1–4 are drawn by equal-weight lottery from all 14 teams. Picks 5–14 go by record.",
    },
    "Top-4 Only Lottery": {
        "desc": (
            "Only the 4 worst teams by record enter a weighted lottery for picks 1–4. "
            "The worst team gets the most lottery weight (40%), tapering to 10% for the 4th-worst. "
            "Teams ranked 5–14 receive picks 5–14 in strict record order."
        ),
        "odds": [40.0, 30.0, 20.0, 10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "odds_note": "Only the 4 worst teams enter the lottery. Weights: 40/30/20/10% (worst to 4th-worst). Slots 5–14 get picks 5–14 by record.",
    },
}


# ── Pre-computation helpers ────────────────────────────────────────────────

def make_bar_rows(metrics: MetricsBundle, top_n: int = 14) -> list[dict]:
    """Return rows sorted by pick-1% descending. Each row includes all 5 pick slots."""
    rows = []
    for team_id in range(NUM_TEAMS):
        slots = metrics.pick_distribution.get(team_id, [0.0] * 5)
        pick1 = slots[0] if slots else 0.0
        rows.append({
            "name": NBA_TEAM_NAMES[team_id],
            "pct": round(pick1, 2),           # primary sort / bar chart value = pick-1%
            "pick1_pct": round(slots[0] if len(slots) > 0 else 0.0, 2),
            "pick2_pct": round(slots[1] if len(slots) > 1 else 0.0, 2),
            "pick3_pct": round(slots[2] if len(slots) > 2 else 0.0, 2),
            "pick4_pct": round(slots[3] if len(slots) > 3 else 0.0, 2),
            "pick5_pct": round(slots[4] if len(slots) > 4 else 0.0, 2),
        })
    rows.sort(key=lambda r: r["pick1_pct"], reverse=True)
    return rows[:top_n]


def make_effort_bars(week_efforts: list[float], color: str, series_idx: int, n_series: int) -> list[dict]:
    """Return bar rect specs for the effort chart (one rect per week)."""
    chart_w, chart_h = 800, 180
    pad_l, pad_r, pad_t, pad_b = 36, 16, 12, 24
    inner_w = chart_w - pad_l - pad_r
    inner_h = chart_h - pad_t - pad_b
    min_v, max_v = 0.4, 1.05
    span = max_v - min_v
    n = len(week_efforts)
    group_w = inner_w / max(n, 1)
    bar_w = group_w * 0.85 / max(n_series, 1)
    x_offset = (group_w - bar_w * n_series) / 2 + series_idx * bar_w
    bottom_y = pad_t + inner_h
    rects = []
    for i, eff in enumerate(week_efforts):
        clamped = max(min_v, min(max_v, eff))
        bar_h = inner_h * (clamped - min_v) / span
        x = pad_l + i * group_w + x_offset
        rects.append({
            "x": round(x, 1), "y": round(bottom_y - bar_h, 1),
            "w": round(max(bar_w - 1, 1), 1), "h": round(bar_h, 1), "color": color,
        })
    return rects


def make_pick_svg_bar(pct: float, max_pct: float, color: str, width: int = 60) -> str:
    bar_w = int((pct / max(max_pct, 0.01)) * (width - 4))
    return (
        f'<svg viewBox="0 0 {width} 10" style="width:{width}px;height:10px;display:block">'
        f'<rect x="0" y="1" width="{bar_w}" height="8" fill="{color}" opacity="0.8" rx="1"/>'
        f"</svg>"
    )


def build_comparison_rows(m0: MetricsBundle, m1: MetricsBundle) -> list[dict]:
    """Build pre-computed comparison rows for the metrics table."""
    specs = [
        ("Late-season effort ratio", m0.late_season_effort, m1.late_season_effort, False, "{:.4f}"),
        ("Repeat #1 pick frequency", m0.repeat_top1_frequency, m1.repeat_top1_frequency, True, "{:.4f}"),
        ("Gini coeff (top-5 picks)", m0.gini_top5, m1.gini_top5, True, "{:.4f}"),
        ("Avg tanking teams/season", m0.tank_cycles, m1.tank_cycles, True, "{:.2f}"),
        ("Competitive balance (σ wins)", m0.competitive_balance, m1.competitive_balance, True, "{:.2f}"),
        ("Avg wins of top-3 recipients", m0.avg_wins_top3_recipients, m1.avg_wins_top3_recipients, True, "{:.2f}"),
    ]
    rows = []
    for label, v0, v1, lower_better, fmt in specs:
        diff = v1 - v0
        abs_diff = abs(diff)
        baseline = max(abs(v0), 0.001)
        relative_diff = abs_diff / baseline
        if relative_diff < 0.05:
            diff_class = "diff-same"
            diff_str = "—"
        elif (lower_better and diff < 0) or (not lower_better and diff > 0):
            diff_class = "diff-better"
            diff_str = f"{diff:+.4f}"
        else:
            diff_class = "diff-worse"
            diff_str = f"{diff:+.4f}"
        rows.append({
            "label": label,
            "v0": fmt.format(v0),
            "v1": fmt.format(v1),
            "diff_class": diff_class,
            "diff_str": diff_str,
        })
    return rows


def make_win_dist_bars(avg_wins_by_rank: list[float], color: str, series_idx: int, n_series: int) -> list[dict]:
    """Return bar rect specs for the win distribution chart (one rect per rank)."""
    chart_w, chart_h = 800, 180
    pad_l, pad_r, pad_t, pad_b = 36, 16, 12, 24
    inner_w = chart_w - pad_l - pad_r
    inner_h = chart_h - pad_t - pad_b
    max_v = float(GAMES_PER_SEASON)
    n = len(avg_wins_by_rank)
    group_w = inner_w / max(n, 1)
    bar_w = group_w * 0.85 / max(n_series, 1)
    x_offset = (group_w - bar_w * n_series) / 2 + series_idx * bar_w
    bottom_y = pad_t + inner_h
    rects = []
    for i, wins in enumerate(avg_wins_by_rank):
        bar_h = inner_h * max(0.0, min(max_v, wins)) / max_v
        x = pad_l + i * group_w + x_offset
        rects.append({
            "x": round(x, 1), "y": round(bottom_y - bar_h, 1),
            "w": round(max(bar_w - 1, 1), 1), "h": round(bar_h, 1), "color": color,
        })
    return rects


def build_win_dist_chart_meta() -> dict:
    chart_w, chart_h = 800, 180
    pad_l, pad_r, pad_t, pad_b = 36, 16, 12, 24
    inner_w = chart_w - pad_l - pad_r
    inner_h = chart_h - pad_t - pad_b
    max_v = float(GAMES_PER_SEASON)

    grid = []
    for v in [20, 30, 40, 50, 60, 70]:
        gy = pad_t + inner_h * (1.0 - v / max_v)
        grid.append({"v": str(v), "y": round(gy, 1)})

    rank_labels = []
    for rank in [1, 5, 10, 15, 16, 20, 25, 30]:
        gx = pad_l + ((rank - 1) / max(NUM_TEAMS - 1, 1)) * inner_w
        rank_labels.append({"label": str(rank), "x": round(gx, 1)})

    cutoff_x = round(pad_l + ((PLAYOFF_SPOTS - 1) / max(NUM_TEAMS - 1, 1)) * inner_w, 1)

    return {
        "chart_w": chart_w,
        "chart_h": chart_h,
        "pad_l": pad_l,
        "pad_t": pad_t,
        "cutoff_x": cutoff_x,
        "grid": grid,
        "rank_labels": rank_labels,
    }


def build_effort_chart_meta() -> dict:
    chart_w, chart_h = 800, 180
    pad_l, pad_r, pad_t, pad_b = 36, 16, 12, 24
    inner_w = chart_w - pad_l - pad_r
    inner_h = chart_h - pad_t - pad_b
    min_v, span = 0.4, 0.65

    grid = []
    for v in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        gy = pad_t + inner_h * (1.0 - (v - min_v) / span)
        grid.append({"v": f"{v:.1f}", "y": round(gy, 1)})

    week_labels = []
    for wk in range(0, WEEKS_PER_SEASON, 4):
        gx = pad_l + (wk / max(WEEKS_PER_SEASON - 1, 1)) * inner_w
        week_labels.append({"label": f"W{wk + 1}", "x": round(gx, 1)})

    return {
        "chart_w": chart_w,
        "chart_h": chart_h,
        "pad_l": pad_l,
        "pad_t": pad_t,
        "mid_x": round(pad_l + 0.5 * inner_w, 1),
        "grid": grid,
        "week_labels": week_labels,
    }


def build_standings_table(metrics: MetricsBundle) -> list[dict]:
    """Build standings table rows sorted by avg wins descending."""
    rows = []
    for tid in range(NUM_TEAMS):
        avg_w = metrics.avg_wins_by_team.get(tid, 0.0)
        avg_l = round(GAMES_PER_SEASON - avg_w, 1)
        slots = metrics.pick_distribution.get(tid, [0.0] * 5)
        pick1 = slots[0] if slots else 0.0
        top5_sum = sum(slots)  # total % across all 5 picks (each slot sums to 100 across teams)
        rows.append({
            "name": NBA_TEAM_NAMES[tid],
            "avg_wins": avg_w,
            "avg_losses": avg_l,
            "pick1_pct": round(pick1, 2),
            "top5_pct": round(top5_sum, 2),
        })
    rows.sort(key=lambda r: r["avg_wins"], reverse=True)
    return rows


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    system_names = [s.name for s in ALL_SYSTEMS]
    explainers = {name: SYSTEM_EXPLAINERS.get(name, {}) for name in system_names}
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "systems": system_names,
            "explainers": explainers,
            "season_keys": SEASON_KEYS,
            "show_historical": False,
        },
    )


@router.post("/simulate", response_class=HTMLResponse)
async def simulate(
    request: Request,
    systems: list[str] = Form(default=[]),
    runs: int = Form(default=50),
    seasons: int = Form(default=15),
    seed: Optional[str] = Form(default=None),
):
    runs = max(5, min(500, runs))
    seasons = max(3, min(30, seasons))
    seed_val: Optional[int] = None
    if seed and seed.strip().isdigit():
        seed_val = int(seed.strip())

    selected = [SYSTEM_MAP[s] for s in systems if s in SYSTEM_MAP][:2]
    if not selected:
        selected = [ALL_SYSTEMS[0]]

    t0 = time.perf_counter()
    results: list[MetricsBundle] = []
    for system in selected:
        m = monte_carlo(system, runs=runs, seasons=seasons, seed=seed_val)
        results.append(m)
    elapsed = round(time.perf_counter() - t0, 2)

    bar_rows_list = [make_bar_rows(m) for m in results]
    n_series = len(results)
    effort_bars = [
        make_effort_bars(m.effort_by_week, CHART_COLORS[i], i, n_series)
        for i, m in enumerate(results)
    ]

    # Pick tables: 5-column per-slot distribution (sortable via JS in template)
    pick_tables: list[list[dict]] = []
    for idx, m in enumerate(results):
        color = CHART_COLORS[idx]
        rows_raw = bar_rows_list[idx]  # already sorted by pick1_pct desc
        max_pick1 = rows_raw[0]["pick1_pct"] if rows_raw else 1.0
        table_rows = []
        for row in rows_raw:
            table_rows.append({
                **row,
                "bar_svg": make_pick_svg_bar(row["pick1_pct"], max(max_pick1, 0.01), color),
            })
        pick_tables.append(table_rows)

    win_dist_bars = [
        make_win_dist_bars(m.avg_wins_by_rank, CHART_COLORS[i], i, n_series)
        for i, m in enumerate(results)
    ]
    win_dist_meta = build_win_dist_chart_meta()
    effort_meta = build_effort_chart_meta()
    comparison_rows = build_comparison_rows(results[0], results[1]) if len(results) == 2 else []
    is_comparison = len(results) == 2

    # Standings tables
    standings_tables = [
        build_standings_table(m)
        for m in results
    ]

    # Selected system explainers
    result_explainers = [
        SYSTEM_EXPLAINERS.get(m.system_name, {})
        for m in results
    ]

    # Single-system metric card color classes
    def card_class(value: float, good_below: float | None, bad_above: float | None,
                   good_above: float | None = None, bad_below: float | None = None) -> str:
        if good_above is not None and value > good_above:
            return "good"
        if bad_below is not None and value < bad_below:
            return "bad"
        if good_below is not None and value < good_below:
            return "good"
        if bad_above is not None and value > bad_above:
            return "bad"
        return ""

    metric_cards = []
    if results:
        m = results[0]
        metric_cards = [
            {
                "label": "Late-season effort",
                "value": f"{m.late_season_effort:.3f}",
                "cls": card_class(m.late_season_effort, good_below=None, bad_above=None,
                                  good_above=0.95, bad_below=0.80),
                "sub": "final 20 / first 62 games",
            },
            {
                "label": "Repeat #1 pick",
                "value": f"{m.repeat_top1_frequency * 100:.1f}%",
                "cls": card_class(m.repeat_top1_frequency, good_below=0.10, bad_above=0.25),
                "sub": "same team within 5 yrs",
            },
            {
                "label": "Gini (top-5 picks)",
                "value": f"{m.gini_top5:.3f}",
                "cls": card_class(m.gini_top5, good_below=0.30, bad_above=0.50),
                "sub": "0 = equal · 1 = monopoly",
            },
            {
                "label": "Tank cycles / season",
                "value": f"{m.tank_cycles:.1f}",
                "cls": card_class(m.tank_cycles, good_below=3.0, bad_above=7.0),
                "sub": "avg teams tanking late",
            },
            {
                "label": "Competitive balance",
                "value": f"{m.competitive_balance:.1f}",
                "cls": card_class(m.competitive_balance, good_below=12.0, bad_above=16.0),
                "sub": "σ of wins per season",
            },
            {
                "label": "Avg wins — top-3 picks",
                "value": f"{m.avg_wins_top3_recipients:.1f}",
                "cls": card_class(m.avg_wins_top3_recipients, good_below=28.0, bad_above=35.0),
                "sub": "lower = bad teams get picks",
            },
        ]

    # Inline bar chart data for pick distribution charts (SVG)
    pick_chart_svg: list[dict] = []
    for idx, rows in enumerate(bar_rows_list):
        color = CHART_COLORS[idx]
        max_pct = rows[0]["pct"] if rows else 1.0
        bar_area = 320
        label_w = 100
        val_w = 50
        bar_h = 16
        gap = 4
        total_w = label_w + bar_area + val_w + 10
        chart_svg_h = (bar_h + gap) * len(rows) + 4
        bars = []
        for row in rows:
            bw = int((row["pct"] / max(max_pct, 0.01)) * bar_area)
            bars.append({"name": row["name"][:12], "pct": row["pct"], "bw": bw})
        pick_chart_svg.append({
            "total_w": total_w,
            "chart_svg_h": chart_svg_h,
            "label_w": label_w,
            "bar_h": bar_h,
            "gap": gap,
            "color": color,
            "bars": bars,
        })

    return templates.TemplateResponse(
        request,
        "results.html",
        {
            "results": results,
            "is_comparison": is_comparison,
            "comparison_rows": comparison_rows,
            "metric_cards": metric_cards,
            "pick_tables": pick_tables,
            "pick_chart_svg": pick_chart_svg,
            "effort_bars": effort_bars,
            "effort_meta": effort_meta,
            "win_dist_bars": win_dist_bars,
            "win_dist_meta": win_dist_meta,
            "standings_tables": standings_tables,
            "result_explainers": result_explainers,
            "elapsed": elapsed,
            "runs": runs,
            "seasons": seasons,
            "selected_systems": [s.name for s in selected],
            "colors": CHART_COLORS,
            "systems": [s.name for s in ALL_SYSTEMS],
        },
    )


# ── Historical helpers ──────────────────────────────────────────────────────

def _make_historical_season_result(season_data: dict) -> tuple[SeasonResult, dict[int, str], dict[str, int]]:
    """
    Build a 30-team SeasonResult from historical season data.
    Returns (season_result, id_to_name, name_to_id).
    Lottery teams get IDs 0-13 (sorted worst-to-best by wins).
    Fake playoff teams get IDs 14-29.
    """
    lottery_teams = season_data["lottery_teams"]  # already sorted worst-to-best
    n_lottery = len(lottery_teams)

    name_to_id: dict[str, int] = {}
    id_to_name: dict[int, str] = {}
    standings: list[tuple[int, int, int]] = []

    for i, (name, wins, losses) in enumerate(lottery_teams):
        name_to_id[name] = i
        id_to_name[i] = name
        standings.append((i, wins, losses))

    # Add 16 fake playoff teams with win totals safely above any real lottery team.
    # We use 60-75 range to ensure even a ~50W borderline lottery team stays in the lottery.
    # (Historical max for a lottery team is ~48W; using 60 as minimum guarantees separation.)
    fake_wins = [75, 73, 71, 70, 69, 68, 67, 66, 65, 64, 63, 62, 61, 60, 60, 60]
    for j in range(16):
        tid = n_lottery + j
        w = fake_wins[j] if j < len(fake_wins) else 60
        actual_losses = season_data["games"] - w
        # Clamp so losses are non-negative (for shortened seasons)
        actual_losses = max(0, actual_losses)
        standings.append((tid, w, actual_losses))
        id_to_name[tid] = f"Playoff Team {j + 1}"

    # Fill to exactly 30 teams if fewer than 14 lottery teams
    while len(standings) < 30:
        tid = len(standings)
        standings.append((tid, 30, 52))
        id_to_name[tid] = f"Team {tid}"

    season_result = SeasonResult(
        standings=standings,
        head_to_head={},
        eliminated_week={},
    )
    return season_result, id_to_name, name_to_id


def _compute_actual_order(season_data: dict) -> list[str]:
    """
    Actual draft order as a 14-element list.

    Builds order from lottery_top4 (the real drawing results, picks 1-4) plus
    the remaining lottery_teams in ascending-wins order (approximate for picks 5-14).
    Any lottery_top4 entry not present in lottery_teams is silently skipped
    (handles expansion/traded picks from outside the lottery pool).
    """
    lottery_teams = season_data["lottery_teams"]
    valid_names = {t[0] for t in lottery_teams}

    top4_raw = season_data.get("lottery_top4", [])
    if not top4_raw and season_data.get("lottery_pick1"):
        top4_raw = [season_data["lottery_pick1"]]

    # Deduplicate while preserving order; only keep teams actually in lottery_teams
    seen: set[str] = set()
    top4_valid: list[str] = []
    for name in top4_raw:
        if name in valid_names and name not in seen:
            top4_valid.append(name)
            seen.add(name)

    # Remaining lottery_teams in record order (worst first = ascending wins)
    remaining = [name for name, _w, _l in lottery_teams if name not in seen]
    return top4_valid + remaining


def _run_historical_lottery(season_data: dict, system, n_runs: int = 500) -> dict[str, list[float]]:
    """
    Run a lottery system against historical standings n_runs times.
    Returns {team_name: [pick1_pct, pick2_pct, ..., pick14_pct]}.
    """
    season_result, id_to_name, name_to_id = _make_historical_season_result(season_data)
    n_lottery = len(season_data["lottery_teams"])

    pick_counts: dict[str, list[int]] = {
        name: [0] * n_lottery
        for name, _, _ in season_data["lottery_teams"]
    }

    rng = random.Random(42)
    for _ in range(n_runs):
        constraints = DraftConstraints()
        order = system.draft_order([season_result], constraints, rng)
        for slot_idx, team_id in enumerate(order[:n_lottery]):
            if team_id in id_to_name and id_to_name[team_id] in pick_counts:
                team_name = id_to_name[team_id]
                pick_counts[team_name][slot_idx] += 1

    result: dict[str, list[float]] = {}
    for name, counts in pick_counts.items():
        result[name] = [round(c / n_runs * 100, 1) for c in counts]
    return result


def _most_likely_pick(dist: list[float]) -> int:
    """Return the 1-indexed pick slot with the highest probability."""
    return dist.index(max(dist)) + 1


# ── Historical routes ───────────────────────────────────────────────────────

@router.get("/historical", response_class=HTMLResponse)
async def historical_form(request: Request):
    system_names = [s.name for s in ALL_SYSTEMS]
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "systems": system_names,
            "explainers": {name: SYSTEM_EXPLAINERS.get(name, {}) for name in system_names},
            "show_historical": True,
            "season_keys": SEASON_KEYS,
        },
    )


@router.post("/historical", response_class=HTMLResponse)
async def historical_run(
    request: Request,
    season_key: str = Form(...),
    systems: list[str] = Form(default=[]),
    n_runs: int = Form(default=500),
):
    n_runs = max(100, min(2000, n_runs))
    season_data = HISTORICAL_SEASONS.get(season_key)
    if not season_data:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "systems": [s.name for s in ALL_SYSTEMS],
                "explainers": {s.name: SYSTEM_EXPLAINERS.get(s.name, {}) for s in ALL_SYSTEMS},
                "show_historical": True,
                "season_keys": SEASON_KEYS,
                "error": f"Unknown season: {season_key}",
            },
        )

    selected = [SYSTEM_MAP[s] for s in systems if s in SYSTEM_MAP][:2]
    if not selected:
        selected = [ALL_SYSTEMS[0]]

    # Ensure lottery teams are sorted worst-to-best for consistent display
    season_data = dict(season_data)
    season_data["lottery_teams"] = sorted(season_data["lottery_teams"], key=lambda t: t[1])

    is_pending = season_data.get("season_pending", False)
    actual_order = _compute_actual_order(season_data) if not is_pending else []

    t0 = time.perf_counter()
    sim_results = []
    for system in selected:
        dist = _run_historical_lottery(season_data, system, n_runs=n_runs)

        rows = []
        lottery_teams = season_data["lottery_teams"]
        for rank_idx, (name, wins, losses) in enumerate(lottery_teams):
            d = dist.get(name, [0.0] * len(lottery_teams))
            ml_pick = _most_likely_pick(d)
            actual_pick = (actual_order.index(name) + 1) if (not is_pending and name in actual_order) else None
            delta = (actual_pick - ml_pick) if (actual_pick is not None) else None

            if delta is None:
                delta_cls = ""
                delta_str = "—"
            elif abs(delta) <= 1:
                delta_cls = "diff-same"
                delta_str = "±0" if delta == 0 else f"{delta:+d}"
            elif delta > 0:
                delta_cls = "diff-worse"
                delta_str = f"{delta:+d}"
            else:
                delta_cls = "diff-better"
                delta_str = f"{delta:+d}"

            rows.append({
                "name": name,
                "wins": wins,
                "losses": losses,
                "lottery_seed": rank_idx + 1,
                "dist": d,
                "ml_pick": ml_pick,
                "actual_pick": actual_pick,
                "delta": delta,
                "delta_cls": delta_cls,
                "delta_str": delta_str,
                "pick1_pct": d[0] if d else 0.0,
                "top4_pct": sum(d[:4]) if len(d) >= 4 else sum(d),
            })

        rows_sorted = sorted(rows, key=lambda r: r["dist"].index(max(r["dist"])))

        sim_results.append({
            "system_name": system.name,
            "rows": rows_sorted,
            "explainer": SYSTEM_EXPLAINERS.get(system.name, {}),
            "color": CHART_COLORS[len(sim_results)] if len(sim_results) < len(CHART_COLORS) else "#ff8c00",
        })

    # Chip Window leaderboard — only computed when Chip Window is selected
    chip_lb = None
    if any(s.name == "Chip Window" for s in selected):
        cw = SYSTEM_MAP["Chip Window"]
        lb_rng = random.Random(42)
        chip_lb = cw.chip_leaderboard(
            season_data["lottery_teams"],
            n_scenarios=600,
            rng=lb_rng,
        )

    elapsed = round(time.perf_counter() - t0, 2)

    return templates.TemplateResponse(
        request,
        "historical_results.html",
        {
            "season_key": season_key,
            "season_data": season_data,
            "sim_results": sim_results,
            "actual_order": actual_order,
            "is_pending": is_pending,
            "elapsed": elapsed,
            "n_runs": n_runs,
            "selected_systems": [s.name for s in selected],
            "colors": CHART_COLORS,
            "season_keys": SEASON_KEYS,
            "systems": [s.name for s in ALL_SYSTEMS],
            "chip_lb": chip_lb,
        },
    )


# ── Chip Window Simulator routes ─────────────────────────────────────────────

@router.get("/chip-window", response_class=HTMLResponse)
async def chip_window_page(request: Request):
    return templates.TemplateResponse(
        request,
        "chip_window.html",
        {"default_seasons": 10, "default_seed": ""},
    )


@router.post("/chip-window/run", response_class=JSONResponse)
async def chip_window_run(
    request: Request,
    seasons: int = Form(default=10),
    seed: Optional[str] = Form(default=None),
):
    seasons = max(5, min(15, seasons))
    seed_val: Optional[int] = None
    if seed and seed.strip().isdigit():
        seed_val = int(seed.strip())

    result = simulate_chip_window_league(seasons=seasons, seed=seed_val)
    return result_to_json(result)
