"""CLI entrypoint for running the multi-agent system."""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import List

from .config import SystemConfig
from .orchestrator import AgentOrchestrator
from .types import AgentState


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Multi-agent crypto management orchestrator")
    parser.add_argument("--cycles", type=int, default=1, help="Number of cycles to execute")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay between cycles in seconds")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    parser.add_argument(
        "--symbols",
        nargs="*",
        help="Override tracked symbols (space separated list, e.g. BTC ETH XRP)",
    )
    parser.add_argument("--initial-cash", type=float, help="Initial cash balance", default=None)
    parser.add_argument(
        "--trade-fraction",
        type=float,
        help="Fraction of available cash deployed per trade",
        default=None,
    )
    parser.add_argument(
        "--min-cash-reserve",
        type=float,
        help="Minimum fraction of cash to keep as reserve",
        default=None,
    )
    parser.add_argument(
        "--min-trade-value",
        type=float,
        help="Minimum KRW amount per trade",
        default=None,
    )
    parser.add_argument(
        "--stop-loss-pct",
        type=float,
        help="Percentage drop from average price to trigger stop loss",
        default=None,
    )
    parser.add_argument(
        "--take-profit-pct",
        type=float,
        help="Percentage gain from average price to trigger take profit",
        default=None,
    )
    parser.add_argument(
        "--max-position-allocation",
        type=float,
        help="Maximum fraction of portfolio value allocated to a single position",
        default=None,
    )
    parser.add_argument(
        "--rebalance-buffer",
        type=float,
        help="Tolerance above the allocation target before trimming positions",
        default=None,
    )
    return parser


async def async_main(args: argparse.Namespace) -> AgentState:
    config = SystemConfig()
    if args.symbols:
        config.tracked_symbols = [symbol.upper() for symbol in args.symbols]
    if args.initial_cash is not None:
        config.initial_cash = args.initial_cash
    if args.trade_fraction is not None:
        config.trade_fraction = args.trade_fraction
    if args.min_cash_reserve is not None:
        config.min_cash_reserve = args.min_cash_reserve
    if args.min_trade_value is not None:
        config.min_trade_value = args.min_trade_value
    if args.stop_loss_pct is not None:
        config.stop_loss_pct = args.stop_loss_pct
    if args.take_profit_pct is not None:
        config.take_profit_pct = args.take_profit_pct
    if args.max_position_allocation is not None:
        config.max_position_allocation = args.max_position_allocation
    if args.rebalance_buffer is not None:
        config.rebalance_buffer = args.rebalance_buffer
    agents = config.create_agents()
    log_level = getattr(logging, str(args.log_level).upper(), logging.INFO)
    for agent in agents:
        agent.configure_logger(level=log_level)
    orchestrator = AgentOrchestrator(agents)
    state = await orchestrator.run(cycles=args.cycles, delay=args.delay)
    await orchestrator.aclose()
    return state


def main(argv: List[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    state = asyncio.run(async_main(args))
    portfolio_value = state.portfolio.total_value(state.market_data)
    print("\n=== Portfolio Summary ===")
    print(f"Cash balance ({state.portfolio.base_currency}): {state.portfolio.balances.get(state.portfolio.base_currency, 0.0):,.2f}")
    for symbol, position in state.portfolio.positions.items():
        if position.quantity <= 0:
            continue
        ticker = state.market_data.get(symbol)
        price = ticker.price if ticker else 0.0
        value = position.quantity * price
        print(
            f"{symbol}: quantity={position.quantity:.6f} avg_price={position.average_price:,.2f} value={value:,.2f}"
        )
    print(f"Total portfolio value: {portfolio_value:,.2f} {state.portfolio.base_currency}")


if __name__ == "__main__":
    main()
