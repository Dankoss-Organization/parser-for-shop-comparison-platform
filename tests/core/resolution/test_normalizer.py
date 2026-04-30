"""
Unit tests for the text normalization module.

This test suite verifies the functionality of the `clean_text` function.
It ensures that the function correctly processes product names by converting
them to lowercase, removing punctuation, handling edge cases, and filtering
out predefined stop words (e.g., promotional terms, currencies, and
measurement units).
"""

import pytest
from core.resolution.normalizer import clean_text


class TestNormalizer:
    """
    A comprehensive collection of test cases for the `clean_text` function.

    This class groups all unit tests related to text normalization. It covers
    standard input processing, whitespace handling, stop-word removal, 
    false-positive prevention, and invalid data type handling.
    """

    @pytest.mark.parametrize("input_text, expected", [
        # 1. Basic lowercasing
        ("МОЛОКО", "молоко"),
        ("Сир Твердий", "сир твердий"),
        ("kefir", "kefir"),

        # 2. Punctuation and special character removal
        ("Шоколад Milka!", "шоколад milka"),
        ("Молоко, Яготинське", "молоко яготинське"),
        ("Печиво (з горіхами)", "печиво горіхами"),
        ("Сир «Голландський»", "сир голландський"),
        ("Ціна: 100$", "ціна 100"),
        ("Кефір 2.5%", "кефір 2 5"),  # Dot and % are replaced by spaces
        ("Кока-кола", "кока кола"),

        # 3. Whitespace normalization (extra spaces, tabs, newlines)
        ("Сир    Твердий", "сир твердий"),
        ("Йогурт\tПерсиковий", "йогурт персиковий"),
        ("Банан \n 1 \n кг", "банан 1"),
        ("  Хліб   ", "хліб"),

        # 4. Stop-word removal (promotional words, currencies, measurement units)
        ("Акція Банан", "банан"),
        ("знижка Хліб білий", "хліб білий"),
        ("суперціна! Ковбаса", "ковбаса"),
        ("Новинка Йогурт", "йогурт"),
        ("Чай чорний упаковка", "чай чорний"),
        ("Ціна 50 грн", "ціна 50"),
        ("Яйця 10 шт", "яйця 10"),
        ("Сир 200 г", "сир 200"),
        ("М'ясо 1 кг", "м ясо 1"),  # Apostrophe is removed and becomes a space
        ("Сік 500 мл", "сік 500"),
        ("Вода 1.5 л", "вода 1 5"),

        # 5. Combinations of multiple stop-words and punctuation
        ("Акція! Цукерки 500 г, суперціна 100 грн", "цукерки 500 100"),
        ("Новинка: Печиво 10 шт (упаковка)", "печиво 10"),
        ("Знижка - молоко 1 л 30 грн!", "молоко 1 30"),

        # 6. Protection against partial matches (False Positives)
        # The function should NOT remove letters inside valid words
        ("Штора", "штора"),  # Contains 'шт', but is a different word
        ("Гранат", "гранат"),  # Contains 'г'
        ("Амлу", "амлу"),  # Contains 'мл'
        ("КГБ", "кгб"),  # Contains 'кг', but is part of another word
        ("Лілія", "лілія"),  # Starts with 'л'
    ])
    def test_clean_text_variations(self, input_text, expected):
        """
        Tests standard string transformations using parameterized inputs.

        This test validates that the `clean_text` function successfully applies
        lowercasing, strips punctuation, normalizes whitespace, removes
        stop words, and safely ignores partial word matches to prevent
        accidental data loss.

        Args:
            input_text (str): The raw string to be normalized.
            expected (str): The expected normalized output string.
        """
        assert clean_text(input_text) == expected

    # 7. Testing empty or None values
    @pytest.mark.parametrize("invalid_input, expected", [
        ("", ""),
        (None, ""),
        ("   ", ""),  # String with spaces only
    ])
    def test_clean_text_empty_and_none(self, invalid_input, expected):
        """
        Tests the normalizer's behavior with empty, null, or whitespace-only inputs.

        Ensures that providing missing or empty string values safely returns
        an empty string without raising exceptions.

        Args:
            invalid_input (str or None): The empty or null input value.
            expected (str): Expected to always evaluate to an empty string.
        """
        assert clean_text(invalid_input) == expected

    # 8. Specific and extreme edge cases
    def test_clean_text_only_stop_words(self):
        """
        Tests normalization on strings composed entirely of stop words and punctuation.

        Verifies that when a string contains no meaningful product name tokens,
        the normalizer correctly strips everything except valid numbers (if any).
        """
        assert clean_text("Акція! Знижка 100 грн за 1 кг (упаковка шт)") == "100 1"  # Only numbers remain
        assert clean_text("акція знижка суперціна шт г кг") == ""

    def test_clean_text_numbers_only(self):
        """
        Tests the preservation of numeric values.

        Verifies that strings consisting solely of digits or multiple
        digit groups are returned completely intact without being stripped.
        """
        assert clean_text("12345") == "12345"
        assert clean_text("100 500") == "100 500"

    def test_clean_text_emojis_and_symbols(self):
        """
        Tests the removal of emojis and non-standard graphical symbols.

        Verifies that the underlying regular expression correctly identifies
        and replaces Unicode emojis and graphical symbols with spaces,
        preventing pollution of the normalized text database.
        """
        assert clean_text("Молоко 🥛 1 л 💯") == "молоко 1"
        assert clean_text("Банан 🍌🍌🍌 суперціна!!!") == "банан"

    def test_clean_text_wrong_type(self):
        """
        Tests type enforcement and exception handling.

        Verifies that passing unsupported data types (such as integers or lists)
        raises an `AttributeError`, since the normalizer strictly expects a
        string input that implements the `.lower()` method.
        """
        with pytest.raises(AttributeError):
            clean_text(123)  # Integer has no .lower() method

        with pytest.raises(AttributeError):
            clean_text(["Хліб", "Білий"])  # List has no .lower() method