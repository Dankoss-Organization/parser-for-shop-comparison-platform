import pytest
from unittest.mock import patch, MagicMock
from scrapers.silpo.scraper import SilpoScraper


class TestSilpoScraper:

    @pytest.fixture
    def scraper(self):
        # Створюємо скрапер з фейковими залежностями
        return SilpoScraper(adapter=MagicMock(), media_proxy=MagicMock())

    @patch('scrapers.silpo.scraper.SilpoApiClient.fetch_all_slugs')
    def test_discover_slugs_calls_api(self, mock_fetch, scraper):
        """Перевіряє, чи скрапер звертається до правильного методу API для збору товарів"""
        mock_fetch.return_value = ["slug1", "slug2"]

        result = scraper.discover_slugs()

        assert result == ["slug1", "slug2"]
        mock_fetch.assert_called_once_with(max_pages=2)

    @patch('scrapers.silpo.scraper.SilpoApiClient.fetch_detailed_product')
    def test_fetch_data_calls_api(self, mock_fetch, scraper):
        """Перевіряє, чи скрапер правильно запитує деталі конкретного товару"""
        mock_fetch.return_value = {"id": 1}

        result = scraper.fetch_data("test-slug")

        assert result == {"id": 1}
        mock_fetch.assert_called_once_with("test-slug")