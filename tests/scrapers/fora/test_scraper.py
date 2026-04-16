"""
Unit tests for the ForaScraper class.

This module contains tests to verify the high-level scraping workflow
for the Fora supermarket. It ensures that the scraper correctly interacts
with the underlying API client to discover product slugs and fetch
detailed product data, while properly handling internal API-level errors.
"""

import pytest
from unittest.mock import patch, MagicMock
from scrapers.fora.scraper import ForaScraper


class TestForaScraper:
    """
    Test suite for the ForaScraper class.

    Validates the scraper's ability to orchestrate the discovery phase
    and the detailed fetching phase, mocking out the actual API network calls
    and the downstream normalization components (Adapter and MediaProxy).
    """

    @pytest.fixture
    def scraper(self):
        """
        Provides a configured instance of ForaScraper for testing.

        Initializes the scraper with mocked `adapter` and `media_proxy`
        dependencies, as data normalization and image uploading are not
        the focus of this specific unit test suite.

        Returns:
            ForaScraper: An instance of the scraper ready for testing.
        """
        return ForaScraper(adapter=MagicMock(), media_proxy=MagicMock())

    @patch('scrapers.fora.scraper.ForaApiClient.fetch_all_slugs')
    def test_discover_slugs_success(self, mock_fetch, scraper):
        """
        Tests the successful discovery of product slugs.

        Verifies that the scraper correctly calls the API client to retrieve
        a list of slugs and applies the expected pagination constraints (max_pages=2).

        Args:
            mock_fetch (MagicMock): The mocked fetch_all_slugs method.
            scraper (ForaScraper): The scraper instance under test.
        """
        mock_fetch.return_value = ["item-1", "item-2"]

        slugs = scraper.discover_slugs()

        assert slugs == ["item-1", "item-2"]
        # Verify that the method was called exactly once with the specific page limit
        mock_fetch.assert_called_once_with(max_pages=2)

    @patch('scrapers.fora.scraper.ForaApiClient.fetch_detailed_product')
    def test_fetch_data_success(self, mock_fetch_detail, scraper):
        """
        Tests successfully fetching raw data for a specific product slug.

        Verifies that the scraper passes the correct slug to the API client
        and returns the valid JSON response payload unmodified.

        Args:
            mock_fetch_detail (MagicMock): The mocked fetch_detailed_product method.
            scraper (ForaScraper): The scraper instance under test.
        """
        mock_data = {"data": {"name": "Молоко"}, "EComError": {"ErrorCode": 0}}
        mock_fetch_detail.return_value = mock_data

        result = scraper.fetch_data("moloko-slug")

        assert result == mock_data
        mock_fetch_detail.assert_called_once_with("moloko-slug")

    @patch('scrapers.fora.scraper.ForaApiClient.fetch_detailed_product')
    def test_fetch_data_with_api_error(self, mock_fetch_detail, scraper):
        """
        Tests error handling when the API returns a logical application error.

        Sometimes the HTTP status code is 200 (OK), but the payload itself
        contains an internal application error (e.g., 'ErrorCode': 1).
        This test verifies that the scraper correctly detects this format
        and safely returns None instead of passing bad data to the adapter.

        Args:
            mock_fetch_detail (MagicMock): The mocked fetch_detailed_product method.
            scraper (ForaScraper): The scraper instance under test.
        """
        mock_error_data = {
            "EComError": {"ErrorCode": 1, "ErrorMessage": "Product not found"}
        }
        mock_fetch_detail.return_value = mock_error_data

        result = scraper.fetch_data("bad-slug")

        # The scraper should return None, per the 'if not ErrorCode' logic
        assert result is None

    @patch('scrapers.fora.scraper.ForaApiClient.fetch_detailed_product')
    def test_fetch_data_empty_response(self, mock_fetch_detail, scraper):
        """
        Tests the handling of empty or None responses from the API client.

        Verifies that if the underlying API client returns None (e.g., due
        to a timeout or completely missing data), the scraper also safely
        returns None.

        Args:
            mock_fetch_detail (MagicMock): The mocked fetch_detailed_product method.
            scraper (ForaScraper): The scraper instance under test.
        """
        mock_fetch_detail.return_value = None

        result = scraper.fetch_data("any-slug")

        assert result is None