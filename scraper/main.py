import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient

from scraper import db
from scraper.listener import fetch_history, start_listener

SCRAPER_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("finance")

# Silence noisy Telethon internals
logging.getLogger("telethon").setLevel(logging.WARNING)


def main() -> None:
    # Load environment variables from scraper/.env
    load_dotenv(SCRAPER_DIR / ".env")

    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    phone = os.getenv("TELEGRAM_PHONE")
    bot_username = os.getenv("BOT_USERNAME", "CardXabarBot")
    db_path = os.getenv("DB_PATH", "finance.db")

    # Validate required config
    missing = []
    if not api_id:
        missing.append("TELEGRAM_API_ID")
    if not api_hash:
        missing.append("TELEGRAM_API_HASH")
    if not phone:
        missing.append("TELEGRAM_PHONE")

    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        logger.error("Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)

    # Initialize database
    db.init_db(db_path)
    logger.info("Database ready at %s", db_path)

    async def run():
        # Create Telethon client inside async context to avoid event loop mismatch
        session_path = str(SCRAPER_DIR / "finance_session")
        client = TelegramClient(session_path, int(api_id), api_hash)
        async with client:
            await client.start(phone=phone)
            logger.info("Telegram client connected successfully")

            # Fetch all historical messages first
            await fetch_history(client, db_path, bot_username)

            # Then listen for new messages
            await start_listener(client, db_path, bot_username)

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")


if __name__ == "__main__":
    main()
