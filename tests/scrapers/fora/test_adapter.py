"""
Unit tests for the ForaAdapter class.

This module verifies the data transformation logic specifically tailored
for the Fora supermarket's API. It ensures that raw JSON responses are
correctly mapped to the system's unified product schema, handling prices,
measurements, promotional tags, and missing data gracefully.
"""

import pytest
from unittest.mock import MagicMock
from scrapers.fora.adapter import ForaAdapter


class TestForaAdapter:
    """
    Test suite for the Fora data adapter.

    These tests validate the parsing of nested JSON structures, the calculation
    of discount percentages, the extraction of specific attributes (like
    national cashback), and the robust handling of missing or null fields.
    """

    @pytest.fixture
    def adapter(self):
        """
        Fixture that provides a fresh instance of the ForaAdapter.

        Returns:
            ForaAdapter: The adapter instance to be tested before each test run.
        """
        return ForaAdapter()

    @pytest.fixture
    def mock_media_proxy(self):
        """
        Fixture that creates a fake media proxy to bypass external network calls.

        This ensures tests run quickly and do not attempt to actually upload
        images to Cloudinary during the automated test suite execution.

        Returns:
            MagicMock: A mocked proxy that constantly returns a static fake image URL.
        """
        proxy = MagicMock()
        # Specifying that whenever process_image is called, it must return this string:
        proxy.process_image.return_value = "https://mocked.cloudinary.url/image.png"
        return proxy

    def test_normalize_empty_data(self, adapter, mock_media_proxy):
        """
        Tests the adapter's behavior when provided with empty or invalid data.

        Verifies that if the API returns an empty dictionary or lacks the
        core 'item' key, the adapter safely returns None.
        """
        assert adapter.normalize({}, mock_media_proxy) is None
        assert adapter.normalize({"error": "not found"}, mock_media_proxy) is None

    def test_normalize_full_product(self, adapter, mock_media_proxy):
        """
        Tests the complete normalization process for a fully populated product payload.

        Verifies the accurate mapping of base fields, the correct calculation
        of discounts, the extraction of nested attributes (calories, brand),
        and the processing of promotional bubbles (e.g., national cashback).
        """
        raw_json = {
            "item": {
                "id": 523478,
                "name": "Шоколад молочний Milka Bubbles",
                "slug": "shokolad-molochnyi-milka-523478",
                "category": {"name": "Шоколад, плитка"},
                "price": 64.9,
                "oldPrice": 89.9,
                "parameters": [
                    {"key": "trademark", "value": "Milka"},
                    {"key": "country", "value": "Україна"},
                    {"key": "calorie", "value": "532/2225"}
                ],
                "bubbles": [{"id": "natsionalnyi-keshbek"}],
                "mainImage": "raw_main.png",
                "images": [{"path": "raw_main.png"}],
                "unit": "80 г",
                "isWeightedProduct": False,
                "unitStep": 1,
                "calcStoreQuantity": 15,
                "rating": 4.0,
                "votesCount": 10
            }
        }

        result = adapter.normalize(raw_json, mock_media_proxy)

        # 1. Base fields validation
        assert result["product_id"] == "fora_523478"
        assert result["canonical_name"] == "Шоколад молочний Milka Bubbles"
        assert result["brand"] == "Milka"
        assert result["country"] == "Україна"
        assert result["category"] == "Шоколад, плитка"

        # 2. Pricing and discount logic validation (89.9 -> 64.9 is ~28% discount)
        offer = result["offers"][0]
        assert offer["store_name"] == "Фора"
        assert offer["is_in_stock"] is True
        assert offer["pricing"]["current_price"] == 64.9
        assert offer["pricing"]["regular_price"] == 89.9
        assert offer["pricing"]["discount_percent"] == 28

        # 3. Specific attributes validation (Cashback)
        assert result["specific_attributes"]["calories"] == "532/2225"
        assert result["specific_attributes"]["is_national_cashback_eligible"] is True

        # 4. Measurement validation (Should be processed by the tested BaseAdapter logic)
        assert result["measurements"]["value"] == 80.0
        assert result["measurements"]["unit"] == "g"

        # 5. Image validation (Should use the injected mock_media_proxy response)
        assert result["media"]["main_image"] == "https://mocked.cloudinary.url/image.png"

    def test_normalize_regular_price_no_discount(self, adapter, mock_media_proxy):
        """
        Tests the pricing logic for products without active promotions.

        Verifies that when 'oldPrice' is absent or lower than the current price,
        the regular price equals the current price, and the discount is calculated as 0.
        """
        raw_json = {
            "item": {
                "id": 111,
                "name": "Хліб",
                "price": 25.0,
                # oldPrice is absent
            }
        }

        result = adapter.normalize(raw_json, mock_media_proxy)
        offer = result["offers"][0]

        assert offer["pricing"]["current_price"] == 25.0
        assert offer["pricing"]["regular_price"] == 25.0
        assert offer["pricing"]["discount_percent"] == 0

    def test_normalize_missing_parameters_and_bubbles(self, adapter, mock_media_proxy):
        """
        Tests robust handling of null values for list-based API fields.

        Verifies that the adapter correctly uses fallback empty lists `(or [])`
        when the API returns `None` for parameters, bubbles, or categories,
        preventing 'NoneType is not iterable' exceptions.
        """
        raw_json = {
            "item": {
                "id": 222,
                "name": "Товар без інфи",
                "parameters": None,  # Might be None instead of an empty list []
                "bubbles": None,
                "category": None
            }
        }

        # If the code does not crash with a TypeError, the test is passed successfully
        result = adapter.normalize(raw_json, mock_media_proxy)

        assert result["brand"] is None
        assert result["category"] == "Невідома категорія"
        assert result["specific_attributes"]["is_national_cashback_eligible"] is False