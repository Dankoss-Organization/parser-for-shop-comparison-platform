"""
Unit tests for the SilpoScraper class.

This module verifies the high-level orchestration logic for the Silpo
supermarket scraper. It ensures that the scraper correctly delegates
the tasks of product discovery and detailed data fetching to the
underlying API client without making real network requests.
"""

import pytest
from unittest.mock import patch, MagicMock
from scrapers.silpo.scraper import SilpoScraper


class TestSilpoScraper:
    """
    Test suite for the SilpoScraper class.

    These tests validate the interaction between the scraper and its
    dependencies, ensuring that API client methods are called with the
    correct parameters during both the discovery and fetching phases.
    """

    @pytest.fixture
    def scraper(self):
        """
        Provides a configured instance of SilpoScraper for testing.

        Initializes the scraper with mocked `adapter` and `media_proxy`
        dependencies, as data normalization and image uploading are outside
        the scope of this specific test suite.

        Returns:
            SilpoScraper: An instance of the scraper ready for testing.
        """
        # Create a scraper with fake dependencies
        return SilpoScraper(adapter=MagicMock(), media_proxy=MagicMock())

    @patch('scrapers.silpo.scraper.SilpoApiClient.fetch_all_slugs')
    def test_discover_slugs_calls_api(self, mock_fetch, scraper):
        """
        Tests the delegation of the product discovery phase.

        Verifies that the scraper correctly calls the appropriate API client
        method to gather product slugs and passes the expected pagination
        limit parameter.

        Args:
            mock_fetch (MagicMock): The mocked fetch_all_slugs method.
            scraper (SilpoScraper): The scraper instance under test.
        """
        mock_fetch.return_value = ["slug1", "slug2"]

        result = scraper.discover_slugs()

        assert result == ["slug1", "slug2"]
        mock_fetch.assert_called_once_with(max_pages=2)

    @patch('scrapers.silpo.scraper.SilpoApiClient.fetch_detailed_product')
    def test_fetch_data_calls_api(self, mock_fetch, scraper):
        """
        Tests the delegation of detailed product data fetching.

        Verifies that the scraper correctly requests details for a specific
        product by passing its slug directly to the API client.

        Args:
            mock_fetch (MagicMock): The mocked fetch_detailed_product method.
            scraper (SilpoScraper): The scraper instance under test.
        """
        mock_fetch.return_value = {"id": 1}

        result = scraper.fetch_data("test-slug")

        assert result == {"id": 1}
        mock_fetch.assert_called_once_with("test-slug")