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
    parser.add_argument(
        "--llm-provider",
        choices=["rule-based", "openai"],
        default="rule-based",
        help="Sentiment analysis backend to use",
    )
    parser.add_argument(
        "--openai-model",
        default="gpt-5.0-mini",
        help="OpenAI GPT-5 model name (used when --llm-provider=openai)",
    )
    parser.add_argument(
        "--openai-temperature",
        type=float,
        default=0.2,
        help="Sampling temperature for GPT-5 sentiment analysis",
    )
    parser.add_argument(
        "--openai-api-key",
        help="Override OPENAI_API_KEY environment variable for GPT-5 integration",
    )
    return parser


async def async_main(args: argparse.Namespace) -> AgentState:
    config = SystemConfig()
    if args.symbols:
        config.tracked_symbols = [symbol.upper() for symbol in args.symbols]
    llm_client = None
    if getattr(args, "llm_provider", "rule-based") == "openai":
        from .llm import OpenAIGPT5LLM

        llm_client = OpenAIGPT5LLM(
            api_key=getattr(args, "openai_api_key", None),
            model=getattr(args, "openai_model", "gpt-5.0-mini"),
            temperature=getattr(args, "openai_temperature", 0.2),
        )
    agents = config.create_agents(llm_client=llm_client)
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
