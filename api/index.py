"""Vercel serverless entrypoint for Lottery Lab.

The FastAPI app lives in ``artifacts/lottery-lab/``. Vercel's Python runtime
imports this file and looks for an ASGI/WSGI ``app`` object. We put the
lottery-lab directory on ``sys.path`` so its ``main``, ``engine``, and ``web``
packages import cleanly, then re-export the FastAPI ``app``.

If that import fails at cold start (e.g. ``includeFiles`` didn't bundle the app
tree, or a module raises on import) Vercel would otherwise show an opaque
``FUNCTION_INVOCATION_FAILED`` page. To stay debuggable we fall back to a tiny
app that reports the real traceback and what actually landed in the bundle.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_APP_DIR = _REPO_ROOT / "artifacts" / "lottery-lab"

if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

try:
    from main import app  # noqa: E402  (import after sys.path mutation)
except Exception:  # pragma: no cover - diagnostic path for serverless cold start
    import traceback

    _tb = traceback.format_exc()

    def _listing() -> str:
        lines = []
        for base in (_REPO_ROOT, _APP_DIR, _APP_DIR / "web"):
            try:
                entries = sorted(p.name + ("/" if p.is_dir() else "") for p in base.iterdir())
            except Exception as exc:  # directory missing entirely
                entries = [f"<unreadable: {exc}>"]
            lines.append(f"{base}:\n  " + "  ".join(entries))
        return "\n\n".join(lines)

    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse

    app = FastAPI()

    @app.get("/{_path:path}")
    async def _diagnostic(_path: str):
        return PlainTextResponse(
            "Lottery Lab failed to import at cold start.\n\n"
            f"sys.path[0] = {sys.path[0]}\n\n"
            f"--- traceback ---\n{_tb}\n"
            f"--- bundle contents ---\n{_listing()}\n",
            status_code=500,
        )

__all__ = ["app"]
