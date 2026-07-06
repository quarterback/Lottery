import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from web.router import router

app = FastAPI(title="Lottery Lab", docs_url=None, redoc_url=None)
# Trust Replit's reverse proxy so request.base_url uses https://
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

_static_dir = Path(__file__).resolve().parent / "web" / "static"
# On Vercel the static assets are served from the build's `public/` dir, and the
# app tree is bundled via `includeFiles` — which may not place `web/static` where
# this resolves. StaticFiles() raises at construction if the dir is missing, which
# would crash the whole serverless function at cold start. Only mount when present
# (local/Replit runs have it; Vercel serves /static from the edge regardless).
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

app.include_router(router)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import FileResponse
    ico = _static_dir / "favicon.ico"
    if ico.exists():
        return FileResponse(str(ico), media_type="image/x-icon")
    return Response(status_code=204)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
