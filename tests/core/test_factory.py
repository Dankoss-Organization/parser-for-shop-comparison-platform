"""
Unit tests for the ParserFactory class.

This module ensures that the Factory Pattern is correctly implemented,
verifying that the factory instantiates the appropriate scraper subclasses
based on the provided store name and handles errors gracefully.
"""

import pytest
from core.factory import ParserFactory
from scrapers.silpo.scraper import SilpoScraper
from scrapers.fora.scraper import ForaScraper


class TestParserFactory:
    """
    A suite of tests to validate the ParserFactory logic.

    These tests confirm that the factory correctly routes requests to the
    proper scraper classes (Silpo or Fora) and strictly enforces valid,
    case-sensitive store identifiers.
    """

    def test_factory_creates_silpo_scraper(self):
        """
        Verify that the factory correctly instantiates a Silpo scraper.

        This test checks if providing the key "silpo" returns an instance
        of the SilpoScraper class.
        """
        scraper = ParserFactory.create_scraper("silpo")
        # assert isinstance checks if the object is indeed an instance of the specified class
        assert isinstance(scraper, SilpoScraper)

    def test_factory_creates_fora_scraper(self):
        """
        Verify that the factory correctly instantiates a Fora scraper.

        This test checks if providing the key "fora" returns an instance
        of the ForaScraper class.
        """
        scraper = ParserFactory.create_scraper("fora")
        assert isinstance(scraper, ForaScraper)

    def test_factory_raises_error_for_unknown_store(self):
        """
        Verify that the factory raises a ValueError for unsupported store names.

        This test ensures that the factory fails safely when an invalid
        identifier (e.g., "atb") is provided.
        """
        with pytest.raises(ValueError) as exc_info:
            ParserFactory.create_scraper("atb")

        # Check both the occurrence of the error and the specific message content
        assert "Магазин 'atb' не підтримується" in str(exc_info.value)

    def test_factory_is_case_insensitive(self):
        """
        Verify that the factory is case-insensitive regarding store identifiers.

        This test ensures that the factory correctly processes names regardless
        of capitalization (e.g., "Silpo" or "SILPO" should work just like "silpo").
        """
        scraper = ParserFactory.create_scraper("SILPO")

        assert scraper.__class__.__name__ == "SilpoScraper"