"""Command line entry point for launching the monitoring dashboard server."""

from __future__ import annotations

import argparse
import logging

import uvicorn

from ..config import SystemConfig
from .app import create_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the monitoring dashboard for the multi-agent system")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind the server")
    parser.add_argument("--port", type=int, default=8000, help="Port to expose the dashboard")
    parser.add_argument("--refresh-interval", type=float, default=120.0, help="Refresh interval in seconds")
    parser.add_argument("--symbols", nargs="*", help="Optional override for tracked symbols")
    parser.add_argument("--log-level", default="INFO", help="Logging level for agents")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (development use only)")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = SystemConfig()
    if args.symbols:
        config.tracked_symbols = [symbol.upper() for symbol in args.symbols]

    log_level = getattr(logging, str(args.log_level).upper(), logging.INFO)
    app = create_app(config=config, refresh_interval=args.refresh_interval, log_level=log_level)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=str(args.log_level).lower(),
        reload=args.reload,
    )


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()
