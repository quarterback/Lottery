# Lottery Lab

NBA draft lottery scenario simulator. Compare 8 different draft lottery systems across Monte Carlo simulations to understand their impact on tanking behavior, competitive balance, and draft equity.

> **The question this answers:** Are you punishing failure, or rewarding competitive failure?

## Systems modeled

| # | System | Mechanic |
|---|--------|----------|
| 1 | Current NBA | Bottom-3 get 14% odds for #1. Status quo. |
| 2 | Flat Bottom | All lottery teams get equal odds. No bottom-out incentive. |
| 3 | Play-In Boost | Play-in teams get equal-or-better odds than worse teams. |
| 4 | UEFA Coefficient | Rolling 3-year weighted performance score sets odds. |
| 5 | RCL | Multi-year coefficient + H2H bonus + hard caps (no #1 more than once in 5 years). |
| 6 | Lottery Tournament | Bottom-8 play single-elim; winner gets #1 pick. |
| 7 | Pure Inversion | Best non-playoff team picks first. Rewards competitive failure. |
| 8 | Gold Plan (PWHL) | Post-elimination wins determine draft order. Already live in the PWHL. |

## Metrics reported

- **Late-season effort** — Win rate of bottom teams in final 20 games vs first 62. < 1.0 = tanking.
- **Repeat #1 pick frequency** — How often does the same team get #1 within a 5-year window?
- **Gini coefficient (top-5 picks)** — Pick equity. 0 = perfectly equal, 1 = one team gets everything.
- **Tank cycles** — Avg number of teams intentionally tanking per season in late weeks.
- **Competitive balance** — Stddev of wins per season. Lower = more parity.
- **Avg wins of top-3 recipients** — Lower means truly bad teams are getting the picks.

## Stack

- Python 3.11
- FastAPI + Uvicorn
- Jinja2 templates
- Inline SVG charts (no JS framework)

## Local development

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open http://localhost:8000

## Running tests

```bash
python tests/test_lottery_sim.py
```

Or with pytest:

```bash
pip install pytest
pytest tests/
```

## Docker

```bash
docker build -t lottery-lab .
docker run -p 8000:8000 lottery-lab
```

## Deploy to Fly.io

```bash
fly launch --name lottery-lab
fly deploy
```

## Deploy to Railway

```bash
railway up
```

## Deploy to Render

Set start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
