import re
from typing import Dict, Any, Union
from bs4 import BeautifulSoup


class BaseAdapter:
    """
    The BaseAdapter serves as the foundation for all store-specific data transformers.

    Its primary responsibility is to define the interface for converting raw
    JSON data from various supermarket APIs into a standardized internal
    dictionary format used by the Shop Comparison Platform.
    """

    @staticmethod
    def strip_html(text: str) -> str:
        """
        Removes all HTML tags from a string and returns clean plain text.

        Uses BeautifulSoup for robust parsing (handles malformed tags,
        entities like &amp;, &nbsp; etc.). Falls back gracefully on
        empty/None input.

        Args:
            text (str): Raw string potentially containing HTML markup.

        Returns:
            str: Plain text with all HTML tags removed and whitespace normalized.

        Examples:
            >>> BaseAdapter.strip_html("<p>Смачний <b>йогурт</b></p>")
            'Смачний йогурт'
            >>> BaseAdapter.strip_html("Без тегів")
            'Без тегів'
            >>> BaseAdapter.strip_html(None)
            ''
        """
        if not text:
            return ""
        return BeautifulSoup(str(text), "html.parser").get_text(separator=" ", strip=True)

    @staticmethod
    def parse_measurements(ratio_str: Any) -> Dict[str, Union[float, str]]:
        """
        Parses a raw measurement string into a standardized numerical value and unit.

        This method handles various formats commonly found in Ukrainian supermarket
        data (e.g., "500 г", "1,5кг", "2L"). It uses regular expressions to
        separate digits from alphabetic units and normalizes decimal separators.

        Logic Flow:
        1. Converts input to a lower-case string and removes whitespace.
        2. Replaces commas (`,`) with dots (`.`) for float compatibility.
        3. Matches the string against a regex: `([digits]) [letters]`.
        4. Maps common Ukrainian units (г, кг, л) to standardized SI-like codes (g, kg, l).
        5. Returns a fallback of 1.0 pcs if parsing fails or input is empty.

        Args:
            ratio_str (Any): The raw string or value representing weight or volume
                (e.g., "400 g", "1.5 кг", "шт").

        Returns:
            Dict[str, Union[float, str]]: A dictionary containing:
                - 'value' (float): The extracted numerical amount.
                - 'unit' (str): The standardized unit (e.g., "g", "kg", "ml", "l", "pcs").

        Examples:
            >>> BaseAdapter.parse_measurements("250г")
            {'value': 250.0, 'unit': 'g'}
            >>> BaseAdapter.parse_measurements("1,75 л")
            {'value': 1.75, 'unit': 'l'}
        """
        if not ratio_str:
            return {"value": 1.0, "unit": "pcs"}

        # Normalize string: lower case, strip whitespace, fix decimal comma
        normalized_str = str(ratio_str).lower().strip().replace(',', '.')

        # Regex explanation:
        # ([\d\.,]+) - Group 1: Matches numbers, dots, and commas
        # \s* - Optional whitespace
        # ([а-яіїєґa-zA-Z]+) - Group 2: Matches Cyrillic or Latin letters
        match = re.match(r"([\d\.,]+)\s*([а-яіїєґa-zA-Z]+)", normalized_str)

        if match:
            try:
                val = float(match.group(1))
                unit = match.group(2)

                # Mapping dictionary to unify Ukrainian and English units
                unit_map = {
                    "г": "g", "g": "g",
                    "кг": "kg", "kg": "kg",
                    "л": "l", "l": "l",
                    "мл": "ml", "ml": "ml",
                    "шт": "pcs", "pcs": "pcs"
                }

                return {
                    "value": val,
                    "unit": unit_map.get(unit, unit)
                }
            except ValueError:
                # Fallback if float conversion fails despite regex match
                return {"value": 1.0, "unit": "pcs"}

        return {"value": 1.0, "unit": "pcs"}

    def normalize(self, raw_data: Dict[str, Any], media_proxy: Any) -> Dict[str, Any]:
        """
        An abstract method that must be implemented by store-specific subclasses.

        The implementation should map the unique JSON structure of a specific
        supermarket (like Silpo or Fora) to the Unified Product Schema.

        Args:
            raw_data (Dict[str, Any]): The raw dictionary obtained from the scraper's API call.
            media_proxy (CloudinaryImageProxy): An instance of the media proxy
                used to process and upload images to cloud storage.

        Returns:
            Dict[str, Any]: A standardized dictionary containing canonical product
                details, pricing, and media links.

        Raises:
            NotImplementedError: If the subclass does not provide its own
                implementation of this method.
        """
        raise NotImplementedError("This method must be implemented by specific store adapter classes.")