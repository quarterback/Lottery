import os
from fastapi import FastAPI
from fastapi.responses import Response
from web.router import router

app = FastAPI(title="Lottery Lab", docs_url=None, redoc_url=None)
app.include_router(router)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
