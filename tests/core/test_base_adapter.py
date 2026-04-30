"""
Unit tests for the BaseAdapter class.

This module contains a comprehensive test suite for the core adapter logic,
specifically focusing on measurement string parsing and ensuring the
abstract nature of the normalization method. It utilizes the `pytest`
framework for automated verification.
"""

import pytest
from core.base_adapter import BaseAdapter

class TestBaseAdapter:
    """
    Test suite for the BaseAdapter utility class.

    This class groups tests that verify the robust extraction of weight,
    volume, and quantity measurements from raw store strings, as well as
    proper enforcement of the adapter interface.
    """

    @pytest.mark.parametrize("input_str, expected", [
        # 1. Grams (Cyrillic and Latin, with and without spaces)
        ("150г", {"value": 150.0, "unit": "g"}),
        ("150 г", {"value": 150.0, "unit": "g"}),
        ("150g", {"value": 150.0, "unit": "g"}),

        # 2. Kilograms
        ("1.5кг", {"value": 1.5, "unit": "kg"}),
        ("1,5 кг", {"value": 1.5, "unit": "kg"}),  # Comma must be replaced by a dot
        ("2kg", {"value": 2.0, "unit": "kg"}),

        # 3. Liquids (Milliliters and Liters)
        ("500 мл", {"value": 500.0, "unit": "ml"}),
        ("500ml", {"value": 500.0, "unit": "ml"}),
        ("1.5 л", {"value": 1.5, "unit": "l"}),
        ("2l", {"value": 2.0, "unit": "l"}),

        # 4. Pieces/Units
        ("10 шт", {"value": 10.0, "unit": "pcs"}),
        ("1шт", {"value": 1.0, "unit": "pcs"}),
        ("5 pcs", {"value": 5.0, "unit": "pcs"}),

        # 5. Unknown measurement units (Regex should capture digits and letters)
        ("100 унцій", {"value": 100.0, "unit": "унцій"}),
    ])
    def test_parse_measurements_valid_inputs(self, input_str, expected):
        """
        Validates correct parsing of various measurement units and numeric formats.

        This test ensures that the static method can handle different languages
        (Cyrillic/Latin), punctuation (commas/dots), and optional spacing
        between the value and the unit.

        Args:
            input_str (str): The raw string containing measurement data.
            expected (dict): The expected dictionary with 'value' (float) and 'unit' (str).
        """
        assert BaseAdapter.parse_measurements(input_str) == expected

    @pytest.mark.parametrize("invalid_input", [
        "",
        None,
        "   ",
        "plain text",     # No digits present
        "100",            # No units/letters present
        "kg 1.5",         # Incorrect order (unit before value)
    ])
    def test_parse_measurements_invalid_and_fallback(self, invalid_input):
        """
        Tests fallback behavior for malformed, empty, or invalid inputs.

        Verifies that when the input does not match the expected numeric+unit
        format, the method returns a safe default value representing 1 piece.

        Args:
            invalid_input (str or None): The malformed input string to test.
        """
        assert BaseAdapter.parse_measurements(invalid_input) == {"value": 1.0, "unit": "pcs"}

    def test_normalize_raises_not_implemented_error(self):
        """
        Verifies that the base normalize method enforces implementation in subclasses.
        """
        adapter = BaseAdapter()

        # Check if NotImplementedError is properly raised
        with pytest.raises(NotImplementedError) as exc_info:
            adapter.normalize(raw_data={}, media_proxy=None)

        # ОНОВЛЕНО: Тепер ми чекаємо англійський текст, який реально є у файлі base_adapter.py
        assert "This method must be implemented by specific store adapter classes." in str(exc_info.value)