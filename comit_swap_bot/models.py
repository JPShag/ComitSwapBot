"""
Data structures for atomic swap detection and tracking.

These models represent the core entities we work with when monitoring
COMIT atomic swaps. Had to iterate on the schema a few times to handle
edge cases like partially redeemed swaps and malformed HTLC scripts.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class SwapState(str, Enum):
    """Current lifecycle state of an atomic swap."""

    LOCKED = "locked"  # Initial HTLC transaction confirmed
    REDEEMED = "redeemed"  # Secret revealed, swap completed
    REFUNDED = "refunded"  # Timelock expired, funds returned
    EXPIRED = "expired"  # Past timelock but no refund seen yet


class HTLCType(str, Enum):
    """Classification of HTLC transaction type."""

    LOCK = "lock"  # Initial HTLC setup transaction
    REDEEM = "redeem"  # Secret reveal transaction
    REFUND = "refund"  # Timelock expiry refund


class HTLCScript(BaseModel):
    """
    Parsed components of an HTLC script.

    These scripts follow the standard COMIT pattern with a secret hash,
    recipient/sender pubkey hashes, and a timelock value.
    """

    recipient_pubkey_hash: str = Field(description="Hash160 of recipient's public key")
    sender_pubkey_hash: str = Field(description="Hash160 of sender's public key")
    secret_hash: str = Field(description="SHA256 hash of the secret")
    timelock_height: int = Field(description="Block height when refund becomes valid")


class Transaction(BaseModel):
    """Basic Bitcoin transaction representation."""

    txid: str = Field(description="Transaction ID (double-SHA256 hash)")
    version: int = Field(default=2, description="Transaction version number")
    locktime: int = Field(
        default=0, description="Earliest block height for confirmation"
    )
    byte_size: int = Field(description="Transaction size in bytes")
    weight_units: int = Field(description="BIP141 weight units for fee calculation")
    fee_sats: Decimal | None = Field(None, description="Transaction fee in satoshis")
    block_height: int | None = Field(None, description="Block height if confirmed")
    block_time: datetime | None = Field(
        None, description="Block timestamp if confirmed"
    )
    confirmation_count: int = Field(default=0, description="Number of confirmations")


class HTLCTransaction(Transaction):
    """
    HTLC-specific transaction with script details.

    Extends the base transaction with HTLC-specific fields like the
    parsed script components and the UTXO output being spent/created.
    """

    htlc_classification: HTLCType
    script_details: HTLCScript | None = Field(
        None, description="Parsed HTLC script components"
    )
    value_sats: int = Field(description="Output value in satoshis")
    output_index: int = Field(description="Index of the HTLC output")
    revealed_secret: str | None = Field(
        None, description="32-byte secret for redeem transactions"
    )


class AtomicSwap(BaseModel):
    """
    Complete atomic swap tracking record.

    Represents the full lifecycle of a BTC⇄XMR atomic swap from initial
    HTLC lock through redemption or refund. The swap_id is generated from
    the lock transaction hash for consistent identification.
    """

    swap_id: str = Field(description="Unique identifier derived from lock TXID")
    lock_transaction: HTLCTransaction = Field(
        description="Initial HTLC setup transaction"
    )
    redeem_transaction: HTLCTransaction | None = Field(
        None, description="Secret reveal transaction"
    )
    refund_transaction: HTLCTransaction | None = Field(
        None, description="Timeout refund transaction"
    )
    current_state: SwapState = Field(description="Current lifecycle state")

    # Bitcoin amounts and pricing
    btc_amount: Decimal = Field(description="Amount in BTC (8 decimal places)")
    xmr_amount: Decimal | None = Field(
        None, description="Equivalent XMR amount at detection time"
    )
    btc_xmr_rate: Decimal | None = Field(None, description="BTC/XMR exchange rate used")

    # Timestamps
    detected_at: datetime = Field(description="When we first detected this swap")
    last_updated: datetime = Field(description="Last modification timestamp")

    # Notification tracking
    notification_sent: str | None = Field(
        None, description="Twitter tweet ID if posted"
    )

    class Config:
        """Pydantic model configuration."""

        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            Decimal: lambda d: str(d),
        }


class SwapAlert(BaseModel):
    """
    Notification payload for detected swaps.

    Contains the swap data plus formatted message content for social media.
    I've experimented with different hashtag combinations to maximize reach
    while avoiding crypto spam filters.
    """

    swap_data: AtomicSwap = Field(description="The detected atomic swap")
    alert_message: str = Field(description="Formatted notification text")
    hashtag_list: list[str] = Field(
        default_factory=lambda: ["AtomicSwap", "Bitcoin", "Monero", "COMIT", "DeFi"],
        description="Social media hashtags for maximum visibility",
    )


class SwapNotification(BaseModel):
    """Notification payload for detected swaps."""

    swap: AtomicSwap = Field(description="The detected atomic swap")
    message: str = Field(description="Notification message")
