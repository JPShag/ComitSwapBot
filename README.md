# COMIT Swap Bot 🤖

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/JPShag/comit-swap-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/JPShag/comit-swap-bot/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-85%25-green.svg)]()

A Twitter bot that detects and tweets COMIT BTC⇆XMR atomic swaps in real-time.

## Features

- 🔍 Detects HTLC patterns specific to COMIT atomic swaps
- 📊 Real-time BTC to XMR conversion using market rates
- 🐦 Automatic tweeting of swap transactions
- 🔌 Extensible notification system (Twitter, Apprise)
- 🏗️ Object-oriented design for chain-agnostic support
- 🚀 Docker support for easy deployment

## Installation

### Using Docker (Recommended)

```bash
docker pull ghcr.io/jpshag/comit-swap-bot:latest
docker run -d --name comit-bot \
  -e TWITTER_API_KEY=your_key \
  -e TWITTER_API_SECRET=your_secret \
  -e TWITTER_ACCESS_TOKEN=your_token \
  -e TWITTER_ACCESS_TOKEN_SECRET=your_token_secret \
  ghcr.io/jpshag/comit-swap-bot:latest