from setuptools import find_packages, setup

setup(
    name="comit_swap_bot",
    version="0.1.0",
    description="COMIT BTC⇆XMR atomic swap monitoring bot",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "structlog>=23.0.0",
        "httpx>=0.24.0",
        "websockets>=11.0.0",
        "tweepy>=4.14.0",
        "apprise>=1.4.0",
        "aiohttp>=3.8.0",
        "cachetools>=5.3.0",
        "python-bitcoinlib>=0.12.0",
        "aiosqlite>=0.19.0",
        "sqlalchemy>=2.0.0",
        "click>=8.1.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",  # ← added
        "python-dotenv>=1.0.0",
        "pytest>=7.4.0",
        "pytest-asyncio>=0.21.0",
        "pytest-mock>=3.11.0",
    ],
)
