"""COMIT Swap Bot - Detecting BTC⇆XMR atomic swaps."""

__version__ = "1.0.0"
__author__ = "JPShag"
__email__ = "jpshag@example.com"

from .swap_watcher import SwapWatcher
from .notifiers import TwitterNotifier, AppriseNotifier
from .price_fetcher import PriceFetcher

__all__ = ["SwapWatcher", "TwitterNotifier", "AppriseNotifier", "PriceFetcher"]