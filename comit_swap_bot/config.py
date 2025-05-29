"""Configuration management for the swap bot."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator


class Config(BaseSettings):
    """Application configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Bitcoin Configuration
    bitcoin_rpc_url: str = Field(
        default="http://localhost:8332",
        description="Bitcoin RPC URL"
    )
    bitcoin_rpc_user: Optional[str] = Field(
        default=None,
        description="Bitcoin RPC username"
    )
    bitcoin_rpc_pass: Optional[str] = Field(
        default=None,
        description="Bitcoin RPC password"
    )
    
    # Mempool API Configuration
    use_mempool_api: bool = Field(
        default=True,
        description="Use Mempool.space API instead of Bitcoin RPC"
    )
    mempool_api_url: str = Field(
        default="https://mempool.space/api",
        description="Mempool.space API URL"
    )
    mempool_ws_url: str = Field(
        default="wss://mempool.space/api/v1/ws",
        description="Mempool.space WebSocket URL"
    )
    
    # Twitter Configuration
    twitter_api_key: Optional[str] = Field(
        default=None,
        description="Twitter API Key"
    )
    twitter_api_secret: Optional[str] = Field(
        default=None,
        description="Twitter API Secret"
    )
    twitter_access_token: Optional[str] = Field(
        default=None,
        description="Twitter Access Token"
    )
    twitter_access_token_secret: Optional[str] = Field(
        default=None,
        description="Twitter Access Token Secret"
    )
    
    # CoinGecko Configuration
    coingecko_api_key: Optional[str] = Field(
        default=None,
        description="CoinGecko API Key (optional, for higher rate limits)"
    )
    coingecko_api_url: str = Field(
        default="https://api.coingecko.com/api/v3",
        description="CoinGecko API URL"
    )
    
    # Database Configuration
    database_url: str = Field(
        default="sqlite+aiosqlite:///swaps.db",
        description="Database URL for storing swap history"
    )
    
    # Application Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    check_interval: int = Field(
        default=10,
        description="Interval in seconds between checks"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retries for failed operations"
    )
    
    # Notification Configuration
    enable_twitter: bool = Field(
        default=True,
        description="Enable Twitter notifications"
    )
    enable_apprise: bool = Field(
        default=False,
        description="Enable Apprise notifications"
    )
    apprise_urls: list[str] = Field(
        default_factory=list,
        description="List of Apprise notification URLs"
    )
    
    @validator("twitter_api_key", "twitter_api_secret", 
               "twitter_access_token", "twitter_access_token_secret")
    def validate_twitter_config(cls, v, values):
        """Validate Twitter configuration."""
        if values.get("enable_twitter") and not v:
            raise ValueError("Twitter credentials required when Twitter is enabled")
        return v


# Global config instance
config = Config()