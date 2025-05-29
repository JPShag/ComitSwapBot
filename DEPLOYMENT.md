# Deployment Guide

This guide covers various deployment options for the COMIT Swap Bot.

## Prerequisites

- Twitter Developer Account with API credentials
- (Optional) CoinGecko API key for higher rate limits
- Docker and Docker Compose (for containerized deployment)
- Python 3.12+ (for direct deployment)

## Configuration

### Environment Variables

Create a `.env` file with your configuration:

```bash
# Twitter API (Required)
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret

# Optional
COINGECKO_API_KEY=your_coingecko_key
LOG_LEVEL=INFO

# Use Mempool.space API (recommended)
USE_MEMPOOL_API=true