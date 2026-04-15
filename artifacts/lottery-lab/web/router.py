from __future__ import annotations

import time
from pathlib import Path
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from engine.lottery_sim import (
    ALL_SYSTEMS,
    SYSTEM_MAP,
    monte_carlo,
    MetricsBundle,
    NBA_TEAM_NAMES,
    NUM_TEAMS,
    WEEKS_PER_SEASON,
    GAMES_PER_SEASON,
    PLAYOFF_SPOTS,
)

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
        "odds": None,
        "odds_note": "Variable by 3-year history. Approximate range: 2%–18%.",
    },
    "RCL": {
        "desc": (
            "Multi-year coefficient (similar to UEFA) plus head-to-head record versus other lottery "
            "teams. Hard caps enforce fairness: no team can receive the #1 pick more than once in "
            "5 years, or a top-3 pick more than twice in 5 years."
        ),
        "odds": None,
        "odds_note": "Variable — capped by history. Teams hitting caps are excluded from those slots.",
    },
    "Lottery Tournament": {
        "desc": (
            "The 8 worst teams by record play a single-elimination tournament. "
            "The tournament winner earns pick #1. Teams 9–14 get picks 9–14 by record. "
            "You need to be in the bottom 8 AND win games to land the top pick."
        ),
        "odds": None,
        "odds_note": "Bottom 8 enter tournament. Better-record teams have a slight edge within each matchup.",
    },
    "Pure Inversion": {
        "desc": (
            "No lottery at all. The best non-playoff team picks #1; the worst non-playoff team picks "
            "last. This completely inverts the tanking incentive — losing hurts your draft position. "
            "Every team should try hard all season."
        ),
        "odds": None,
        "odds_note": "Deterministic. Best record among non-playoff teams = Pick #1.",
    },
    "Gold Plan (PWHL)": {
        "desc": (
            "Draft order is determined by wins accumulated after a team is mathematically eliminated "
            "from playoff contention. Teams that keep competing hard after elimination are rewarded. "
            "This system is used in real life by the PWHL."
        ),
        "odds": None,
        "odds_note": "Deterministic. Most post-elimination wins = Pick #1.",
    },
}


# ── Pre-computation helpers ────────────────────────────────────────────────

def make_bar_rows(metrics: MetricsBundle, top_n: int = 14) -> list[dict]:
    rows = []
    for team_id in range(NUM_TEAMS):
        pct = metrics.pick_distribution.get(team_id, [0.0])[0]
        rows.append({"name": NBA_TEAM_NAMES[team_id], "pct": round(pct, 3)})
    rows.sort(key=lambda r: r["pct"], reverse=True)
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


def build_standings_table(metrics: MetricsBundle, color: str) -> list[dict]:
    """Build standings table rows sorted by avg wins descending."""
    rows = []
    max_pick1 = max(metrics.pick1_by_team.values(), default=1.0) or 1.0
    max_top5 = max(
        (metrics.pick_distribution.get(tid, [0.0])[0] for tid in range(NUM_TEAMS)),
        default=1.0,
    ) or 1.0
    for tid in range(NUM_TEAMS):
        avg_w = metrics.avg_wins_by_team.get(tid, 0.0)
        avg_l = round(GAMES_PER_SEASON - avg_w, 1)
        pick1 = metrics.pick1_by_team.get(tid, 0.0)
        top5 = round(metrics.pick_distribution.get(tid, [0.0])[0], 2)
        is_lottery = avg_w < (GAMES_PER_SEASON * PLAYOFF_SPOTS / NUM_TEAMS * 1.1)
        rows.append({
            "name": NBA_TEAM_NAMES[tid],
            "avg_wins": avg_w,
            "avg_losses": avg_l,
            "pick1_pct": pick1,
            "top5_pct": top5,
            "is_lottery": is_lottery,
            "pick1_bar": make_pick_svg_bar(pick1, max_pick1, color, 50),
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

    # Enhanced pick tables with #1 pick column
    pick_tables: list[list[dict]] = []
    for idx, m in enumerate(results):
        color = CHART_COLORS[idx]
        rows_raw = bar_rows_list[idx]
        max_pct = rows_raw[0]["pct"] if rows_raw else 1.0
        max_pick1 = max(
            (m.pick1_by_team.get(tid, 0.0) for tid in range(NUM_TEAMS)),
            default=1.0,
        ) or 1.0
        table_rows = []
        for row in rows_raw:
            tid = NBA_TEAM_NAMES.index(row["name"])
            pick1_pct = m.pick1_by_team.get(tid, 0.0)
            table_rows.append({
                **row,
                "pick1_pct": pick1_pct,
                "bar_svg": make_pick_svg_bar(row["pct"], max_pct, color),
                "pick1_bar": make_pick_svg_bar(pick1_pct, max_pick1, color, 50),
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
        build_standings_table(m, CHART_COLORS[i])
        for i, m in enumerate(results)
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
