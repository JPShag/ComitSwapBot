"""
Attribution utilities for third-party data sources.

This module handles proper attribution for APIs we use, ensuring
compliance with their terms of service.
"""

from .config import config


class AttributionManager:
    """
    Manages attribution requirements for external data sources.
    
    Ensures we properly credit data providers like CoinGecko to maintain
    compliance with their API terms and keep access to free data.
    """
    
    @staticmethod
    def get_coingecko_attribution() -> dict:
        """
        Get CoinGecko attribution information.
        
        Returns:
            dict: Attribution text and link information
        """
        return {
            "text": config.coingecko_attribution_text,
            "url": config.coingecko_attribution_url,
            "logo_required": True,
            "placement": "near_price_data"
        }
    
    @staticmethod
    def format_attribution_for_twitter() -> str:
        """
        Format attribution text for Twitter posts.
        
        Returns:
            str: Compact attribution text suitable for tweets
        """
        return f"💱 {config.coingecko_attribution_text}"
    
    @staticmethod
    def format_attribution_for_discord() -> str:
        """
        Format attribution text for Discord messages.
        
        Returns:
            str: Attribution with clickable link for Discord
        """
        return f"💱 [{config.coingecko_attribution_text}]({config.coingecko_attribution_url})"
    
    @staticmethod
    def get_utm_tracking_url(source_name: str = "comit-swap-bot") -> str:
        """
        Generate UTM-tracked attribution URL.
        
        Args:
            source_name: Name of the project for UTM tracking
            
        Returns:
            str: CoinGecko URL with proper UTM parameters
        """
        base_url = "https://www.coingecko.com"
        return f"{base_url}?utm_source={source_name}&utm_medium=referral"


# Convenience instance
attribution = AttributionManager()
