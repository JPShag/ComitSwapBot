#!/usr/bin/env python3
"""
Demo mode script to run the COMIT atomic swap bot.

This script demonstrates the full functionality:
1. Watches for atomic swaps on Bitcoin network
2. Detects COMIT-style HTLCs
3. Calculates XMR equivalent using current exchange rates
4. Posts tweets with transaction details

For testing purposes, you can also inject a mock transaction.
"""

import asyncio
import os
import signal
import sys
from datetime import datetime, timezone
from decimal import Decimal

import structlog
from structlog.stdlib import LoggerFactory

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


async def create_demo_swap():
    """Create a demo atomic swap for immediate testing."""
    from comit_swap_bot.models import (
        AtomicSwap,
        HTLCScript,
        HTLCTransaction,
        HTLCType,
        SwapState,
    )
    from comit_swap_bot.price_fetcher import PriceFetcher

    print("🎭 Creating demo atomic swap...")

    # Create realistic HTLC script
    htlc_script = HTLCScript(
        recipient_pubkey_hash="76a914" + "a" * 40 + "88ac",
        sender_pubkey_hash="76a914" + "b" * 40 + "88ac",
        secret_hash="a914" + "c" * 64 + "87",
        timelock_height=850000
    )

    # Create lock transaction with realistic data
    lock_tx = HTLCTransaction(
        txid="demo" + "a1b2c3d4e5f67890" * 3 + "1234567890abcdef",  # 64 char txid
        version=2,
        locktime=0,
        byte_size=225,
        weight_units=900,
        fee_sats=Decimal("2500"),
        block_height=849750,
        block_time=datetime.now(timezone.utc),
        confirmation_count=1,
        htlc_classification=HTLCType.LOCK,
        script_details=htlc_script,
        value_sats=25000000,  # 0.25 BTC
        output_index=0,
        revealed_secret=None,
    )
      # Get current exchange rate
    price_fetcher = PriceFetcher()
    try:
        current_rate = await price_fetcher.get_btc_to_xmr_rate()
        btc_amount = Decimal("0.25")
        if current_rate:
            xmr_amount = btc_amount * current_rate
        else:
            xmr_amount = None
    finally:
        await price_fetcher.close()

    # Create atomic swap
    swap = AtomicSwap(
        swap_id=f"{lock_tx.txid}:0",
        lock_transaction=lock_tx,
        redeem_transaction=None,
        refund_transaction=None,
        current_state=SwapState.LOCKED,
        btc_amount=btc_amount,
        xmr_amount=xmr_amount,
        btc_xmr_rate=current_rate,
        detected_at=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
        notification_sent=None,
    )

    print(f"✅ Demo swap created: {swap.btc_amount} BTC ≈ {swap.xmr_amount} XMR")
    return swap


async def run_demo_bot(demo_mode=False):
    """Run the bot in demo or real mode."""
    from comit_swap_bot.database import SwapDatabase
    from comit_swap_bot.notifiers import NotificationManager, SwapNotification
    from comit_swap_bot.orchestrator import SwapOrchestrator
    from comit_swap_bot.price_fetcher import PriceFetcher
    from comit_swap_bot.swap_watcher import SwapWatcher

    logger.info("🚀 Starting COMIT Atomic Swap Bot", demo_mode=demo_mode)

    # Initialize components
    db = SwapDatabase()
    await db.init()

    watcher = SwapWatcher(db)
    price_fetcher = PriceFetcher()
    notifier = NotificationManager()

    orchestrator = SwapOrchestrator(
        watcher=watcher,
        price_fetcher=price_fetcher,
        notifier=notifier,
        database=db
    )

    if demo_mode:
        logger.info("🎭 Running in DEMO mode - will post demo swap")

        # Create and post a demo swap
        demo_swap = await create_demo_swap()

        # Save to database
        await db.save_swap(demo_swap)

        # Create notification
        notification = SwapNotification(
            swap=demo_swap,
            message="Demo atomic swap detected!"
        )

        # Send notification
        success = await notifier.notify_swap(notification)

        if success:
            logger.info("✅ Demo notification sent successfully!")
        else:
            logger.error("❌ Failed to send demo notification")

        await db.close()
        await price_fetcher.close()
        return

    # Real mode - watch for actual swaps
    logger.info("👀 Running in REAL mode - watching for actual atomic swaps")

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def signal_handler(sig):
        logger.info("Received signal, shutting down", signal=sig)
        loop.create_task(orchestrator.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            signal.signal(sig, lambda s, f: signal_handler(s))

    # Start the orchestrator
    try:
        await orchestrator.start()
    except Exception as e:
        logger.error("💥 Fatal error", error=str(e), exc_info=True)
        sys.exit(1)
    finally:
        await db.close()
        await price_fetcher.close()


def check_twitter_credentials():
    """Check if Twitter credentials are configured."""
    required_vars = [
        "TWITTER_API_KEY",
        "TWITTER_API_SECRET",
        "TWITTER_ACCESS_TOKEN",
        "TWITTER_ACCESS_TOKEN_SECRET"
    ]

    # Try to load .env file
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value

    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        print("❌ Missing Twitter credentials:")
        for var in missing:
            print(f"   {var}")
        print()
        print("🔧 Run this to setup credentials:")
        print("   python setup_and_test.py")
        return False

    print("✅ Twitter credentials configured")
    return True


def main():
    """Main entry point."""
    print("🔄 COMIT Atomic Swap Bot - Demo Runner")
    print("=" * 45)

    if not check_twitter_credentials():
        return

    print()
    print("Choose mode:")
    print("  1. Demo mode (post demo swap immediately)")
    print("  2. Real mode (watch for actual atomic swaps)")
    print("  3. Exit")

    try:
        choice = input("\nEnter choice [1-3]: ").strip()

        if choice == "1":
            asyncio.run(run_demo_bot(demo_mode=True))
        elif choice == "2":
            print("\n⚠️  Real mode will watch Bitcoin network for atomic swaps.")
            print("This may take a long time as atomic swaps are rare!")
            confirm = input("Continue? [y/N]: ").strip().lower()
            if confirm == 'y':
                asyncio.run(run_demo_bot(demo_mode=False))
            else:
                print("Cancelled.")
        elif choice == "3":
            print("👋 Goodbye!")
        else:
            print("❌ Invalid choice")

    except KeyboardInterrupt:
        print("\n\n👋 Bot stopped by user")
    except Exception as e:
        print(f"\n💥 Error: {e}")


if __name__ == "__main__":
    main()
