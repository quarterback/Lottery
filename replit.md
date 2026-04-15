# Workspace

## Overview

pnpm workspace monorepo using TypeScript. Each package manages its own dependencies.

## Artifacts

### Lottery Lab (`artifacts/lottery-lab/`)
- **Kind**: Python/FastAPI web app (not a React artifact)
- **Preview path**: `/` (port 21381)
- **Workflow**: "Lottery Lab" — runs `cd artifacts/lottery-lab && uvicorn main:app --host 0.0.0.0 --port 21381 --reload`
- **Purpose**: NBA draft lottery scenario simulator comparing 8 systems via Monte Carlo simulations
- **Features**: System comparison, per-slot pick distributions, sortable tables, historical NBA seasons mode (2000-01 through 2025-26)
- **Stack**: Python 3.11, FastAPI, Jinja2 templates, inline SVG charts, Bloomberg terminal dark theme CSS
- **Key files**: `engine/lottery_sim.py` (sim engine), `web/router.py` (FastAPI routes), `web/templates/` (Jinja2), `data/historical_seasons.py` (26 seasons of data)
- **Tests**: 21 tests in `tests/test_lottery_sim.py`, all passing
- **Note**: The `artifacts/lottery-lab: web` workflow (auto-created by the artifact system for Vite) should remain NOT STARTED — uvicorn handles the server via the "Lottery Lab" workflow

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)

## Key Commands

- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `pnpm --filter @workspace/api-server run dev` — run API server locally

See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details.
