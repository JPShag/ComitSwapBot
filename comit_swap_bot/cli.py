
"""Command-line interface for the swap bot."""

import asyncio
import signal
import sys



import click
import structlog
from structlog.stdlib import LoggerFactory

from . import __version__
from .config import config
from .database import Database
from .notifiers import NotificationManager
from .orchestrator import SwapOrchestrator
from .price_fetcher import PriceFetcher
from .swap_watcher import SwapWatcher


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


@click.group()
@click.version_option(version=__version__)
def cli():
    """COMIT Swap Bot - Detecting BTC⇆XMR atomic swaps."""
    pass


@cli.command()
@click.option(
    "--check-interval",
    default=config.check_interval,
    help="Interval in seconds between checks",
)
def watch(check_interval: int):
    """Watch for new atomic swaps in real-time."""
    logger.info("Starting swap bot", version=__version__)

    async def run():
        # Initialize components
        db = Database()
        await db.init()

        watcher = SwapWatcher(db)
        price_fetcher = PriceFetcher()
        notifier = NotificationManager()

        orchestrator = SwapOrchestrator(
            watcher=watcher, price_fetcher=price_fetcher, notifier=notifier, database=db
        )

        # Setup signal handlers
        loop = asyncio.get_event_loop()

        def signal_handler(sig):
            logger.info("Received signal, shutting down", signal=sig)
            loop.create_task(orchestrator.stop())

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

        # Start watching
        try:
            await orchestrator.start()
        except Exception as e:
            logger.error("Fatal error", error=str(e), exc_info=True)
            sys.exit(1)
        finally:
            await db.close()
            await price_fetcher.close()

    asyncio.run(run())


@cli.command()
@click.option("--txid", required=True, help="Transaction ID to check")
def check(txid: str):
    """Check if a specific transaction is part of an atomic swap."""

    async def run():
        db = Database()
        await db.init()

        watcher = SwapWatcher(db)
        swap = await watcher.check_transaction(txid)

        if swap:
            click.echo(f"✓ Transaction {txid} is part of an atomic swap!")
            click.echo(f"  Swap ID: {swap.swap_id}")
            click.echo(f"  State: {swap.state.value}")
            click.echo(f"  Amount: {swap.amount_btc} BTC")
            if swap.amount_xmr:
                click.echo(f"  XMR Amount: {swap.amount_xmr} XMR")
        else:
            click.echo(f"✗ Transaction {txid} is not part of an atomic swap")

        await db.close()

    asyncio.run(run())


@cli.command()
@click.option("--start-height", required=True, type=int, help="Starting block height")
@click.option("--end-height", required=True, type=int, help="Ending block height")
def backfill(start_height: int, end_height: int):
    """Backfill historical swaps between block heights."""

    async def run():
        db = Database()
        await db.init()

        watcher = SwapWatcher(db)
        price_fetcher = PriceFetcher()
        notifier = NotificationManager()

        orchestrator = SwapOrchestrator(
            watcher=watcher, price_fetcher=price_fetcher, notifier=notifier, database=db
        )

        await orchestrator.backfill(start_height, end_height)

        await db.close()
        await price_fetcher.close()

    asyncio.run(run())


@cli.command()
@click.option("--limit", default=10, help="Number of swaps to show")
def list_swaps(limit: int):
    """List recent atomic swaps."""

    async def run():
        db = Database()
        await db.init()

        swaps = await db.get_recent_swaps(limit)

        if not swaps:
            click.echo("No swaps found")
            return

        click.echo(f"Recent {len(swaps)} swaps:\n")

        for swap in swaps:
            click.echo(f"Swap ID: {swap.swap_id}")
            click.echo(f"  State: {swap.state.value}")
            click.echo(f"  Amount: {swap.amount_btc} BTC")
            if swap.amount_xmr:
                click.echo(f"  XMR: {swap.amount_xmr} XMR")
            click.echo(f"  Created: {swap.created_at}")
            if swap.tweet_id:
                click.echo(f"  Tweet: https://twitter.com/i/status/{swap.tweet_id}")
            click.echo()

        await db.close()

    asyncio.run(run())


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
