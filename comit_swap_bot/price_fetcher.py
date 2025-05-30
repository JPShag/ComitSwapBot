"""Price fetching utilities for BTC/XMR conversion."""

from datetime import datetime
from decimal import Decimal

import httpx
import structlog
from cachetools import TTLCache

from .config import config

logger = structlog.get_logger()


class PriceFetcher:
    """
    Fetches cryptocurrency prices from CoinGecko API.

    Price data provided by CoinGecko (https://www.coingecko.com)
    Attribution required per CoinGecko API terms of service.
    """

    def __init__(self):
        """Initialize the price fetcher with CoinGecko API client."""
        self.client = httpx.AsyncClient(
            timeout=10.0,
            headers={
                "Accept": "application/json",
                "User-Agent": "COMIT-Swap-Bot/1.0 (Price attribution: CoinGecko)",
            },
        )
        if config.coingecko_api_key:
            self.client.headers["x-cg-pro-api-key"] = config.coingecko_api_key

        # Cache prices for 60 seconds to respect rate limits
        self._price_cache: TTLCache = TTLCache(maxsize=10, ttl=60)

    async def get_btc_to_xmr_rate(self) -> Decimal | None:
        """Get the current BTC to XMR exchange rate."""
        cache_key = "btc_xmr_rate"

        # Check cache
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]

        try:
            # Fetch both BTC and XMR prices in USD
            url = f"{config.coingecko_api_url}/simple/price"
            params = {"ids": "bitcoin,monero", "vs_currencies": "usd", "precision": 18}

            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            btc_usd = Decimal(str(data["bitcoin"]["usd"]))
            xmr_usd = Decimal(str(data["monero"]["usd"]))

            # Calculate BTC to XMR rate
            rate = btc_usd / xmr_usd

            # Cache the result
            self._price_cache[cache_key] = rate

            logger.info(
                "📊 Fetched exchange rate from CoinGecko",
                btc_usd=btc_usd,
                xmr_usd=xmr_usd,
                btc_to_xmr=rate,
                attribution="Price data by CoinGecko",
            )

            return rate

        except Exception as e:
            logger.error("Failed to fetch price", error=str(e))
            return None

    async def convert_btc_to_xmr(self, btc_amount: Decimal) -> Decimal | None:
        """Convert BTC amount to XMR using current market rate."""
        rate = await self.get_btc_to_xmr_rate()
        if rate:
            return btc_amount * rate
        return None

    async def get_historical_rate(self, timestamp: datetime) -> Decimal | None:
        """Get historical BTC to XMR rate for a specific timestamp."""
        try:
            # CoinGecko requires date in dd-mm-yyyy format
            date_str = timestamp.strftime("%d-%m-%Y")

            url = f"{config.coingecko_api_url}/coins/bitcoin/history"
            params = {"date": date_str}

            btc_response = await self.client.get(url, params=params)
            btc_data = btc_response.json()

            url = f"{config.coingecko_api_url}/coins/monero/history"
            xmr_response = await self.client.get(url, params=params)
            xmr_data = xmr_response.json()

            btc_usd = Decimal(str(btc_data["market_data"]["current_price"]["usd"]))
            xmr_usd = Decimal(str(xmr_data["market_data"]["current_price"]["usd"]))

            return btc_usd / xmr_usd

        except Exception as e:
            logger.error(
                "Failed to fetch historical price", timestamp=timestamp, error=str(e)
            )
            return None

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
