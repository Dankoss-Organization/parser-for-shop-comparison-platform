import pytest
import requests
from unittest.mock import patch, MagicMock
from scrapers.fora.api_client import ForaApiClient


class TestForaApiClient:

    # @patch підміняє реальний requests.post у файлі api_client на фейковий (mock_post)
    @patch('scrapers.fora.api_client.requests.post')
    def test_fetch_detailed_product_success(self, mock_post):
        """Перевіряє успішний запит за деталями товару"""
        # 1. Налаштовуємо фейкову відповідь
        mock_response = MagicMock()
        mock_response.json.return_value = {"item": {"id": 123, "name": "Хліб"}}
        mock_response.raise_for_status = MagicMock()  # Імітуємо відсутність помилок HTTP (код 200)
        mock_post.return_value = mock_response

        # 2. Викликаємо наш метод
        result = ForaApiClient.fetch_detailed_product("hlib-123")

        # 3. Перевіряємо результати
        assert result == {"item": {"id": 123, "name": "Хліб"}}
        # Перевіряємо, чи наш клієнт дійсно викликав requests.post один раз
        mock_post.assert_called_once()

    @patch('scrapers.fora.api_client.requests.post')
    def test_fetch_detailed_product_network_error(self, mock_post):
        """Перевіряє, як клієнт реагує на відсутність інтернету або таймаут"""
        # Змушуємо фейковий запит викинути помилку мережі
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        # Перевіряємо, чи клієнт перехоплює цю помилку і викидає свою (з текстом 'Відмова API Фори:')
        with pytest.raises(Exception) as exc_info:
            ForaApiClient.fetch_detailed_product("hlib-123")

        assert "Відмова API Фори: Connection timed out" in str(exc_info.value)

    @patch('scrapers.fora.api_client.requests.post')
    def test_fetch_all_slugs_success(self, mock_post):
        """Перевіряє складний ланцюжок запитів (категорії -> товари)"""
        # 1. Запит за категоріями
        mock_cat_resp = MagicMock()
        mock_cat_resp.json.return_value = {"tree": [{"slug": "cat1"}]}

        # 2. Запит за товарами (Сторінка 1)
        mock_items_page1 = MagicMock()
        mock_items_page1.json.return_value = {
            "items": [{"slug": "item1"}, {"slug": "item2"}],
            "itemsCount": 40  # 🔥 ЗМІНИЛИ З 4 НА 40, щоб код пішов далі (бо 30 < 40)
        }

        # 3. Запит за товарами (Сторінка 2)
        mock_items_page2 = MagicMock()
        mock_items_page2.json.return_value = {
            "items": [{"slug": "item3"}, {"slug": "item4"}],
            "itemsCount": 40
        }

        mock_post.side_effect = [mock_cat_resp, mock_items_page1, mock_items_page2]

        slugs = ForaApiClient.fetch_all_slugs(max_pages=2)

        assert set(slugs) == {"item1", "item2", "item3", "item4"}
        assert mock_post.call_count == 3

    @patch('scrapers.fora.api_client.requests.post')
    def test_fetch_all_slugs_category_fail(self, mock_post):
        """Якщо API категорій впало, клієнт має повернути порожній список і не впасти"""
        mock_post.side_effect = requests.exceptions.ConnectionError("API is down")

        slugs = ForaApiClient.fetch_all_slugs()

        assert slugs == []  # Повертає порожній список, як і написано в блоці except

    @patch('scrapers.fora.api_client.requests.post')
    def test_fetch_all_slugs_partial_data(self, mock_post):
        """Перевірка стійкості, якщо деякі товари в списку не мають slug або itemsCount відсутній"""
        mock_cat_resp = MagicMock()
        mock_cat_resp.json.return_value = {"tree": [{"slug": "cat1"}]}

        mock_items_resp = MagicMock()
        mock_items_resp.json.return_value = {
            "items": [
                {"slug": "valid-item"},
                {"name": "item-without-slug"},  # цей має бути проігнорований
                None  # і цей не має зламати код
            ],
            # itemsCount відсутній (буде None)
        }

        mock_post.side_effect = [mock_cat_resp, mock_items_resp]

        slugs = ForaApiClient.fetch_all_slugs(max_pages=1)

        assert slugs == ["valid-item"]
        assert len(slugs) == 1