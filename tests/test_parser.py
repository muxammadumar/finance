from src.parser import parse_message


DEBIT_MESSAGE = (
    "\U0001f534 Spisanie c karty\n"
    "\u2796 1 005.00 UZS\n"
    "\U0001f4b3 ***7947\n"
    "\U0001f4cd XAZNA P2P UZCARD XB UZCARD OTHER, UZ\n"
    "\U0001f553 23.05.26 02:45\n"
    "\U0001f4b5 2 731 085.78 UZS"
)

CREDIT_MESSAGE = (
    "\U0001f7e2 Perevod na kartu\n"
    "\u2795 1 000.00 UZS\n"
    "\U0001f4b3 ***5056\n"
    "\U0001f4cd XAZNA P2P UZCARD XB UZCARD OTHER, UZ\n"
    "\U0001f553 23.05.26 02:45\n"
    "\U0001f4b5 13 545.11 UZS"
)


class TestDebitMessage:
    def test_type(self):
        result = parse_message(DEBIT_MESSAGE)
        assert result["type"] == "debit"

    def test_description(self):
        result = parse_message(DEBIT_MESSAGE)
        assert result["description"] == "Spisanie c karty"

    def test_amount(self):
        result = parse_message(DEBIT_MESSAGE)
        assert result["amount"] == 1005.00

    def test_currency(self):
        result = parse_message(DEBIT_MESSAGE)
        assert result["currency"] == "UZS"

    def test_card(self):
        result = parse_message(DEBIT_MESSAGE)
        assert result["card"] == "***7947"

    def test_merchant(self):
        result = parse_message(DEBIT_MESSAGE)
        assert result["merchant"] == "XAZNA P2P UZCARD XB UZCARD OTHER, UZ"

    def test_timestamp(self):
        result = parse_message(DEBIT_MESSAGE)
        assert result["timestamp"] == "2026-05-23 02:45"

    def test_balance(self):
        result = parse_message(DEBIT_MESSAGE)
        assert result["balance"] == 2731085.78

    def test_raw_message_preserved(self):
        result = parse_message(DEBIT_MESSAGE)
        assert result["raw_message"] == DEBIT_MESSAGE


class TestCreditMessage:
    def test_type(self):
        result = parse_message(CREDIT_MESSAGE)
        assert result["type"] == "credit"

    def test_description(self):
        result = parse_message(CREDIT_MESSAGE)
        assert result["description"] == "Perevod na kartu"

    def test_amount(self):
        result = parse_message(CREDIT_MESSAGE)
        assert result["amount"] == 1000.00

    def test_currency(self):
        result = parse_message(CREDIT_MESSAGE)
        assert result["currency"] == "UZS"

    def test_card(self):
        result = parse_message(CREDIT_MESSAGE)
        assert result["card"] == "***5056"

    def test_merchant(self):
        result = parse_message(CREDIT_MESSAGE)
        assert result["merchant"] == "XAZNA P2P UZCARD XB UZCARD OTHER, UZ"

    def test_timestamp(self):
        result = parse_message(CREDIT_MESSAGE)
        assert result["timestamp"] == "2026-05-23 02:45"

    def test_balance(self):
        result = parse_message(CREDIT_MESSAGE)
        assert result["balance"] == 13545.11


class TestUnknownMessages:
    def test_none_input(self):
        assert parse_message(None) is None

    def test_empty_string(self):
        assert parse_message("") is None

    def test_random_text(self):
        assert parse_message("Hello, this is a random message") is None

    def test_partial_message_no_amount(self):
        msg = "\U0001f534 Spisanie c karty"
        assert parse_message(msg) is None

    def test_wrong_emoji_prefix(self):
        msg = (
            "\U0001f535 Something else\n"
            "\u2796 1 000.00 UZS\n"
            "\U0001f553 23.05.26 02:45"
        )
        assert parse_message(msg) is None

    def test_non_string_input(self):
        assert parse_message(12345) is None

    def test_missing_timestamp(self):
        msg = (
            "\U0001f534 Spisanie c karty\n"
            "\u2796 1 005.00 UZS\n"
            "\U0001f4b3 ***7947"
        )
        assert parse_message(msg) is None

    def test_debit_without_optional_fields(self):
        """A minimal valid message: type, amount, and timestamp only."""
        msg = (
            "\U0001f534 Test transaction\n"
            "\u2796 500.00 UZS\n"
            "\U0001f553 23.05.26 10:00"
        )
        result = parse_message(msg)
        assert result is not None
        assert result["type"] == "debit"
        assert result["amount"] == 500.00
        assert result["card"] is None
        assert result["merchant"] is None
        assert result["balance"] is None


class TestEdgeCases:
    def test_large_amount_with_spaces(self):
        msg = (
            "\U0001f7e2 Popolnenie\n"
            "\u2795 10 000 000.50 UZS\n"
            "\U0001f553 23.05.26 12:00"
        )
        result = parse_message(msg)
        assert result["amount"] == 10000000.50

    def test_amount_no_decimals(self):
        msg = (
            "\U0001f534 Oplata\n"
            "\u2796 500 UZS\n"
            "\U0001f553 23.05.26 12:00"
        )
        result = parse_message(msg)
        assert result["amount"] == 500.0

    def test_whitespace_around_lines(self):
        msg = (
            "  \U0001f534 Spisanie c karty  \n"
            "  \u2796 1 005.00 UZS  \n"
            "  \U0001f553 23.05.26 02:45  \n"
        )
        result = parse_message(msg)
        assert result is not None
        assert result["type"] == "debit"
        assert result["amount"] == 1005.00
