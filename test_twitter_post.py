#!/usr/bin/env python3
"""
Test script to create a mock atomic swap and post it to Twitter.

This script simulates discovering an atomic swap and posting about it,
allowing you to test the Twitter functionality without waiting for a real swap.
"""

import asyncio
import os
from datetime import datetime, timezone
from decimal import Decimal

# Set up environment variables for Twitter API (you'll need to set these)
# You can get these from https://developer.twitter.com/
if not os.getenv("TWITTER_API_KEY"):
    print("⚠️  Please set Twitter API credentials as environment variables:")
    print("   export TWITTER_API_KEY='your_api_key'")
    print("   export TWITTER_API_SECRET='your_api_secret'")
    print("   export TWITTER_ACCESS_TOKEN='your_access_token'")
    print("   export TWITTER_ACCESS_TOKEN_SECRET='your_access_token_secret'")
    print("\n   You can get these from: https://developer.twitter.com/")
    exit(1)

# Import after setting environment
from comit_swap_bot.models import (
    AtomicSwap,
    HTLCScript,
    HTLCTransaction,
    HTLCType,
    SwapState,
)
from comit_swap_bot.notifiers import SwapNotification, TwitterNotifier
from comit_swap_bot.price_fetcher import PriceFetcher


async def create_mock_swap() -> AtomicSwap:
    """Create a realistic mock atomic swap for testing."""

    # Create HTLC script details
    htlc_script = HTLCScript(
        recipient_pubkey_hash="1234567890abcdef1234567890abcdef12345678",
        sender_pubkey_hash="abcdef1234567890abcdef1234567890abcdef12",
        secret_hash="fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321",
        timelock_height=850000
    )

    # Create lock transaction
    lock_tx = HTLCTransaction(
        txid="a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890",
        version=2,
        locktime=0,
        byte_size=250,
        weight_units=1000,
        fee_sats=Decimal("1500"),
        block_height=849500,
        block_time=datetime.now(timezone.utc),
        confirmation_count=3,
        htlc_classification=HTLCType.LOCK,
        script_details=htlc_script,
        value_sats=15000000,  # 0.15 BTC
        output_index=0,
        revealed_secret=None,
    )
      # Get current BTC/XMR rate
    print("📊 Fetching current BTC/XMR rate...")
    price_fetcher = PriceFetcher()
    current_rate = await price_fetcher.get_btc_to_xmr_rate()
    await price_fetcher.close()

    btc_amount = Decimal("0.15")
    if current_rate:
        xmr_amount = btc_amount * current_rate
    else:
        xmr_amount = None

    # Create the atomic swap
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

    return swap


async def test_twitter_post():
    """Test posting a mock swap to Twitter."""
    try:
        print("🔄 Creating mock atomic swap...")
        swap = await create_mock_swap()

        print("✅ Mock swap created:")
        print(f"   Swap ID: {swap.swap_id}")
        print(f"   BTC Amount: {swap.btc_amount} BTC")
        print(f"   XMR Amount: {swap.xmr_amount} XMR")
        print(f"   Rate: 1 BTC = {swap.btc_xmr_rate} XMR")
        print(f"   TX ID: {swap.lock_transaction.txid}")

        print("\n📝 Creating Twitter notification...")
        notifier = TwitterNotifier()
        notification = SwapNotification(
            swap=swap,
            message="Test atomic swap notification"
        )

        # Show the message that would be tweeted
        message = notifier.format_swap_message(swap)
        print(f"\n📱 Tweet message ({len(message)} characters):")
        print("=" * 50)
        print(message)
        print("=" * 50)

        # Ask for confirmation before posting
        confirm = input("\n🤔 Post this tweet? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("❌ Tweet cancelled.")
            return

        print("\n🐦 Posting to Twitter...")
        success = await notifier.notify(notification)

        if success:
            print("✅ Successfully posted to Twitter!")
            print("🎉 Check your Twitter account to see the tweet.")
        else:
            print("❌ Failed to post to Twitter. Check your credentials and try again.")

    except Exception as e:
        print(f"💥 Error: {e}")
        print("Check your Twitter API credentials and network connection.")


if __name__ == "__main__":
    print("🚀 COMIT Atomic Swap Bot - Twitter Test")
    print("=" * 45)
    asyncio.run(test_twitter_post())
