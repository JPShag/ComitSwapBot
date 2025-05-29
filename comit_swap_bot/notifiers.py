"""Notification system for detected swaps."""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
import tweepy
from apprise import Apprise

from .config import config
from .models import AtomicSwap, SwapNotification

logger = structlog.get_logger()


class Notifier(ABC):
    """Base class for swap notifiers."""

    @abstractmethod
    async def notify(self, notification: SwapNotification) -> bool:
        """Send a notification about a detected swap."""
        pass

    def format_swap_message(self, swap: AtomicSwap) -> str:
        """Format a swap into a notification message with proper attribution."""
        message_parts = [
            "🔄 New BTC⇆XMR Atomic Swap!",
            "",
            f"📦 TX: {swap.lock_transaction.txid[:16]}...",
            f"💰 Amount: {swap.btc_amount:.8f} BTC",
        ]

        if swap.xmr_amount and swap.btc_xmr_rate:
            message_parts.append(f"   ≈ {swap.xmr_amount:.4f} XMR")
            message_parts.append(f"📊 Rate: 1 BTC = {swap.btc_xmr_rate:.4f} XMR")
            # Add CoinGecko attribution when price data is included
            message_parts.append(f"💱 {config.coingecko_attribution_text}")

        message_parts.extend(
            [
                f"🕐 {swap.detected_at.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                "",
                " ".join(f"#{tag}" for tag in ["AtomicSwap", "Bitcoin", "Monero"]),
            ]
        )

        return "\n".join(message_parts)


class TwitterNotifier(Notifier):
    """Twitter notification handler."""

    def __init__(self):
        """Initialize Twitter client."""
        if not all(
            [
                config.twitter_api_key,
                config.twitter_api_secret,
                config.twitter_access_token,
                config.twitter_access_token_secret,
            ]
        ):
            raise ValueError("Twitter credentials not configured")

        # Initialize v2 client for tweeting
        self.client = tweepy.Client(
            consumer_key=config.twitter_api_key,
            consumer_secret=config.twitter_api_secret,
            access_token=config.twitter_access_token,
            access_token_secret=config.twitter_access_token_secret,
        )

    async def notify(self, notification: SwapNotification) -> bool:
        """Tweet about a detected swap."""
        try:
            # Format message
            message = self.format_swap_message(notification.swap)

            # Ensure message fits Twitter's character limit
            if len(message) > 280:
                # Truncate transaction ID if needed
                message = message.replace(
                    notification.swap.lock_transaction.txid[:16],
                    notification.swap.lock_transaction.txid[:12],
                )

            # Tweet in a thread-safe way
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, self.client.create_tweet, message
            )

            tweet_id = response.data["id"]
            logger.info(
                "Tweeted swap notification",
                swap_id=notification.swap.swap_id,
                tweet_id=tweet_id,
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to tweet", swap_id=notification.swap.swap_id, error=str(e)
            )
            return False


class AppriseNotifier(Notifier):
    """Multi-platform notification handler using Apprise."""

    def __init__(self, urls: Optional[List[str]] = None):
        """Initialize Apprise with notification URLs."""
        self.apprise = Apprise()

        urls = urls or config.apprise_urls
        for url in urls:
            self.apprise.add(url)

        if not self.apprise.urls():
            logger.warning("No Apprise URLs configured")

    async def notify(self, notification: SwapNotification) -> bool:
        """Send notification via Apprise."""
        try:
            message = self.format_swap_message(notification.swap)
            title = "New BTC⇆XMR Atomic Swap Detected!"

            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self.apprise.notify, message, title
            )

            if result:
                logger.info(
                    "Sent Apprise notification", swap_id=notification.swap.swap_id
                )
            else:
                logger.warning(
                    "Apprise notification failed", swap_id=notification.swap.swap_id
                )

            return result

        except Exception as e:
            logger.error(
                "Apprise error", swap_id=notification.swap.swap_id, error=str(e)
            )
            return False


class ConsoleNotifier(Notifier):
    """Simple console output notifier for testing."""

    async def notify(self, notification: SwapNotification) -> bool:
        """Print notification to console."""
        print("\n" + "=" * 60)
        print(self.format_swap_message(notification.swap))
        print("=" * 60 + "\n")
        return True


class NotificationManager:
    """Manages multiple notifiers."""

    def __init__(self):
        """Initialize notification manager."""
        self.notifiers: List[Notifier] = []

        # Add configured notifiers
        if config.enable_twitter:
            try:
                self.notifiers.append(TwitterNotifier())
            except Exception as e:
                logger.error("Failed to initialize Twitter notifier", error=str(e))

        if config.enable_apprise:
            self.notifiers.append(AppriseNotifier())

        # Always add console notifier for visibility
        self.notifiers.append(ConsoleNotifier())

    async def notify_swap(self, swap: AtomicSwap):
        """Notify all configured notifiers about a swap."""
        notification = SwapNotification(
            swap=swap, message=f"Detected atomic swap: {swap.swap_id}"
        )

        # Send notifications concurrently
        tasks = [notifier.notify(notification) for notifier in self.notifiers]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if isinstance(r, bool) and r)

        logger.info(
            "Sent notifications",
            swap_id=swap.swap_id,
            success_count=success_count,
            total_count=len(self.notifiers),
        )
