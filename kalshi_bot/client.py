"""Minimal Kalshi Trade API v2 client with RSA-PSS request signing."""

from __future__ import annotations

import base64
import time
from typing import Any

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from .config import BotConfig


class KalshiClient:
    def __init__(self, config: BotConfig):
        self.config = config
        self.session = requests.Session()
        self._private_key: rsa.RSAPrivateKey | None = None
        if config.private_key_path:
            with open(config.private_key_path, "rb") as f:
                key = serialization.load_pem_private_key(f.read(), password=None)
            assert isinstance(key, rsa.RSAPrivateKey)
            self._private_key = key

    def _sign(self, timestamp_ms: str, method: str, path: str) -> str:
        assert self._private_key is not None
        message = f"{timestamp_ms}{method}{path}".encode()
        signature = self._private_key.sign(
            message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode()

    def _headers(self, method: str, path: str) -> dict[str, str]:
        if self._private_key is None:
            return {}
        timestamp_ms = str(int(time.time() * 1000))
        base_path = "/trade-api/v2" + path
        return {
            "KALSHI-ACCESS-KEY": self.config.api_key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
            "KALSHI-ACCESS-SIGNATURE": self._sign(timestamp_ms, method, base_path),
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = self.config.api_base + path
        resp = self.session.request(
            method, url, headers=self._headers(method, path), timeout=15, **kwargs
        )
        resp.raise_for_status()
        return resp.json()

    # ---- public market data (no auth required) ----

    def get_markets(self, status: str = "open", limit: int = 200, **params: Any) -> list[dict]:
        params.update({"status": status, "limit": limit})
        return self._request("GET", "/markets", params=params).get("markets", [])

    def get_market(self, ticker: str) -> dict:
        return self._request("GET", f"/markets/{ticker}").get("market", {})

    def get_orderbook(self, ticker: str, depth: int = 10) -> dict:
        return self._request("GET", f"/markets/{ticker}/orderbook", params={"depth": depth}).get(
            "orderbook", {}
        )

    # ---- authenticated trading ----

    def get_balance(self) -> int:
        return int(self._request("GET", "/portfolio/balance").get("balance", 0))

    def get_positions(self) -> list[dict]:
        return self._request("GET", "/portfolio/positions").get("market_positions", [])

    def create_order(
        self,
        ticker: str,
        side: str,
        action: str,
        count: int,
        price_cents: int,
        order_type: str = "limit",
    ) -> dict:
        body = {
            "ticker": ticker,
            "side": side,
            "action": action,
            "count": count,
            "type": order_type,
            ("yes_price" if side == "yes" else "no_price"): price_cents,
        }
        return self._request("POST", "/portfolio/orders", json=body)
