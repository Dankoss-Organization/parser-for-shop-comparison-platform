import pytest
from unittest.mock import patch, MagicMock
from scrapers.fora.scraper import ForaScraper


class TestForaScraper:

    @pytest.fixture
    def scraper(self):
        # Ініціалізуємо скрапер. Адаптер та медіа-проксі нам тут не потрібні,
        # тому передаємо заглушки.
        return ForaScraper(adapter=MagicMock(), media_proxy=MagicMock())

    @patch('scrapers.fora.scraper.ForaApiClient.fetch_all_slugs')
    def test_discover_slugs_success(self, mock_fetch, scraper):
        """Перевіряє, чи скрапер коректно витягує список slug-ів через клієнт"""
        mock_fetch.return_value = ["item-1", "item-2"]

        slugs = scraper.discover_slugs()

        assert slugs == ["item-1", "item-2"]
        # Перевіряємо, що викликається саме з max_pages=2 (як у твоєму коді)
        mock_fetch.assert_called_once_with(max_pages=2)

    @patch('scrapers.fora.scraper.ForaApiClient.fetch_detailed_product')
    def test_fetch_data_success(self, mock_fetch_detail, scraper):
        """Перевіряє успішне отримання даних про товар"""
        mock_data = {"data": {"name": "Молоко"}, "EComError": {"ErrorCode": 0}}
        mock_fetch_detail.return_value = mock_data

        result = scraper.fetch_data("moloko-slug")

        assert result == mock_data
        mock_fetch_detail.assert_called_once_with("moloko-slug")

    @patch('scrapers.fora.scraper.ForaApiClient.fetch_detailed_product')
    def test_fetch_data_with_api_error(self, mock_fetch_detail, scraper):
        """Перевіряє поведінку, якщо API Фори повернуло помилку в JSON"""
        # Буває, що HTTP код 200, але в тілі відповіді прийшла помилка
        mock_error_data = {
            "EComError": {"ErrorCode": 1, "ErrorMessage": "Product not found"}
        }
        mock_fetch_detail.return_value = mock_error_data

        result = scraper.fetch_data("bad-slug")

        # Скрапер має повернути None, згідно з твоєю логікою 'if not ErrorCode'
        assert result is None

    @patch('scrapers.fora.scraper.ForaApiClient.fetch_detailed_product')
    def test_fetch_data_empty_response(self, mock_fetch_detail, scraper):
        """Перевіряє випадок, коли API повернуло пусту відповідь або None"""
        mock_fetch_detail.return_value = None

        result = scraper.fetch_data("any-slug")

        assert result is None