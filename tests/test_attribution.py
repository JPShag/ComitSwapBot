"""Test attribution functionality."""

from datetime import datetime
from decimal import Decimal

import pytest

from comit_swap_bot.attribution import attribution
from comit_swap_bot.models import AtomicSwap, HTLCTransaction, HTLCType, SwapState
from comit_swap_bot.notifiers import TwitterNotifier


def test_coingecko_attribution_config():
    """Test that CoinGecko attribution is properly configured."""
    attr_info = attribution.get_coingecko_attribution()

    assert attr_info["text"] == "Price data by CoinGecko"
    assert "coingecko.com" in attr_info["url"]
    assert "utm_source=comit-swap-bot" in attr_info["url"]
    assert attr_info["logo_required"] is True


def test_twitter_attribution_format():
    """Test Twitter attribution formatting."""
    twitter_attr = attribution.format_attribution_for_twitter()

    assert "💱" in twitter_attr
    assert "CoinGecko" in twitter_attr


def test_discord_attribution_format():
    """Test Discord attribution formatting with markdown link."""
    discord_attr = attribution.format_attribution_for_discord()

    assert "[" in discord_attr and "](" in discord_attr
    assert "coingecko.com" in discord_attr


def test_swap_message_includes_attribution():
    """Test that swap notification messages include CoinGecko attribution."""
    # Create a mock swap with price data
    lock_tx = HTLCTransaction(
        txid="abc123def456",
        version=2,
        locktime=0,
        byte_size=250,
        weight_units=1000,
        htlc_classification=HTLCType.LOCK,
        value_sats=50000000,  # 0.5 BTC
        output_index=0,
    )

    swap = AtomicSwap(
        swap_id="test-swap-123",
        lock_transaction=lock_tx,
        current_state=SwapState.LOCKED,
        btc_amount=Decimal("0.5"),
        xmr_amount=Decimal("7.5"),  # Simulated XMR amount
        btc_xmr_rate=Decimal("15.0"),  # Simulated rate
        detected_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )

    # Test message formatting
    notifier = TwitterNotifier()
    message = notifier.format_swap_message(swap)

    # Should include attribution when price data is present
    assert "Price data by CoinGecko" in message
    assert "💱" in message
    assert "0.5" in message  # BTC amount
    assert "7.5" in message  # XMR amount


def test_swap_message_without_price_data():
    """Test that swaps without price data don't include attribution."""
    # Create a swap without price data
    lock_tx = HTLCTransaction(
        txid="abc123def456",
        version=2,
        locktime=0,
        byte_size=250,
        weight_units=1000,
        htlc_classification=HTLCType.LOCK,
        value_sats=50000000,
        output_index=0,
    )

    swap = AtomicSwap(
        swap_id="test-swap-456",
        lock_transaction=lock_tx,
        current_state=SwapState.LOCKED,
        btc_amount=Decimal("0.5"),
        # No xmr_amount or btc_xmr_rate
        detected_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )

    notifier = TwitterNotifier()
    message = notifier.format_swap_message(swap)

    # Should NOT include attribution when no price data
    assert "CoinGecko" not in message
    assert "💱" not in message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
