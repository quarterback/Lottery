"""Vercel serverless entrypoint for Lottery Lab.

The FastAPI app lives in ``artifacts/lottery-lab/``. Vercel's Python runtime
imports this file and looks for an ASGI/WSGI ``app`` object. We put the
lottery-lab directory on ``sys.path`` so its ``main``, ``engine``, and ``web``
packages import cleanly, then re-export the FastAPI ``app``.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_APP_DIR = _REPO_ROOT / "artifacts" / "lottery-lab"

if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from main import app  # noqa: E402  (import after sys.path mutation)

__all__ = ["app"]
