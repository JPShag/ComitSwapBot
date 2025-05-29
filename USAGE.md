# 🔄 COMIT Atomic Swap Twitter Bot

A sophisticated bot that monitors the Bitcoin network for COMIT-style atomic swaps and automatically posts detailed tweets about detected transactions.

## ✨ Features

- **🎯 Real-time Detection**: Monitors Bitcoin network for COMIT atomic swap transactions
- **📊 Price Integration**: Calculates XMR equivalents using live CoinGecko rates
- **🐦 Twitter Integration**: Automatically posts tweets with transaction details
- **📱 Multi-platform Notifications**: Supports Discord, Slack, and other platforms via Apprise
- **🗄️ Data Persistence**: SQLite database for tracking swap history and states
- **🔄 State Tracking**: Monitors full swap lifecycle (lock → redeem/refund)
- **⚡ Object-Oriented Design**: Easily adaptable for Bitcoin forks

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -e .
```

### 2. Setup Twitter API Credentials

Run the setup script to configure Twitter API access:

```bash
python setup_and_test.py
```

You'll need:
- Twitter API Key
- Twitter API Secret  
- Twitter Access Token
- Twitter Access Token Secret

Get these from [Twitter Developer Portal](https://developer.twitter.com/).

### 3. Test the Bot

#### Option A: Demo Mode (Immediate Test)
```bash
python demo_bot.py
# Choose option 1 for demo mode
```

#### Option B: Manual Test
```bash
python test_twitter_post.py
```

### 4. Run in Production

```bash
# Watch for real atomic swaps
python -m comit_swap_bot watch

# Or use the demo runner in real mode
python demo_bot.py
# Choose option 2 for real mode
```

## 📋 Tweet Format

The bot posts tweets in this format:

```
🔄 New BTC⇆XMR Atomic Swap!

📦 TX: a1b2c3d4e5f67890...
💰 Amount: 0.15000000 BTC
   ≈ 5.7750 XMR
📊 Rate: 1 BTC = 38.5000 XMR
💱 Price data by CoinGecko
🕐 2025-05-29 12:00:00 UTC

#AtomicSwap #Bitcoin #Monero
```

## 🏗️ Architecture

### Core Components

- **SwapWatcher**: Monitors Bitcoin network via multiple APIs
- **PriceFetcher**: Gets BTC/XMR rates from CoinGecko with caching
- **NotificationManager**: Handles Twitter and multi-platform notifications
- **SwapDatabase**: SQLite persistence for swap tracking
- **SwapOrchestrator**: Coordinates all components

### Models

- **AtomicSwap**: Complete swap representation with lifecycle state
- **HTLCTransaction**: Bitcoin transaction with HTLC script details
- **HTLCScript**: Parsed COMIT script components

## 🔧 Configuration

### Environment Variables

```bash
# Twitter API (required)
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret

# Optional settings
COINGECKO_API_KEY=your_coingecko_key  # For higher rate limits
LOG_LEVEL=INFO                        # DEBUG, INFO, WARNING, ERROR
CHECK_INTERVAL=10                     # Seconds between checks
```

### Configuration File

Create `config.toml` to override defaults:

```toml
[bitcoin]
network = "mainnet"
api_endpoints = [
    "https://blockstream.info/api",
    "https://mempool.space/api"
]

[notifications]
enable_twitter = true
enable_apprise = false
apprise_urls = [
    "discord://webhook_id/webhook_token",
    "slack://token_a/token_b/token_c"
]

[database]
url = "sqlite+aiosqlite:///swaps.db"
```

## 🧪 Testing

### Run Tests
```bash
pytest tests/ -v
```

### Test Individual Components
```bash
# Test swap detection
python -m comit_swap_bot check --txid <transaction_id>

# Test notifications
python test_twitter_post.py

# Run specific test
pytest tests/test_notifiers.py::TestTwitterNotifier::test_tweet_success -v
```

## 📊 Database Schema

The bot stores swap data in SQLite:

```sql
CREATE TABLE atomic_swaps (
    swap_id TEXT PRIMARY KEY,
    lock_txid TEXT NOT NULL,
    redeem_txid TEXT,
    refund_txid TEXT,
    current_state TEXT NOT NULL,
    btc_amount DECIMAL(16,8) NOT NULL,
    xmr_amount DECIMAL(16,8),
    btc_xmr_rate DECIMAL(16,8),
    detected_at DATETIME NOT NULL,
    last_updated DATETIME NOT NULL,
    notification_sent TEXT,
    full_swap_json TEXT NOT NULL
);
```

## 🔍 HTLC Detection

The bot identifies COMIT atomic swaps by detecting this script pattern:

```
OP_IF
    OP_SHA256 <32-byte hash> OP_EQUALVERIFY
    OP_DUP OP_HASH160 <20-byte recipient hash> OP_EQUALVERIFY
OP_ELSE
    <4-byte timelock> OP_CHECKLOCKTIMEVERIFY OP_DROP
    OP_DUP OP_HASH160 <20-byte sender hash> OP_EQUALVERIFY
OP_ENDIF
OP_CHECKSIG
```

## 🌐 Multi-Platform Support

### Apprise Integration

Enable notifications to multiple platforms:

```python
# Discord
discord://webhook_id/webhook_token

# Slack  
slack://token_a/token_b/token_c

# Telegram
tgram://bot_token/chat_id

# Email
mailto://user:pass@gmail.com
```

## 🚨 Error Handling

The bot includes robust error handling:

- **API Failures**: Automatic retry with exponential backoff
- **Rate Limiting**: Respects API limits with intelligent queuing
- **Network Issues**: Graceful degradation and reconnection
- **Data Validation**: Comprehensive input validation

## 📈 Performance

- **Caching**: Price data cached for 5 minutes
- **Async Operations**: Non-blocking I/O for all network calls
- **Database Connection Pooling**: Efficient SQLite access
- **Memory Management**: Automatic cleanup of old data

## 🔒 Security

- **API Key Management**: Secure credential storage
- **Input Validation**: Protection against malicious data
- **Rate Limiting**: Prevents API abuse
- **Error Logging**: No sensitive data in logs

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

### Development Setup

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run linting
ruff check .
ruff format .

# Run type checking
mypy comit_swap_bot

# Run tests with coverage
pytest --cov=comit_swap_bot tests/
```

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Attribution

- **CoinGecko**: Price data (automatically attributed in tweets)
- **Blockstream/Mempool**: Bitcoin API data
- **COMIT Network**: Atomic swap protocol specification

## 🐛 Troubleshooting

### Common Issues

**Twitter API Errors**:
- Verify credentials are correct
- Check if your app has write permissions
- Ensure you're using API v2 endpoints

**No Swaps Detected**:
- Atomic swaps are rare - be patient
- Use demo mode for immediate testing
- Check API connectivity

**Database Errors**:
- Ensure write permissions in bot directory
- Check disk space availability

### Debug Mode

Enable detailed logging:

```bash
export LOG_LEVEL=DEBUG
python -m comit_swap_bot watch
```

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/user/comit-swap-bot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/user/comit-swap-bot/discussions)
- **Twitter**: [@comit_swap_bot](https://twitter.com/comit_swap_bot)

---

Made with ❤️ for the Bitcoin and Monero communities
