"""CLI entrypoint: `python -m kalshi_bot [scan|run]`."""

from __future__ import annotations

import argparse
import logging
import sys

from .config import BotConfig
from .engine import TradingEngine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kalshi_bot", description="Kalshi trading bot")
    parser.add_argument(
        "command",
        choices=["scan", "run", "once", "dashboard"],
        help="scan: list current signals; once: single trade cycle; run: continuous loop; "
        "dashboard: web UI",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = BotConfig()

    if not config.paper_trading and not config.live_enabled:
        print(
            "PAPER_TRADING=false requires KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH",
            file=sys.stderr,
        )
        return 2

    if args.command == "dashboard":
        from .dashboard import serve

        serve(host=args.host, port=args.port)
        return 0

    engine = TradingEngine(config)
    if args.command == "scan":
        for signal in engine.scan():
            print(
                f"[{signal.strategy}] {signal.ticker} BUY {signal.side.upper()} "
                f"@ {signal.price_cents}c edge={signal.edge:.3f} — {signal.reason}"
            )
    elif args.command == "once":
        executed = engine.run_once()
        print(f"executed {executed} trades ({'paper' if config.paper_trading else 'LIVE'})")
    else:
        engine.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
