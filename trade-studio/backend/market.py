"""Public read-only market feed. Does not access any brokerage account."""

import json
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from threading import Lock
from urllib.error import URLError
from urllib.request import Request, urlopen


class QuoteUnavailable(Exception):
    pass


class CoinbaseTicker:
    url = "https://api.exchange.coinbase.com/products/BTC-USD/ticker"

    def __init__(self):
        self.lock = Lock()
        self.cached = None
        self.fresh_until = 0

    def __call__(self):
        with self.lock:
            if time.monotonic() < self.fresh_until:
                if self.cached is None:
                    raise QuoteUnavailable
                return self.cached

            try:
                request = Request(self.url, headers={"User-Agent": "TradeStudioMarket/1", "Accept": "application/json"})
                with urlopen(request, timeout=7) as response:
                    quote = json.loads(response.read(8193))
                price = Decimal(quote["price"])
                timestamp = datetime.fromisoformat(quote["time"].replace("Z", "+00:00"))
                if not price.is_finite() or not 0 < price < Decimal("1000000000") or not timestamp.tzinfo:
                    raise ValueError
            except (URLError, OSError, ValueError, KeyError, TypeError, AttributeError, InvalidOperation):
                self.cached = None
                self.fresh_until = time.monotonic() + 5
                raise QuoteUnavailable from None

            self.cached = {"symbol": "BTC-USD", "price": format(price, "f"),
                           "time": timestamp.isoformat(), "provider": "Coinbase Exchange"}
            self.fresh_until = time.monotonic() + 10
            return self.cached
