#!/usr/bin/env python3
"""
Setup script for Twitter API credentials and testing the bot.

This script helps you:
1. Set up Twitter API credentials
2. Test the bot's Twitter posting functionality
3. Run a complete end-to-end test
"""

import os
import sys


def _get_credential_specs():
    """Get Twitter credential specifications."""
    return [
        ("TWITTER_API_KEY", os.getenv("TWITTER_API_KEY")),
        ("TWITTER_API_SECRET", os.getenv("TWITTER_API_SECRET")),
        ("TWITTER_ACCESS_TOKEN", os.getenv("TWITTER_ACCESS_TOKEN")),
        ("TWITTER_ACCESS_TOKEN_SECRET", os.getenv("TWITTER_ACCESS_TOKEN_SECRET")),
    ]


def _check_existing_credentials():
    """Check if credentials are already configured."""
    existing_creds = _get_credential_specs()
    has_all_creds = all(cred[1] for cred in existing_creds)

    if has_all_creds:
        print("✅ Twitter credentials already configured!")
        for name, value in existing_creds:
            masked_value = value[:8] + "..." if value else "Not set"
            print(f"   {name}: {masked_value}")

        choice = input("\n🤔 Reconfigure credentials? [y/N]: ").strip().lower()
        return choice != 'y'
    return False


def _collect_credentials():
    """Collect credentials from user input."""
    existing_creds = _get_credential_specs()
    credentials = {}

    for name, _ in existing_creds:
        current_value = os.getenv(name, "")
        if current_value:
            print(f"{name}: {'*' * 20} (already set)")
            update = input(f"Update {name}? [y/N]: ").strip().lower()
            if update != 'y':
                credentials[name] = current_value
                continue

        while True:
            value = input(f"{name}: ").strip()
            if value:
                credentials[name] = value
                break
            print("❌ This field is required!")

    return credentials


def _save_credentials(credentials):
    """Save credentials to .env file and environment."""
    with open(".env", "w") as f:
        f.write("# Twitter API Credentials\n")
        for name, value in credentials.items():
            f.write(f"{name}={value}\n")

    # Set environment variables for current session
    for name, value in credentials.items():
        os.environ[name] = value


def setup_twitter_credentials():
    """Interactive setup for Twitter API credentials."""
    print("🐦 Twitter API Setup")
    print("=" * 30)
    print()
    print("You'll need a Twitter Developer account and app to get these credentials.")
    print("Visit: https://developer.twitter.com/en/portal/dashboard")
    print()

    # Check if credentials are already configured
    if _check_existing_credentials():
        return True

    print("\n📝 Please enter your Twitter API credentials:")
    print("(You can find these in your Twitter Developer portal)")
    print()

    # Collect new credentials
    credentials = _collect_credentials()

    # Save credentials
    _save_credentials(credentials)

    print("\n✅ Credentials saved to .env file!")
    print("💡 Tip: Load these in your shell with: source .env")

    return True


def run_twitter_test():
    """Run the Twitter posting test."""
    print("\n🧪 Running Twitter Test")
    print("=" * 25)

    # Check if credentials are available
    required_vars = [
        "TWITTER_API_KEY",
        "TWITTER_API_SECRET",
        "TWITTER_ACCESS_TOKEN",
        "TWITTER_ACCESS_TOKEN_SECRET"
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"❌ Missing credentials: {', '.join(missing_vars)}")
        return False

    # Load .env file if it exists
    if os.path.exists(".env"):
        print("📂 Loading credentials from .env file...")
        with open(".env") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value

    print("🚀 Starting Twitter test...")

    # Run the test script
    import subprocess
    result = subprocess.run([sys.executable, "test_twitter_post.py"],
                          capture_output=False, text=True)

    return result.returncode == 0


def main():
    """Main setup and test function."""
    print("🔄 COMIT Atomic Swap Bot - Setup & Test")
    print("=" * 45)

    try:
        # Step 1: Setup Twitter credentials
        if not setup_twitter_credentials():
            print("❌ Failed to setup Twitter credentials")
            return

        # Step 2: Run Twitter test
        print("\n" + "="*45)
        success = run_twitter_test()

        if success:
            print("\n🎉 All tests completed successfully!")
            print("✅ Your bot is ready to detect and tweet about atomic swaps!")
        else:
            print("\n❌ Test failed. Please check your credentials and try again.")

    except KeyboardInterrupt:
        print("\n\n👋 Setup cancelled by user.")
    except Exception as e:
        print(f"\n💥 Error during setup: {e}")


if __name__ == "__main__":
    main()
