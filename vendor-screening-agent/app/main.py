"""
Application entry point.

Run from the project root:
    python3 -m uvicorn app.main:app --port 8000
then open http://127.0.0.1:8000
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api.routes import router

app = FastAPI(
    title="AI Vendor / Legal-Entity Screening Agent",
    version=__version__,
    description="Detects duplicate vendor records and validates vendor "
                "legitimacy against the open GLEIF LEI registry.",
)


@app.middleware("http")
async def no_cache(request: Request, call_next):
    """Tell the browser never to cache the page/assets, so changes always show
    up on a normal refresh (no hard-refresh needed)."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router)
