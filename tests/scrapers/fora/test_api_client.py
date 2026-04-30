"""
Unit tests for the ForaApiClient class.

This module verifies the network communication layer for the Fora scraper.
It uses `unittest.mock.patch` to intercept HTTP requests, allowing the tests
to simulate various API responses (success, timeouts, malformed data)
without making real network calls.
"""

import pytest
import requests
from unittest.mock import patch, MagicMock
from scrapers.fora.api_client import ForaApiClient


class TestForaApiClient:
    """
    Test suite for the Fora API client.

    These tests validate the client's ability to fetch detailed product
    data, execute the paginated discovery phase to collect product slugs,
    and gracefully handle network failures or incomplete JSON responses.
    """

    # @patch replaces the actual requests.post in api_client with a mock object (mock_post)
    @patch('scrapers.fora.api_client.requests.post')
    def test_fetch_detailed_product_success(self, mock_post):
        """
        Tests a successful request for detailed product information.

        Args:
            mock_post (MagicMock): The mocked requests.post method.
        """
        # 1. Configure the mocked response
        mock_response = MagicMock()
        mock_response.json.return_value = {"item": {"id": 123, "name": "Хліб"}}
        mock_response.raise_for_status = MagicMock()  # Simulate a successful HTTP status code (200 OK)
        mock_post.return_value = mock_response

        # 2. Call the target method
        result = ForaApiClient.fetch_detailed_product("hlib-123")

        # 3. Verify the results
        assert result == {"item": {"id": 123, "name": "Хліб"}}
        # Verify that our client actually called requests.post exactly once
        mock_post.assert_called_once()

    @patch('scrapers.fora.api_client.requests.post')
    def test_fetch_detailed_product_network_error(self, mock_post):
        """
        Tests the client's reaction to network failures or timeouts.

        Args:
            mock_post (MagicMock): The mocked requests.post method.
        """
        # Force the mocked request to raise a network timeout exception
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        # Verify that the client catches this error and raises its own custom exception
        with pytest.raises(Exception) as exc_info:
            ForaApiClient.fetch_detailed_product("hlib-123")

        assert "Відмова API Фори: Connection timed out" in str(exc_info.value)

    @patch('scrapers.fora.api_client.requests.post')
    def test_fetch_all_slugs_success(self, mock_post):
        """
        Tests the complex chain of requests (Categories -> Paginated Products).

        Args:
            mock_post (MagicMock): The mocked requests.post method.
        """
        # 1. Category request response
        mock_cat_resp = MagicMock()
        mock_cat_resp.json.return_value = {"tree": [{"slug": "cat1"}]}

        # 2. Product request response (Page 1)
        mock_items_page1 = MagicMock()
        mock_items_page1.json.return_value = {
            "items": [{"slug": "item1"}, {"slug": "item2"}],
            "itemsCount": 40  # Changed to 40 so the pagination loop continues (since 30 < 40)
        }

        # 3. Product request response (Page 2)
        mock_items_page2 = MagicMock()
        mock_items_page2.json.return_value = {
            "items": [{"slug": "item3"}, {"slug": "item4"}],
            "itemsCount": 40
        }

        # Assign the sequence of responses to the mocked post method
        mock_post.side_effect = [mock_cat_resp, mock_items_page1, mock_items_page2]

        slugs = ForaApiClient.fetch_all_slugs(max_pages=2)

        # Verify that all unique slugs were successfully collected
        assert set(slugs) == {"item1", "item2", "item3", "item4"}
        assert mock_post.call_count == 3

    @patch('scrapers.fora.api_client.requests.post')
    def test_fetch_all_slugs_category_fail(self, mock_post):
        """
        Tests resilience when the initial category API endpoint is down.

        The client must catch the exception and return an empty list rather
        than crashing the entire application.

        Args:
            mock_post (MagicMock): The mocked requests.post method.
        """
        mock_post.side_effect = requests.exceptions.ConnectionError("API is down")

        slugs = ForaApiClient.fetch_all_slugs()

        assert slugs == []  # Returns an empty list, as defined in the except block

    @patch('scrapers.fora.api_client.requests.post')
    def test_fetch_all_slugs_partial_data(self, mock_post):
        """
        Tests resilience when items lack slugs or the response is malformed.

        Args:
            mock_post (MagicMock): The mocked requests.post method.
        """
        mock_cat_resp = MagicMock()
        mock_cat_resp.json.return_value = {"tree": [{"slug": "cat1"}]}

        mock_items_resp = MagicMock()
        mock_items_resp.json.return_value = {
            "items": [
                {"slug": "valid-item"},
                {"name": "item-without-slug"},  # This should be ignored by the logic
                None  # This should trigger the exception block and safely break the loop
            ],
            # itemsCount is missing (evaluates to None in .get)
        }

        mock_post.side_effect = [mock_cat_resp, mock_items_resp]

        slugs = ForaApiClient.fetch_all_slugs(max_pages=1)

        # Verify that the valid item was saved before the malformed data broke the loop
        assert slugs == ["valid-item"]
        assert len(slugs) == 1