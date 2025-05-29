"""COMIT Swap Bot - Detecting BTC⇆XMR atomic swaps."""

__version__ = "1.0.0"
__author__ = "JPShag"
__email__ = "jpshag@example.com"

from .notifiers import AppriseNotifier, TwitterNotifier
from .price_fetcher import PriceFetcher
from .swap_watcher import SwapWatcher

__all__ = ["SwapWatcher", "TwitterNotifier", "AppriseNotifier", "PriceFetcher"]
