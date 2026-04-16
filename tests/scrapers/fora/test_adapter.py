import pytest
from unittest.mock import MagicMock
from scrapers.fora.adapter import ForaAdapter


class TestForaAdapter:

    @pytest.fixture
    def adapter(self):
        """Фікстура, яка створює екземпляр адаптера перед кожним тестом"""
        return ForaAdapter()

    @pytest.fixture
    def mock_media_proxy(self):
        """Створюємо фейковий media_proxy, щоб не робити реальних запитів у Cloudinary"""
        proxy = MagicMock()
        # Вказуємо, що при виклику process_image він завжди має повертати цей рядок:
        proxy.process_image.return_value = "https://mocked.cloudinary.url/image.png"
        return proxy

    def test_normalize_empty_data(self, adapter, mock_media_proxy):
        """Якщо API повернуло порожній словник або немає ключа 'item', повертаємо None"""
        assert adapter.normalize({}, mock_media_proxy) is None
        assert adapter.normalize({"error": "not found"}, mock_media_proxy) is None

    def test_normalize_full_product(self, adapter, mock_media_proxy):
        """Тест повноцінного товару з усіма полями, знижкою та кешбеком"""
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

        # 1. Базові поля
        assert result["product_id"] == "fora_523478"
        assert result["canonical_name"] == "Шоколад молочний Milka Bubbles"
        assert result["brand"] == "Milka"
        assert result["country"] == "Україна"
        assert result["category"] == "Шоколад, плитка"

        # 2. Логіка ціни та знижки (89.9 -> 64.9 це знижка ~28%)
        offer = result["offers"][0]
        assert offer["store_name"] == "Фора"
        assert offer["is_in_stock"] is True
        assert offer["pricing"]["current_price"] == 64.9
        assert offer["pricing"]["regular_price"] == 89.9
        assert offer["pricing"]["discount_percent"] == 28

        # 3. Специфічні атрибути (Кешбек)
        assert result["specific_attributes"]["calories"] == "532/2225"
        assert result["specific_attributes"]["is_national_cashback_eligible"] is True

        # 4. Перевірка ваги (має відпрацювати наш протестований BaseAdapter)
        assert result["measurements"]["value"] == 80.0
        assert result["measurements"]["unit"] == "g"

        # 5. Перевірка картинок (має підставитися фейк з нашого mock_media_proxy)
        assert result["media"]["main_image"] == "https://mocked.cloudinary.url/image.png"

    def test_normalize_regular_price_no_discount(self, adapter, mock_media_proxy):
        """Перевірка логіки, коли товар без акції (oldPrice відсутній або менший)"""
        raw_json = {
            "item": {
                "id": 111,
                "name": "Хліб",
                "price": 25.0,
                # oldPrice немає
            }
        }

        result = adapter.normalize(raw_json, mock_media_proxy)
        offer = result["offers"][0]

        assert offer["pricing"]["current_price"] == 25.0
        assert offer["pricing"]["regular_price"] == 25.0
        assert offer["pricing"]["discount_percent"] == 0

    def test_normalize_missing_parameters_and_bubbles(self, adapter, mock_media_proxy):
        """Перевірка стійкості (захист від NoneType), якщо API не прислало масиви"""
        raw_json = {
            "item": {
                "id": 222,
                "name": "Товар без інфи",
                "parameters": None,  # Може бути None замість []
                "bubbles": None,
                "category": None
            }
        }

        # Якщо код не впаде з помилкою NoneType, значить тест пройдено
        result = adapter.normalize(raw_json, mock_media_proxy)

        assert result["brand"] is None
        assert result["category"] == "Невідома категорія"
        assert result["specific_attributes"]["is_national_cashback_eligible"] is False