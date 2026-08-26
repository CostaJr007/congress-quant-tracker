"""API routers — one module per resource area."""

from server.routers import analyze, core, pipeline, politicians, stocks, terminal, trades

__all__ = ["analyze", "core", "pipeline", "politicians", "stocks", "trades", "terminal"]
