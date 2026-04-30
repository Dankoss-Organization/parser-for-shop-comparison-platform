"""
Unit tests for the SilpoApiClient class.

This module verifies the network communication layer for the Silpo scraper.
It utilizes `unittest.mock.patch` to intercept HTTP GET requests, enabling
the testing of successful data retrieval, error handling, and complex
pagination logic without making actual network calls.
"""

import pytest
import requests
from unittest.mock import patch, MagicMock
from scrapers.silpo.api_client import SilpoApiClient


class TestSilpoApiClient:
    """
    Test suite for the Silpo API client.

    These tests validate the client's ability to fetch detailed product
    information, handle HTTP exceptions, navigate through paginated
    product lists (Discovery phase), and terminate loops efficiently
    when no more data is available.
    """

    @patch('scrapers.silpo.api_client.requests.get')
    def test_fetch_detailed_product_success(self, mock_get):
        """
        Tests the successful retrieval of detailed product information.

        Verifies that the client correctly executes a GET request and
        returns the parsed JSON response when the API call is successful.

        Args:
            mock_get (MagicMock): The mocked requests.get method.
        """
        # Configure the fake response from Silpo
        mock_response = MagicMock()
        mock_response.json.return_value = {"title": "Банан", "externalProductId": "123"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = SilpoApiClient.fetch_detailed_product("banan-123")

        assert result["title"] == "Банан"
        # Verify that exactly one GET request was executed
        mock_get.assert_called_once()

    @patch('scrapers.silpo.api_client.requests.get')
    def test_fetch_detailed_product_error(self, mock_get):
        """
        Tests error handling during detailed product retrieval.

        Verifies that HTTP errors (such as 404 Not Found or timeouts)
        are caught and wrapped in a custom application exception.

        Args:
            mock_get (MagicMock): The mocked requests.get method.
        """
        mock_get.side_effect = requests.exceptions.HTTPError("404 Not Found")

        with pytest.raises(Exception) as exc_info:
            SilpoApiClient.fetch_detailed_product("unknown-slug")

        assert "Відмова API Сільпо" in str(exc_info.value)

    @patch('scrapers.silpo.api_client.requests.get')
    def test_fetch_all_slugs_pagination(self, mock_get):
        """
        Tests the product discovery phase across multiple pages.

        Simulates a paginated API response sequence to verify that the
        client accurately aggregates product slugs from multiple pages.

        Args:
            mock_get (MagicMock): The mocked requests.get method.
        """
        # Response for the 1st page (2 items)
        mock_resp_p1 = MagicMock()
        mock_resp_p1.json.return_value = {
            "items": [{"slug": "apple"}, {"slug": "pear"}]
        }

        # Response for the 2nd page (1 item)
        mock_resp_p2 = MagicMock()
        mock_resp_p2.json.return_value = {
            "items": [{"slug": "orange"}]
        }

        # Set up the sequence of responses
        mock_get.side_effect = [mock_resp_p1, mock_resp_p2]

        # Call the method with a maximum of 2 pages
        slugs = SilpoApiClient.fetch_all_slugs(max_pages=2)

        # Verify that all 3 unique items were collected
        assert len(slugs) == 3
        assert "apple" in slugs
        assert "orange" in slugs
        assert mock_get.call_count == 2

    @patch('scrapers.silpo.api_client.requests.get')
    def test_fetch_all_slugs_empty_stop(self, mock_get):
        """
        Tests the early termination of the pagination loop.

        Verifies that if the API returns an empty items list before
        reaching the `max_pages` limit, the client correctly breaks
        the loop to prevent unnecessary network requests.

        Args:
            mock_get (MagicMock): The mocked requests.get method.
        """
        mock_resp_empty = MagicMock()
        mock_resp_empty.json.return_value = {"items": []}
        mock_get.return_value = mock_resp_empty

        slugs = SilpoApiClient.fetch_all_slugs(max_pages=5)

        # Despite a limit of 5 pages, there should be only 1 call
        # because the first response's items list is empty
        assert slugs == []
        assert mock_get.call_count == 1