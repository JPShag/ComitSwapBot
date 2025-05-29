"""Tests for notification system."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from comit_swap_bot.models import AtomicSwap, HTLCTransaction, HTLCType, SwapState
from comit_swap_bot.notifiers import ConsoleNotifier, SwapNotification, TwitterNotifier


@pytest.fixture
def sample_swap():
    """Create a sample swap for testing."""
    return AtomicSwap(
        swap_id="test_swap_123",
        lock_transaction=HTLCTransaction(
            txid="abc123def456789",
            version=2,
            locktime=0,
            byte_size=250,
            weight_units=1000,
            htlc_classification=HTLCType.LOCK,
            value_sats=10000000,  # 0.1 BTC
            output_index=0,
        ),
        current_state=SwapState.LOCKED,
        btc_amount=Decimal("0.1"),
        xmr_amount=Decimal("3.85"),
        btc_xmr_rate=Decimal("38.5"),
        detected_at=datetime(2025, 5, 29, 12, 0, 0, tzinfo=timezone.utc),
        last_updated=datetime(2025, 5, 29, 12, 0, 0, tzinfo=timezone.utc),
    )


class TestTwitterNotifier:
    """Test Twitter notification functionality."""

    @pytest.mark.asyncio
    async def test_tweet_formatting(self, sample_swap):
        """Test tweet message formatting."""
        with patch("comit_swap_bot.notifiers.config") as mock_config:
            mock_config.twitter_api_key = "test_key"
            mock_config.twitter_api_secret = "test_secret"
            mock_config.twitter_access_token = "test_token"
            mock_config.twitter_access_token_secret = "test_token_secret"

            notifier = TwitterNotifier()
            message = notifier.format_swap_message(sample_swap)

            assert "🔄 New BTC⇆XMR Atomic Swap!" in message
            assert "abc123def456789" in message
            assert "0.10000000 BTC" in message
            assert "3.8500 XMR" in message
            assert "1 BTC = 38.5000 XMR" in message
            assert "#AtomicSwap" in message
            assert len(message) <= 280  # Twitter character limit

    @pytest.mark.asyncio
    async def test_tweet_success(self, sample_swap):
        """Test successful tweet posting."""
        with patch("comit_swap_bot.notifiers.config") as mock_config:
            mock_config.twitter_api_key = "test_key"
            mock_config.twitter_api_secret = "test_secret"
            mock_config.twitter_access_token = "test_token"
            mock_config.twitter_access_token_secret = "test_token_secret"

            with patch("comit_swap_bot.notifiers.tweepy.Client") as mock_client:
                mock_instance = Mock()
                mock_instance.create_tweet.return_value = Mock(
                    data={"id": "1234567890"}
                )
                mock_client.return_value = mock_instance

                notifier = TwitterNotifier()
                notification = SwapNotification(
                    swap=sample_swap, message="Test notification"
                )

                result = await notifier.notify(notification)

                assert result is True
                mock_instance.create_tweet.assert_called_once()


class TestConsoleNotifier:
    """Test console notification functionality."""

    @pytest.mark.asyncio
    async def test_console_output(self, sample_swap, capsys):
        """Test console notification output."""
        notifier = ConsoleNotifier()
        notification = SwapNotification(swap=sample_swap, message="Test notification")

        result = await notifier.notify(notification)

        assert result is True
        captured = capsys.readouterr()
        assert "New BTC⇆XMR Atomic Swap!" in captured.out
        assert "abc123def456789" in captured.out
