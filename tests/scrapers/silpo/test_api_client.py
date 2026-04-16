import pytest
import requests
from unittest.mock import patch, MagicMock
from scrapers.silpo.api_client import SilpoApiClient


class TestSilpoApiClient:

    @patch('scrapers.silpo.api_client.requests.get')
    def test_fetch_detailed_product_success(self, mock_get):
        """Перевірка успішного отримання деталей товару Сільпо"""
        # Налаштовуємо фейкову відповідь від Сільпо
        mock_response = MagicMock()
        mock_response.json.return_value = {"title": "Банан", "externalProductId": "123"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = SilpoApiClient.fetch_detailed_product("banan-123")

        assert result["title"] == "Банан"
        # Перевіряємо, чи був викликаний саме GET запит
        mock_get.assert_called_once()

    @patch('scrapers.silpo.api_client.requests.get')
    def test_fetch_detailed_product_error(self, mock_get):
        """Перевірка обробки помилки (наприклад, 404 або таймаут)"""
        mock_get.side_effect = requests.exceptions.HTTPError("404 Not Found")

        with pytest.raises(Exception) as exc_info:
            SilpoApiClient.fetch_detailed_product("unknown-slug")

        assert "Відмова API Сільпо" in str(exc_info.value)

    @patch('scrapers.silpo.api_client.requests.get')
    def test_fetch_all_slugs_pagination(self, mock_get):
        """Перевірка збору списку товарів (Discovery) з імітацією двох сторінок"""

        # Відповідь для 1-ї сторінки (2 товари)
        mock_resp_p1 = MagicMock()
        mock_resp_p1.json.return_value = {
            "items": [{"slug": "apple"}, {"slug": "pear"}]
        }

        # Відповідь для 2-ї сторінки (1 товар)
        mock_resp_p2 = MagicMock()
        mock_resp_p2.json.return_value = {
            "items": [{"slug": "orange"}]
        }

        # Налаштовуємо черговість відповідей
        mock_get.side_effect = [mock_resp_p1, mock_resp_p2]

        # Викликаємо метод (максимум 2 сторінки)
        slugs = SilpoApiClient.fetch_all_slugs(max_pages=2)

        # Перевіряємо, чи всі 3 унікальні товари зібрані
        assert len(slugs) == 3
        assert "apple" in slugs
        assert "orange" in slugs
        assert mock_get.call_count == 2

    @patch('scrapers.silpo.api_client.requests.get')
    def test_fetch_all_slugs_empty_stop(self, mock_get):
        """Перевірка зупинки циклу, якщо товари закінчилися раніше max_pages"""
        mock_resp_empty = MagicMock()
        mock_resp_empty.json.return_value = {"items": []}
        mock_get.return_value = mock_resp_empty

        slugs = SilpoApiClient.fetch_all_slugs(max_pages=5)

        # Незважаючи на ліміт у 5 сторінок, має бути лише 1 виклик, бо items порожній
        assert slugs == []
        assert mock_get.call_count == 1