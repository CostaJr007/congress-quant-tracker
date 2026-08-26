"""FastAPI server — CongressInvests Tracker API.

App factory + static mounts only; route modules live in server/routers/.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

_ROOT_DIR = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(_ROOT_DIR))
sys.path.insert(0, str(_ROOT_DIR / "src"))

import uvicorn  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from congress_quant_tracker.config import settings  # noqa: E402
from congress_quant_tracker.database.models import Trade, init_db  # noqa: E402
from server.deps import get_db  # noqa: E402
from server.routers import (  # noqa: E402
    analyze,
    core,
    pipeline,
    politicians,
    stocks,
    terminal,
    trades,
)


async def _run_startup_tasks():
    """Startup background tasks:
    1. Automatic data sync for new congressional disclosures (if AUTO_SYNC_ON_STARTUP is enabled).
    2. Market data cache warmup for active database tickers.
    """
    import concurrent.futures
    loop = asyncio.get_running_loop()

    # Step 1: Check and ingest new disclosure data in the background
    if getattr(settings, "AUTO_SYNC_ON_STARTUP", True):
        try:
            await asyncio.sleep(1.5)  # Wait for server to bind and be fully responsive
            logger.info("[Startup Sync] Checking for new congressional filings (House Official)...")
            from congress_quant_tracker.services.official_pipeline import OfficialHousePipeline

            max_filings = getattr(settings, "STARTUP_SYNC_MAX", 60)
            since_days = getattr(settings, "STARTUP_SYNC_DAYS", 90)

            def _run_house_sync():
                pipe = OfficialHousePipeline()
                return pipe.run(
                    max_filings=max_filings,
                    since_days=since_days,
                    use_tavily=bool(settings.TAVILY_API_KEY),
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                stats = await loop.run_in_executor(pool, _run_house_sync)
            logger.info(
                "[Startup Sync] Completed: added %s trades, %s politicians (indexed %s filings)",
                stats.get("trades_added", 0),
                stats.get("politicians_added", 0),
                stats.get("filings_indexed", 0),
            )
        except Exception as e:
            logger.warning("[Startup Sync] Notice/Warning during startup sync: %s", e)

        # Senate sync (eFD with CongressInvests fallback when blocked)
        try:
            logger.info("[Startup Sync] Checking for new Senate filings...")
            from congress_quant_tracker.services.senate_pipeline import SenatePipeline

            def _run_senate_sync():
                return SenatePipeline().run(strategy="auto", max_efd_reports=20)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                sstats = await loop.run_in_executor(pool, _run_senate_sync)
            logger.info(
                "[Startup Sync] Senate: added %s trades via %s",
                sstats.get("trades_added", 0),
                sstats.get("strategy_used", "?"),
            )
        except Exception as e:
            logger.warning("[Startup Sync] Senate sync skipped: %s", e)

    # Step 2: Pre-fetch and warm up market data cache
    try:
        session = get_db()
        try:
            tickers = [
                r[0]
                for r in session.query(Trade.ticker)
                .filter(Trade.ticker.isnot(None), Trade.ticker != "")
                .distinct()
                .all()
            ]
        finally:
            session.close()

        if tickers:
            logger.info("Pre-warming market data cache for %d tickers...", len(tickers))
            from congress_quant_tracker.enrichers.market_data import prefetch_tickers
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                await loop.run_in_executor(pool, prefetch_tickers, tickers)
            logger.info("Market data cache warmup complete.")
    except Exception as e:
        logger.warning("Cache warmup notice: %s", e)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db(settings.DATABASE_URL)
    settings.ensure_dirs()
    startup_task = asyncio.create_task(_run_startup_tasks())
    try:
        yield
    finally:
        if not startup_task.done():
            startup_task.cancel()
            try:
                await startup_task
            except asyncio.CancelledError:
                pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="CongressInvests Tracker",
        version="2.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(core.router)
    app.include_router(trades.router)
    app.include_router(politicians.router)
    app.include_router(stocks.router)
    app.include_router(analyze.router)
    app.include_router(pipeline.router)
    app.include_router(terminal.router)  # keep last: contains /api/terminal/{dataset} catch-all

    @app.get("/")
    def root_index():
        """Redirect root to CI://TERMINAL."""
        return RedirectResponse(url="/terminal/", status_code=302)

    # Politician headshots (bioguide jpgs) for CI://TERMINAL + API clients
    _pol_photo_dir = _ROOT_DIR / "data" / "politicians"
    _pol_photo_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/politicians",
        StaticFiles(directory=str(_pol_photo_dir)),
        name="politician_photos",
    )

    # Mount static assets for terminal (css, js, fonts) — after routes so /terminal hits HTML first
    _terminal_dir = _ROOT_DIR / "ci_terminal"
    @app.get("/terminal")
    @app.get("/terminal/")
    def terminal_index():
        """Serve Bloomberg × ASCII global market terminal."""
        index = _terminal_dir / "index.html"
        if not index.exists():
            raise HTTPException(
                status_code=404,
                detail="CI://TERMINAL not installed (ci_terminal/ missing)",
            )
        return FileResponse(index, media_type="text/html")

    # Mount static assets for terminal (css, js, fonts) — after routes so /terminal hits HTML first
    if _terminal_dir.is_dir():
        app.mount(
            "/terminal",
            StaticFiles(directory=str(_terminal_dir), html=True),
            name="gmt_terminal",
        )

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT, log_level="info")
