"""Core swap detection engine."""

import asyncio
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
import structlog
import websockets
from bitcoin.core import COIN

from .config import config
from .database import SwapDatabase
from .models import AtomicSwap, HTLCScript, HTLCTransaction, HTLCType, SwapState

logger = structlog.get_logger()


class SwapWatcher:
    """Watches for atomic swap transactions on the Bitcoin network."""

    # HTLC script pattern for COMIT swaps
    # OP_IF
    #   OP_SHA256 <secret_hash> OP_EQUALVERIFY
    #   OP_DUP OP_HASH160 <recipient_pubkey_hash> OP_EQUALVERIFY OP_CHECKSIG
    # OP_ELSE
    #   <timelock> OP_CHECKLOCKTIMEVERIFY OP_DROP
    #   OP_DUP OP_HASH160 <sender_pubkey_hash> OP_EQUALVERIFY OP_CHECKSIG
    # OP_ENDIF

    HTLC_PATTERN = re.compile(
        rb"\x63"  # OP_IF
        rb"\xa8\x20(.{32})\x88"  # OP_SHA256 <32-byte secret_hash> OP_EQUALVERIFY
        rb"\x76\xa9\x14(.{20})\x88\xac"  # OP_DUP OP_HASH160 <20-byte recipient_pubkey_hash> OP_EQUALVERIFY OP_CHECKSIG
        rb"\x67"  # OP_ELSE
        rb"(.{1,5})\xb1\x75"  # <timelock> OP_CHECKLOCKTIMEVERIFY OP_DROP (1-5 bytes for timelock)
        rb"\x76\xa9\x14(.{20})\x88\xac"  # OP_DUP OP_HASH160 <20-byte sender_pubkey_hash> OP_EQUALVERIFY OP_CHECKSIG
        rb"\x68",  # OP_ENDIF
        re.DOTALL,  # Allow . to match newlines
    )

    # Alternative pattern for different COMIT implementations
    HTLC_PATTERN_ALT = re.compile(
        rb"\x63"  # OP_IF
        rb"\xa8\x20(.{32})\x88"  # OP_SHA256 <secret_hash> OP_EQUALVERIFY
        rb"\x76\xa9\x14(.{20})\x88\xac"  # OP_DUP OP_HASH160 <recipient> OP_EQUALVERIFY OP_CHECKSIG
        rb"\x67"  # OP_ELSE
        rb"(.{2,9})\xb1\x75"  # <timelock> OP_CHECKLOCKTIMEVERIFY OP_DROP (more flexible timelock size)
        rb"\x76\xa9\x14(.{20})\x88\xac"  # OP_DUP OP_HASH160 <sender> OP_EQUALVERIFY OP_CHECKSIG
        rb"\x68",  # OP_ENDIF
        re.DOTALL,
    )

    def __init__(self, database: SwapDatabase):
        """Initialize the swap watcher."""
        self.db = database
        self.client = httpx.AsyncClient(timeout=30.0)
        self.watching = False
        self._watched_addresses: set[str] = set()
        self._pending_htlcs: dict[str, HTLCTransaction] = {}

    async def start(self):
        """Start watching for swaps."""
        self.watching = True
        logger.info("Starting swap watcher")

        if config.use_mempool_api:
            await self._watch_mempool_ws()
        else:
            await self._watch_bitcoin_rpc()

    async def stop(self):
        """Stop watching for swaps."""
        self.watching = False
        await self.client.aclose()
        logger.info("Stopped swap watcher")

    async def _watch_mempool_ws(self):
        """Watch for transactions using Mempool.space WebSocket."""
        retry_count = 0
        max_retries = 5

        while self.watching and retry_count < max_retries:
            try:
                async with websockets.connect(
                    config.mempool_ws_url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10,
                ) as ws:
                    logger.info("Connected to Mempool WebSocket")
                    retry_count = 0  # Reset on successful connection
                    await self._subscribe_mempool_ws(ws)
                    await self._handle_mempool_ws_messages(ws)
            except Exception as e:
                retry_count += 1
                logger.error(
                    "WebSocket error",
                    error=str(e),
                    retry_count=retry_count,
                    max_retries=max_retries,
                )
                await self._handle_ws_retry(retry_count, max_retries)

    async def _subscribe_mempool_ws(self, ws):
        """Send subscription message to Mempool WebSocket."""
        await ws.send(
            json.dumps(
                {
                    "action": "want",
                    "data": ["mempool-blocks", "live-2h-chart"],
                }
            )
        )

    async def _handle_mempool_ws_messages(self, ws):
        """Process incoming messages from Mempool WebSocket."""
        while self.watching:
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=30)
                data = json.loads(message)
                await self._process_mempool_ws_data(data)
            except asyncio.TimeoutError:
                await ws.ping()
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed, will retry")
                break

    async def _process_mempool_ws_data(self, data):
        """Process a single message from the Mempool WebSocket feed."""
        # Process mempool blocks (contains new transactions)
        if data.get("mempool-blocks"):
            for block in data["mempool-blocks"]:
                for tx in block.get("transactions", []):
                    await self._process_transaction(tx["txid"])
        # Process individual transactions from live feed
        elif data.get("tx"):
            await self._process_transaction(data["tx"]["txid"])

    async def _handle_ws_retry(self, retry_count, max_retries):
        """Handle retry logic for WebSocket connection."""
        if retry_count < max_retries:
            await asyncio.sleep(min(5 * retry_count, 30))  # Exponential backoff
        else:
            logger.error("Max WebSocket retries exceeded, stopping watcher")
            self.watching = False

    async def _watch_bitcoin_rpc(self):
        """Watch for transactions using Bitcoin RPC."""
        # Implementation for Bitcoin RPC monitoring
        # This would require zmq or polling getrawmempool
        raise NotImplementedError("Bitcoin RPC watching not yet implemented")

    async def _process_transaction(self, txid: str):
        """Process a transaction to check if it's part of an atomic swap."""
        try:
            tx_data = await self._get_transaction(txid)
            if not tx_data:
                return

            # Check each output for HTLC pattern
            for idx, output in enumerate(tx_data.get("vout", [])):
                if htlc_script := self._detect_htlc_script(output):
                    await self._handle_htlc_detection(txid, idx, output, htlc_script)

            # Check if this spends any watched HTLCs
            for input_data in tx_data.get("vin", []):
                if spent_txid := input_data.get("txid"):
                    if spent_txid in self._pending_htlcs:
                        await self._handle_htlc_spend(txid, spent_txid, input_data)

        except Exception as e:
            logger.error("Error processing transaction", txid=txid, error=str(e))

    async def _get_transaction(self, txid: str) -> dict[str, Any] | None:
        """Fetch transaction data from Mempool API."""
        try:
            url = f"{config.mempool_api_url}/tx/{txid}"
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Failed to fetch transaction", txid=txid, error=str(e))
            return None

    def _detect_htlc_script(self, output: dict[str, Any]) -> HTLCScript | None:
        """Detect if an output contains a COMIT HTLC script."""
        script_hex = output.get("scriptPubKey", {}).get("hex", "")
        if not script_hex:
            return None

        script_bytes = bytes.fromhex(script_hex)

        # Try primary pattern first
        match = self.HTLC_PATTERN.match(script_bytes)
        if not match:
            # Try alternative pattern
            match = self.HTLC_PATTERN_ALT.match(script_bytes)

        if match:
            secret_hash = match.group(1).hex()
            recipient_pubkey_hash = match.group(2).hex()
            timelock_bytes = match.group(3)
            sender_pubkey_hash = match.group(4).hex()

            # Decode timelock (little-endian, handle variable length)
            try:
                timelock = int.from_bytes(timelock_bytes, byteorder="little")

                # Validate timelock is reasonable (not too far in future)
                if timelock > 2147483647:  # Max valid timestamp
                    logger.debug("Invalid timelock detected", timelock=timelock)
                    return None

            except Exception as e:
                logger.debug("Failed to decode timelock", error=str(e))
                return None

            return HTLCScript(
                secret_hash=secret_hash,
                recipient_pubkey_hash=recipient_pubkey_hash,
                sender_pubkey_hash=sender_pubkey_hash,
                timelock_height=timelock,
            )
        return None

    async def _handle_htlc_detection(
        self,
        txid: str,
        output_idx: int,
        output: dict[str, Any],
        htlc_script: HTLCScript,
    ):
        """Handle detection of a new HTLC."""
        amount_sats = int(output["value"] * COIN)

        htlc_tx = HTLCTransaction(
            txid=txid,
            version=2,  # Will be updated with full tx data
            locktime=0,
            size=0,
            weight=0,
            htlc_type=HTLCType.LOCK,
            htlc_script=htlc_script,
            amount_sats=amount_sats,
            output_index=output_idx,
            block_height=None,
            confirmations=0,
        )

        # Store in pending HTLCs
        self._pending_htlcs[txid] = htlc_tx

        # Create swap record
        swap = AtomicSwap(
            swap_id=f"{txid}:{output_idx}",
            lock_tx=htlc_tx,
            state=SwapState.LOCKED,
            amount_btc=Decimal(amount_sats) / COIN,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        await self.db.save_swap(swap)
        logger.info(
            "Detected new HTLC", swap_id=swap.swap_id, amount_btc=swap.amount_btc
        )

    async def _handle_htlc_spend(
        self, spending_txid: str, spent_txid: str, input_data: dict[str, Any]
    ):
        """Handle spending of an HTLC (redeem or refund)."""
        htlc = self._pending_htlcs.get(spent_txid)
        if not htlc:
            return

        # Determine if this is a redeem or refund
        witness = input_data.get("witness", [])
        if len(witness) >= 2:
            # Check if there's a secret in the witness
            if len(witness[1]) == 64:  # 32-byte secret in hex
                htlc_type = HTLCType.REDEEM
                secret = witness[1]
            else:
                htlc_type = HTLCType.REFUND
                secret = None
        else:
            htlc_type = HTLCType.REFUND
            secret = None

        # Update swap record
        swap = await self.db.get_swap_by_lock_txid(spent_txid)
        if swap:
            if htlc_type == HTLCType.REDEEM:
                swap.state = SwapState.REDEEMED
                swap.redeem_tx = HTLCTransaction(
                    txid=spending_txid,
                    version=2,
                    locktime=0,
                    size=0,
                    weight=0,
                    htlc_type=HTLCType.REDEEM,
                    amount_sats=htlc.amount_sats,
                    output_index=0,
                    secret=secret,
                )
            else:
                swap.state = SwapState.REFUNDED
                swap.refund_tx = HTLCTransaction(
                    txid=spending_txid,
                    version=2,
                    locktime=0,
                    size=0,
                    weight=0,
                    htlc_type=HTLCType.REFUND,
                    amount_sats=htlc.amount_sats,
                    output_index=0,
                )

            swap.updated_at = datetime.now(timezone.utc)
            await self.db.save_swap(swap)

            logger.info(
                "HTLC spent",
                swap_id=swap.swap_id,
                spend_type=htlc_type.value,
                spending_tx=spending_txid,
            )

        # Remove from pending
        del self._pending_htlcs[spent_txid]

    async def check_transaction(self, txid: str) -> AtomicSwap | None:
        """Check if a specific transaction is part of an atomic swap."""
        await self._process_transaction(txid)
        return await self.db.get_swap_by_lock_txid(txid)

    async def backfill(self, start_height: int, end_height: int):
        """Backfill historical swaps between block heights."""
        logger.info(
            "Starting backfill", start_height=start_height, end_height=end_height
        )

        for height in range(start_height, end_height + 1):
            try:
                # Get block hash
                url = f"{config.mempool_api_url}/block-height/{height}"
                response = await self.client.get(url)
                block_hash = response.text.strip()

                # Get block transactions
                url = f"{config.mempool_api_url}/block/{block_hash}/txids"
                response = await self.client.get(url)
                txids = response.json()

                # Process each transaction
                for txid in txids:
                    await self._process_transaction(txid)
                    await asyncio.sleep(0.1)  # Rate limiting

                logger.info("Processed block", height=height, tx_count=len(txids))

            except Exception as e:
                logger.error("Error processing block", height=height, error=str(e))

        logger.info("Backfill complete")
