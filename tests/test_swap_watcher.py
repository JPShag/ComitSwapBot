"""Tests for swap watcher."""

from decimal import Decimal

import pytest
import pytest_asyncio

from comit_swap_bot.database import SwapDatabase
from comit_swap_bot.models import SwapState
from comit_swap_bot.swap_watcher import SwapWatcher


@pytest_asyncio.fixture
async def db():
    """Create test database."""
    db = SwapDatabase()
    db.engine = db.engine.execution_options(url="sqlite+aiosqlite:///:memory:")
    await db.init()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def watcher(db):
    """Create swap watcher instance."""
    return SwapWatcher(db)


class TestSwapWatcher:
    """Test swap watcher functionality."""

    def test_htlc_pattern_matching(self, watcher):
        """Test HTLC script pattern detection."""
        # Valid HTLC script bytes (simplified for testing)
        # Use a reasonable timelock (e.g., 1703980800 = 2023-12-30 12:00:00)
        timelock_bytes = (1703980800).to_bytes(4, byteorder="little")
        valid_script = (
            b"\x63"  # OP_IF
            b"\xa8\x20" + b"a" * 32 + b"\x88"  # OP_SHA256 <secret_hash> OP_EQUALVERIFY
            b"\x76\xa9\x14"
            + b"b"
            * 20
            + b"\x88\xac"  # DUP HASH160 <recipient> EQUALVERIFY CHECKSIG
            b"\x67"  # OP_ELSE
            + timelock_bytes
            + b"\xb1\x75"  # <timelock> CHECKLOCKTIMEVERIFY DROP
            + b"\x76\xa9\x14"
            + b"c" * 20
            + b"\x88\xac"  # DUP HASH160 <sender> EQUALVERIFY CHECKSIG
            + b"\x68"  # OP_ENDIF
        )

        # Test detection
        output = {"scriptPubKey": {"hex": valid_script.hex()}}
        htlc = watcher._detect_htlc_script(output)

        assert htlc is not None

        # Test detection
        output = {"scriptPubKey": {"hex": valid_script.hex()}}
        htlc = watcher._detect_htlc_script(output)

        assert htlc is not None
        assert htlc.secret_hash == "61" * 32  # hex of b"a" * 32
        assert htlc.recipient_pubkey_hash == "62" * 20  # hex of b"b" * 20
        assert htlc.sender_pubkey_hash == "63" * 20  # hex of b"c" * 20
        assert htlc.timelock_height > 0

    @pytest.mark.asyncio
    async def test_swap_detection(self, watcher, db):
        """Test full swap detection flow."""
        # Mock transaction data
        txid = "abc123"
        timelock_bytes = (1703980800).to_bytes(4, byteorder="little")
        output = {
            "scriptPubKey": {
                "hex": (
                    b"\x63"
                    b"\xa8\x20" + b"x" * 32 + b"\x88"
                    b"\x76\xa9\x14" + b"y" * 20 + b"\x88\xac"
                    b"\x67" + timelock_bytes + b"\xb1\x75"  # Valid timelock
                    b"\x76\xa9\x14" + b"z" * 20 + b"\x88\xac"
                    b"\x68"
                ).hex()
            },
            "value": 0.1,
        }

        # Process HTLC detection
        htlc_script = watcher._detect_htlc_script(output)
        await watcher._handle_htlc_detection(txid, 0, output, htlc_script)

        # Verify swap was saved
        swap = await db.get_swap_by_lock_txid(txid)
        assert swap is not None
        assert swap.lock_transaction.txid == txid
        assert swap.current_state == SwapState.LOCKED
        assert swap.btc_amount == Decimal("0.1")

    @pytest.mark.asyncio
    async def test_htlc_redeem_detection(self, watcher, db):
        """Test HTLC redeem detection."""
        # First create a locked HTLC
        lock_txid = "lock123"
        timelock_bytes = (1703980800).to_bytes(4, byteorder="little")
        output = {
            "scriptPubKey": {
                "hex": (
                    b"\x63"
                    b"\xa8\x20" + b"s" * 32 + b"\x88"
                    b"\x76\xa9\x14" + b"r" * 20 + b"\x88\xac"
                    b"\x67" + timelock_bytes + b"\xb1\x75"  # Valid timelock
                    b"\x76\xa9\x14" + b"s" * 20 + b"\x88\xac"
                    b"\x68"
                ).hex()
            },
            "value": 0.05,
        }

        htlc_script = watcher._detect_htlc_script(output)
        await watcher._handle_htlc_detection(lock_txid, 0, output, htlc_script)

        # Add to pending HTLCs
        swap = await db.get_swap_by_lock_txid(lock_txid)
        watcher._pending_htlcs[lock_txid] = swap.lock_transaction

        # Now simulate a redeem
        redeem_txid = "redeem456"
        input_data = {
            "txid": lock_txid,
            "witness": [
                "signature_hex",
                "s" * 64,  # 32-byte secret in hex
                "pubkey_hex",
            ],
        }

        await watcher._handle_htlc_spend(redeem_txid, lock_txid, input_data)

        # Verify swap was updated
        swap = await db.get_swap_by_lock_txid(lock_txid)
        assert swap.current_state == SwapState.REDEEMED
        assert swap.redeem_transaction is not None
        assert swap.redeem_transaction.txid == redeem_txid
        assert swap.redeem_transaction.revealed_secret == "s" * 64
