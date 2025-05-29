"""
Main coordination logic for the atomic swap monitoring system.

This module ties together all the components: mempool watching, price fetching,
database persistence, and notifications. I learned the hard way that proper
orchestration is crucial after my first version crashed every few hours due
to unhandled websocket disconnections.
"""

import asyncio
from datetime import datetime, timezone

import structlog

from .database import SwapDatabase
from .health import HealthServer
from .models import AtomicSwap
from .notifiers import NotificationManager
from .price_fetcher import PriceFetcher
from .swap_watcher import SwapWatcher

logger = structlog.get_logger()


class SwapOrchestrator:
    """
    Central coordinator for all swap monitoring operations.

    Manages the lifecycle of swap detection, enrichment with price data,
    and notifications. Also handles graceful shutdown and error recovery
    because Bitcoin never sleeps and neither should this bot.
    """

    def __init__(
        self,
        mempool_watcher: SwapWatcher,
        price_service: PriceFetcher,
        notification_mgr: NotificationManager,
        swap_db: SwapDatabase,
        enable_health_server: bool = True,
    ):
        """
        Wire up all the moving parts.

        Args:
            mempool_watcher: Monitors mempool for HTLC transactions
            price_service: Fetches BTC/XMR exchange rates
            notification_mgr: Handles Twitter and Discord notifications
            swap_db: Persistent storage for swap records
            enable_health_server: Whether to expose health check endpoint
        """
        self.mempool_watcher = mempool_watcher
        self.price_service = price_service
        self.notification_mgr = notification_mgr
        self.swap_db = swap_db
        self.is_running = False
        self.background_tasks = []
        self.health_server = HealthServer() if enable_health_server else None

        # Track stats for debugging
        self.total_swaps_processed = 0
        self.last_price_update = None

    async def start(self):
        """
        Fire up the whole operation.

        Starts all background services and monitors them for failures.
        The health server helps with Docker health checks and debugging
        when things go sideways (which they will).
        """
        self.is_running = True
        logger.info("🚀 Starting atomic swap monitoring bot")

        # Get the health check endpoint running first
        if self.health_server:
            await self.health_server.start()
            self.health_server.update_status(
                started_at=datetime.utcnow().isoformat(),
                watcher_running=True,
                swaps_processed=self.total_swaps_processed,
            )

        # Launch all the background workers
        self.background_tasks = [
            asyncio.create_task(self.mempool_watcher.start(), name="mempool-watcher"),
            asyncio.create_task(self._handle_pending_swaps(), name="swap-processor"),
            asyncio.create_task(
                self._monitor_swap_lifecycle(), name="lifecycle-monitor"
            ),
        ]

        # Wait for any task to complete (usually means an error occurred)
        try:
            await asyncio.gather(*self.background_tasks)
        except Exception as e:
            logger.error(
                "💥 Background task crashed",
                error=str(e),
                task_count=len(self.background_tasks),
            )
            raise

    async def stop(self):
        """Gracefully shut down all services."""
        self.is_running = False
        logger.info("🛑 Shutting down swap orchestrator")

        # Cancel all background tasks
        for task in self.background_tasks:
            if not task.done():
                task.cancel()

        # Wait for clean shutdown (with timeout)
        try:
            await asyncio.wait_for(
                asyncio.gather(*self.background_tasks, return_exceptions=True),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.warning("⏰ Shutdown timeout - some tasks may still be running")

        # Stop the mempool connection
        await self.mempool_watcher.stop()

        # Finally stop health server
        if self.health_server:
            await self.health_server.stop()

        logger.info("✅ Swap orchestrator stopped cleanly")

    async def _handle_pending_swaps(self):
        """
        Process swaps that need price data or notifications.

        This runs continuously to catch up on any swaps that were detected
        but couldn't be fully processed immediately (e.g., price API was down).
        """
        while self.is_running:
            try:
                # Find swaps missing price data or notifications
                incomplete_swaps = await self.swap_db.get_pending_swaps()

                for pending_swap in incomplete_swaps:
                    # Enrich with current BTC/XMR rate if needed
                    if not pending_swap.amount_xmr:
                        await self._enrich_with_price_data(pending_swap)

                    # Send notification if we haven't already
                    if not pending_swap.tweet_id and pending_swap.amount_xmr:
                        await self.notification_mgr.notify_swap(pending_swap)

                # Check again in 30 seconds - not too aggressive
                await asyncio.sleep(30)

            except Exception as e:
                logger.error("🔥 Error in swap processing loop", error=str(e))
                # Back off a bit more on errors
                await asyncio.sleep(60)

    async def _monitor_swap_lifecycle(self):
        """
        Watch for redemptions and refunds of tracked swaps.

        The SwapWatcher handles initial detection, but this monitors
        the full lifecycle of each swap to completion.
        """
        while self.is_running:
            try:
                # The swap watcher already monitors for updates via websocket
                # This is mostly a placeholder for additional lifecycle logic
                await asyncio.sleep(60)

            except Exception as e:
                logger.error("🔥 Error in lifecycle monitoring", error=str(e))
                await asyncio.sleep(60)

    async def _enrich_with_price_data(self, incomplete_swap: AtomicSwap):
        """
        Add current market pricing to a detected swap.

        Args:
            incomplete_swap: Swap record missing XMR amount calculation
        """
        try:
            # Get latest BTC/XMR rate from price service
            current_rate = await self.price_service.get_btc_to_xmr_rate()
            if current_rate:
                incomplete_swap.btc_xmr_rate = current_rate
                incomplete_swap.xmr_amount = (
                    await self.price_service.convert_btc_to_xmr(
                        incomplete_swap.btc_amount
                    )
                )
                incomplete_swap.last_updated = datetime.now(timezone.utc)
                await self.swap_db.save_swap(incomplete_swap)

                self.last_price_update = datetime.now(timezone.utc)

                logger.info(
                    "💱 Added pricing data to swap",
                    swap_id=incomplete_swap.swap_id,
                    btc_xmr_rate=float(current_rate),
                    xmr_amount=float(incomplete_swap.xmr_amount),
                )

        except Exception as e:
            logger.error(
                "💸 Failed to add price data",
                swap_id=incomplete_swap.swap_id,
                error=str(e),
            )

    async def run_historical_backfill(self, start_height: int, end_height: int):
        """
        Scan historical blocks for missed atomic swaps.

        Useful when the bot was offline or for initial setup to find
        past swaps. Be careful with large ranges - this can take a while
        and hit API rate limits.

        Args:
            start_height: Bitcoin block height to start scanning from
            end_height: Bitcoin block height to stop scanning at
        """
        logger.info(
            "📚 Starting historical backfill scan",
            start_block=start_height,
            end_block=end_height,
            total_blocks=end_height - start_height,
        )

        try:
            # Let the swap watcher handle the actual scanning
            await self.mempool_watcher.backfill(start_height, end_height)

            # Process any newly found swaps
            await self._handle_pending_swaps()

            self.total_swaps_processed += 1  # Update stats

            logger.info("✅ Historical backfill completed successfully")

        except Exception as e:
            logger.error("💥 Backfill scan failed", error=str(e))
            raise
