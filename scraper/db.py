import sqlite3
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tiyin helpers  (1 UZS = 100 tiyin)
# ---------------------------------------------------------------------------

def to_tiyin(amount_float):
    """Convert a float amount to integer tiyin (cents). E.g. 150.50 -> 15050."""
    return int(round(amount_float * 100))


def from_tiyin(amount_int):
    """Convert integer tiyin back to a float amount. E.g. 15050 -> 150.50."""
    return amount_int / 100.0


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def get_connection(db_path):
    """Create and return a database connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

def init_db(db_path):
    """Create tables if they don't exist."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_text TEXT NOT NULL,
                telegram_message_id INTEGER,
                chat_id INTEGER,
                received_at TEXT DEFAULT (datetime('now'))
            )
        """)

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uix_raw_messages_tg
            ON raw_messages(telegram_message_id, chat_id)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                description TEXT NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL,
                card TEXT,
                merchant TEXT,
                timestamp TEXT NOT NULL,
                balance INTEGER,
                raw_message TEXT NOT NULL,
                raw_message_id INTEGER REFERENCES raw_messages(id),
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        conn.commit()
    finally:
        conn.close()
    logger.info("Database initialized at %s", db_path)


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------

def save_raw_message(db_path, message_text, telegram_message_id=None, chat_id=None):
    """Save a raw message and return its row id."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO raw_messages (message_text, telegram_message_id, chat_id) VALUES (?, ?, ?)",
            (message_text, telegram_message_id, chat_id),
        )
        row_id = cursor.lastrowid
        conn.commit()
        return row_id
    finally:
        conn.close()


def save_transaction(db_path, data, raw_message_id=None):
    """Save a parsed transaction and return its row id.

    ``amount`` and ``balance`` in *data* are expected as float values and
    will be converted to integer tiyin before storage.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO transactions
               (type, description, amount, currency, card, merchant,
                timestamp, balance, raw_message, raw_message_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["type"],
                data["description"],
                to_tiyin(data["amount"]),
                data["currency"],
                data.get("card"),
                data.get("merchant"),
                data["timestamp"],
                to_tiyin(data["balance"]) if data.get("balance") is not None else None,
                data["raw_message"],
                raw_message_id,
            ),
        )
        row_id = cursor.lastrowid
        conn.commit()
        return row_id
    finally:
        conn.close()


def save_message_and_transaction(db_path, message_text, telegram_message_id, chat_id, transaction_data):
    """Atomically save a raw message and its parsed transaction.

    Both rows are written inside a single SQLite transaction.  If either
    INSERT fails the entire operation is rolled back so the database never
    contains a raw_message without its matching transaction or vice-versa.

    Returns a tuple ``(raw_message_id, transaction_id)``.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO raw_messages (message_text, telegram_message_id, chat_id) VALUES (?, ?, ?)",
            (message_text, telegram_message_id, chat_id),
        )
        raw_message_id = cursor.lastrowid

        if transaction_data is None:
            conn.commit()
            return raw_message_id, None

        cursor.execute(
            """INSERT INTO transactions
               (type, description, amount, currency, card, merchant,
                timestamp, balance, raw_message, raw_message_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                transaction_data["type"],
                transaction_data["description"],
                transaction_data["amount"],
                transaction_data["currency"],
                transaction_data.get("card"),
                transaction_data.get("merchant"),
                transaction_data["timestamp"],
                transaction_data.get("balance"),
                transaction_data["raw_message"],
                raw_message_id,
            ),
        )
        transaction_id = cursor.lastrowid

        conn.commit()
        return raw_message_id, transaction_id
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def is_message_processed(db_path, telegram_message_id, chat_id):
    """Check if a message has already been saved (avoid duplicates on re-run)."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM raw_messages WHERE telegram_message_id = ? AND chat_id = ?",
            (telegram_message_id, chat_id),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def get_transactions(db_path, limit=50):
    """Return recent transactions as a list of dicts."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM transactions ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_last_message_id(db_path, chat_id):
    """Return the highest telegram_message_id for *chat_id*, or None.

    This serves as a high-water mark so the fetcher can skip messages
    that have already been stored.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT MAX(telegram_message_id) FROM raw_messages WHERE chat_id = ?",
            (chat_id,),
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()
