from __future__ import annotations

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def parse_message(text: str) -> Optional[dict]:
    """
    Parse a CardXabarBot transaction message into structured data.

    Returns a dict with keys:
        type, description, amount, currency, card, merchant, timestamp, balance, raw_message

    Returns None if the message doesn't match the expected format.
    """
    if not text or not isinstance(text, str):
        return None

    text = text.replace('\ufe0f', '').replace('\ufe0e', '')

    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]

    # We need at least the type/description line and amount line
    if len(lines) < 2:
        return None

    # --- Line 1: Type + Description ---
    # Debit:  \U0001f534 Spisanie c karty
    # Credit: \U0001f7e2 Perevod na kartu
    first_line = lines[0]

    if first_line.startswith("\U0001f534"):  # red circle
        txn_type = "debit"
    elif first_line.startswith("\U0001f7e2"):  # green circle
        txn_type = "credit"
    else:
        logger.debug("Unknown message format (no type emoji): %s", first_line[:50])
        return None

    # Description is everything after the emoji (strip the emoji + space)
    description = re.sub(r"^[\U0001f534\U0001f7e2]\s*", "", first_line).strip()
    if not description:
        return None

    # --- Line 2: Amount ---
    # Debit:  \u2796 1 005.00 UZS
    # Credit: \u2795 1 000.00 UZS
    amount_line = lines[1] if len(lines) > 1 else ""
    amount_match = re.match(r"^[\u2795\u2796➕➖]\s*([\d\s]+\.?\d*)\s+(\S+)$", amount_line)
    if not amount_match:
        logger.debug("Could not parse amount line: %s", amount_line[:50])
        return None

    amount_str = amount_match.group(1).replace(" ", "")
    currency = amount_match.group(2)

    try:
        amount = float(amount_str)
    except ValueError:
        logger.debug("Invalid amount value: %s", amount_str)
        return None

    # --- Line 3: Card (optional) ---
    card = None
    card_line = _find_line(lines, "\U0001f4b3")  # credit card emoji
    if card_line:
        card_match = re.search(r"\*{2,3}\d+", card_line)
        if card_match:
            card = card_match.group(0)

    # --- Line 4: Merchant (optional) ---
    merchant = None
    merchant_line = _find_line(lines, "\U0001f4cd")  # pin emoji
    if merchant_line:
        merchant = re.sub(r"^[\U0001f4cd]\s*", "", merchant_line).strip()

    # --- Line 5: Timestamp ---
    timestamp = None
    time_line = _find_line(lines, "\U0001f553")  # clock emoji
    if time_line:
        timestamp = re.sub(r"^[\U0001f553]\s*", "", time_line).strip()

    if not timestamp:
        logger.debug("Could not find timestamp in message")
        return None

    ts_match = re.match(r"(\d{2})\.(\d{2})\.(\d{2})\s+(\d{2}:\d{2})$", timestamp)
    if ts_match:
        timestamp = "20{}-{}-{} {}".format(ts_match.group(3), ts_match.group(2), ts_match.group(1), ts_match.group(4))

    # --- Line 6: Balance (optional) ---
    balance = None
    balance_line = _find_line(lines, "\U0001f4b5")  # dollar bill emoji
    if balance_line:
        balance_match = re.search(r"([\d\s]+\.?\d*)\s+\S+", re.sub(r"^[\U0001f4b5]\s*", "", balance_line))
        if balance_match:
            balance_str = balance_match.group(1).replace(" ", "")
            try:
                balance = float(balance_str)
            except ValueError:
                pass

    return {
        "type": txn_type,
        "description": description,
        "amount": amount,
        "currency": currency,
        "card": card,
        "merchant": merchant,
        "timestamp": timestamp,
        "balance": balance,
        "raw_message": text,
    }


def _find_line(lines: list, prefix: str) -> Optional[str]:
    """Find the first line that starts with the given emoji prefix."""
    for line in lines:
        if line.startswith(prefix):
            return line
    return None
