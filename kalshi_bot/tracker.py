"""Trade performance tracker: persists trade history and computes stats."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

def _default_path() -> str:
    return os.environ.get("TRADE_HISTORY_PATH", "trade_history.json")


@dataclass
class PerformanceTracker:
    path: str = field(default_factory=_default_path)
    records: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        p = Path(self.path)
        if p.exists():
            try:
                self.records = json.loads(p.read_text())
            except (json.JSONDecodeError, OSError):
                self.records = []

    def _save(self) -> None:
        Path(self.path).write_text(json.dumps(self.records, indent=1))

    def record_trade(self, trade: dict) -> None:
        self.records.append({**trade, "status": "open", "pnl_cents": None})
        self._save()

    def record_settlement(self, ticker: str, won: bool) -> None:
        payout_per_contract = 100 if won else 0
        for r in self.records:
            if r["ticker"] == ticker and r["status"] == "open":
                r["status"] = "won" if won else "lost"
                r["pnl_cents"] = r["contracts"] * (payout_per_contract - r["price_cents"])
                r["settled_ts"] = time.time()
        self._save()

    def stats(self) -> dict:
        settled = [r for r in self.records if r["status"] in ("won", "lost")]
        wins = [r for r in settled if r["status"] == "won"]
        total_pnl = sum(r["pnl_cents"] or 0 for r in settled)
        best = max(settled, key=lambda r: r["pnl_cents"] or 0, default=None)
        return {
            "total_trades": len(self.records),
            "open_trades": len([r for r in self.records if r["status"] == "open"]),
            "settled_trades": len(settled),
            "wins": len(wins),
            "losses": len(settled) - len(wins),
            "win_rate": round(len(wins) / len(settled), 3) if settled else None,
            "total_pnl_cents": total_pnl,
            "best_trade": {
                "ticker": best["ticker"],
                "pnl_cents": best["pnl_cents"],
            }
            if best
            else None,
        }
