import logging
from telethon import TelegramClient, events
from src.parser import parse_message
from src import db

logger = logging.getLogger(__name__)


async def process_message(db_path: str, message) -> None:
    """Process a single Telegram message: save raw, parse, save transaction."""
    text = message.text
    if not text:
        return

    msg_id = message.id
    chat_id = message.chat_id

    try:
        # Skip if already processed (handles re-runs gracefully)
        if db.is_message_processed(db_path, msg_id, chat_id):
            return

        # Try to parse as a transaction
        parsed = parse_message(text)

        # Convert amounts to tiyin (integer) before saving
        transaction_data = None
        if parsed:
            transaction_data = dict(parsed)
            transaction_data["amount"] = int(round(transaction_data["amount"] * 100))
            if transaction_data.get("balance") is not None:
                transaction_data["balance"] = int(round(transaction_data["balance"] * 100))

        # Atomically save raw message and transaction together
        db.save_message_and_transaction(
            db_path, text, telegram_message_id=msg_id,
            chat_id=chat_id, transaction_data=transaction_data,
        )

        if parsed:
            logger.info(
                "[txn] %s | %s %.2f %s | card %s | %s",
                parsed["type"].upper(),
                "+" if parsed["type"] == "credit" else "-",
                parsed["amount"],
                parsed["currency"],
                parsed["card"] or "n/a",
                parsed["timestamp"],
            )
        else:
            logger.info("[skip] Message #%d is not a known transaction format, saved to raw_messages only", msg_id)
    except Exception:
        logger.exception("Failed to process message #%d, skipping", msg_id)


async def fetch_history(client: TelegramClient, db_path: str, bot_username: str) -> int:
    """
    Fetch all historical messages from the bot chat.
    Returns the number of messages processed.
    """
    logger.info("Fetching historical messages from @%s ...", bot_username)

    entity = await client.get_entity(bot_username)
    chat_id = entity.id

    # Use high-water-mark so subsequent runs only fetch new messages
    last_id = db.get_last_message_id(db_path, chat_id)
    iter_kwargs = {"entity": entity, "reverse": True}
    if last_id is not None:
        iter_kwargs["min_id"] = last_id
        logger.info("Resuming from message id %d", last_id)

    count = 0

    async for message in client.iter_messages(**iter_kwargs):
        await process_message(db_path, message)
        count += 1
        if count % 100 == 0:
            logger.info("  ... processed %d historical messages so far", count)

    logger.info("History complete: %d messages processed", count)
    return count


async def start_listener(client: TelegramClient, db_path: str, bot_username: str) -> None:
    """
    Register a handler for new incoming messages from the bot chat,
    then run the client until disconnected.
    """
    entity = await client.get_entity(bot_username)
    chat_id = entity.id

    @client.on(events.NewMessage(chats=chat_id))
    async def on_new_message(event):
        logger.info("New message received from @%s", bot_username)
        await process_message(db_path, event.message)

    logger.info("Listening for new messages from @%s (chat_id=%d) ...", bot_username, chat_id)
    logger.info("Press Ctrl+C to stop.")

    await client.run_until_disconnected()
