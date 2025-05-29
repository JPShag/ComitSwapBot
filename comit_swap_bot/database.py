"""
Database persistence for atomic swap records.

Using SQLite for simplicity since we're not dealing with huge volumes.
The schema has evolved over time as I discovered edge cases - initially
didn't account for partial redemptions or multiple refund attempts.
"""

import structlog
from sqlalchemy import Column, DateTime, Index, Numeric, String, Text, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .config import config
from .models import AtomicSwap, SwapState

logger = structlog.get_logger()
Base = declarative_base()


class SwapRecord(Base):
    """
    SQLite table schema for atomic swap persistence.

    Stores both normalized fields for querying and a JSON blob
    with the complete swap data for easy serialization.
    """

    __tablename__ = "atomic_swaps"

    # Primary identification
    swap_id = Column(String, primary_key=True)
    lock_txid = Column(String, nullable=False, index=True)
    redeem_txid = Column(String, nullable=True)
    refund_txid = Column(String, nullable=True)

    # State tracking
    current_state = Column(String, nullable=False)

    # Financial data
    btc_amount = Column(Numeric(16, 8), nullable=False)
    xmr_amount = Column(Numeric(16, 8), nullable=True)
    btc_xmr_rate = Column(Numeric(16, 8), nullable=True)

    # Timestamps
    detected_at = Column(DateTime, nullable=False)
    last_updated = Column(DateTime, nullable=False)

    # Social media tracking
    notification_sent = Column(String, nullable=True)

    # Complete record as JSON for flexibility
    full_swap_json = Column(Text, nullable=False)

    __table_args__ = (
        Index("idx_detection_time", "detected_at"),
        Index("idx_swap_state", "current_state"),
        Index("idx_notification_status", "notification_sent"),
    )


class SwapDatabase:
    """
    Database operations for atomic swap persistence.

    Handles storage, retrieval, and querying of swap records with
    proper async support for non-blocking database access.
    """

    def __init__(self):
        """Initialize database connection."""
        self.engine = create_async_engine(
            config.database_url, echo=False, pool_pre_ping=True
        )
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init(self):
        """Initialize database schema."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized")

    async def close(self):
        """Close database connection."""
        await self.engine.dispose()

    async def save_swap(self, swap: AtomicSwap):
        """Save or update a swap record."""
        async with self.async_session() as session:
            record = SwapRecord(
                swap_id=swap.swap_id,
                lock_txid=swap.lock_transaction.txid,
                redeem_txid=swap.redeem_transaction.txid
                if swap.redeem_transaction
                else None,
                refund_txid=swap.refund_transaction.txid
                if swap.refund_transaction
                else None,
                current_state=swap.current_state.value,
                btc_amount=swap.btc_amount,
                xmr_amount=swap.xmr_amount,
                btc_xmr_rate=swap.btc_xmr_rate,
                detected_at=swap.detected_at,
                last_updated=swap.last_updated,
                notification_sent=getattr(swap, "notification_sent", None),
                full_swap_json=swap.model_dump_json(),
            )

            await session.merge(record)
            await session.commit()

    async def get_swap(self, swap_id: str) -> AtomicSwap | None:
        """Get a swap by ID."""
        async with self.async_session() as session:
            result = await session.get(SwapRecord, swap_id)
            if result:
                return AtomicSwap.model_validate_json(result.full_swap_json)
            return None

    async def get_swap_by_lock_txid(self, txid: str) -> AtomicSwap | None:
        """Get a swap by its lock transaction ID."""
        async with self.async_session() as session:
            result = await session.execute(
                text("SELECT full_swap_json FROM atomic_swaps WHERE lock_txid = :txid"),
                {"txid": txid},
            )
            row = result.first()
            if row:
                return AtomicSwap.model_validate_json(row[0])
            return None

    async def get_pending_swaps(self) -> list[AtomicSwap]:
        """Get all swaps in locked state."""
        async with self.async_session() as session:
            result = await session.execute(
                text(
                    "SELECT full_swap_json FROM atomic_swaps WHERE current_state = :state"
                ),
                {"state": SwapState.LOCKED.value},
            )
            return [AtomicSwap.model_validate_json(row[0]) for row in result]

    async def get_recent_swaps(self, limit: int = 10) -> list[AtomicSwap]:
        """Get recent swaps."""
        async with self.async_session() as session:
            result = await session.execute(
                text(
                    "SELECT full_swap_json FROM atomic_swaps ORDER BY detected_at DESC LIMIT :limit"
                ),
                {"limit": limit},
            )
            return [AtomicSwap.model_validate_json(row[0]) for row in result]

    async def update_tweet_id(self, swap_id: str, tweet_id: str):
        """Update the tweet ID for a swap."""
        async with self.async_session() as session:
            await session.execute(
                text(
                    "UPDATE atomic_swaps SET notification_sent = :tweet_id WHERE swap_id = :swap_id"
                ),
                 {"tweet_id": tweet_id, "swap_id": swap_id},
            )
            await session.commit()
