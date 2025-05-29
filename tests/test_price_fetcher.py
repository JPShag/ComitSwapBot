"""Tests for price fetcher."""

import pytest
import pytest_asyncio
from decimal import Decimal
from unittest.mock import Mock, patch

from comit_swap_bot.price_fetcher import PriceFetcher


@pytest_asyncio.fixture
async def price_fetcher():
    """Create price fetcher instance."""
    fetcher = PriceFetcher()
    yield fetcher
    await fetcher.close()


class TestPriceFetcher:
    """Test price fetching functionality."""
    
    @pytest.mark.asyncio
    async def test_get_btc_to_xmr_rate(self, price_fetcher):
        """Test fetching BTC to XMR exchange rate."""
        # Mock API response
        mock_response = {
            "bitcoin": {"usd": 50000},
            "monero": {"usd": 200}
        }
        
        with patch.object(price_fetcher.client, 'get') as mock_get:
            # Create a proper mock response
            mock_resp = Mock()
            mock_resp.json.return_value = mock_response  # Synchronous json() method
            mock_resp.raise_for_status.return_value = None  # Synchronous raise_for_status()
            mock_get.return_value = mock_resp
            
            rate = await price_fetcher.get_btc_to_xmr_rate()
            
            assert rate == Decimal("250")  # 50000 / 200
            
    @pytest.mark.asyncio
    async def test_convert_btc_to_xmr(self, price_fetcher):
        """Test BTC to XMR conversion."""
        # Mock the rate
        with patch.object(price_fetcher, 'get_btc_to_xmr_rate') as mock_rate:
            mock_rate.return_value = Decimal("38.5")
            
            xmr_amount = await price_fetcher.convert_btc_to_xmr(Decimal("0.1"))
            
            assert xmr_amount == Decimal("3.85")  # 0.1 * 38.5
            
    @pytest.mark.asyncio
    async def test_caching(self, price_fetcher):
        """Test that prices are cached."""
        mock_response = {
            "bitcoin": {"usd": 50000},
            "monero": {"usd": 200}
        }
        
        with patch.object(price_fetcher.client, 'get') as mock_get:
            # Create a proper mock response
            mock_resp = Mock()
            mock_resp.json.return_value = mock_response  # Synchronous json() method
            mock_resp.raise_for_status.return_value = None  # Synchronous raise_for_status()
            mock_get.return_value = mock_resp
            
            # First call
            rate1 = await price_fetcher.get_btc_to_xmr_rate()
            # Second call (should use cache)
            rate2 = await price_fetcher.get_btc_to_xmr_rate()
            
            assert rate1 == rate2
            # Should only call API once due to caching
            assert mock_get.call_count == 1