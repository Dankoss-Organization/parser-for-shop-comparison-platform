import pytest
from unittest.mock import MagicMock
from scrapers.silpo.adapter import SilpoAdapter


class TestSilpoAdapter:

    @pytest.fixture
    def adapter(self):
        return SilpoAdapter()

    @pytest.fixture
    def mock_media_proxy(self):
        proxy = MagicMock()
        proxy.process_image.return_value = "https://mocked.cloudinary.url/silpo_img.webp"
        return proxy

    def test_normalize_empty_data(self, adapter, mock_media_proxy):
        """Якщо передати порожній словник або None, метод має повернути None"""
        assert adapter.normalize({}, mock_media_proxy) is None
        assert adapter.normalize(None, mock_media_proxy) is None

    def test_normalize_full_product(self, adapter, mock_media_proxy):
        """Перевірка парсингу складного товару Сільпо з атрибутами, категоріями та гуртовими цінами"""
        raw_json = {
            "externalProductId": "886097",
            "title": "Суміш овочева Bauer",
            "slug": "sumish-ovocheva-886097",
            "brandTitle": "Bauer",
            "price": 99.0,
            "oldPrice": 127.0,
            "stock": 10,
            "guestProductRating": 4.7,
            "guestProductRatingCount": 40,
            "displayRatio": "400 г",
            "ratio": "шт",
            "addToBasketStep": 1,
            "isTobacco": False,
            "blurForUnderAged": False,
            "descriptionRich": "Смачна суміш",
            "path": [
                {"title": "Заморожена продукція"},
                {"title": "Овочі і фрукти заморожені"}
            ],
            "attributeGroups": [
                {
                    "attributes": [
                        {"attribute": {"key": "country"}, "value": {"title": "Польща"}},
                        {"attribute": {"key": "calorie"}, "value": {"key": "36/153"}},
                        {"attribute": {"key": "proteins"}, "value": {"title": "1.9"}}
                    ]
                }
            ],
            "promotions": [{"id": "national-cashback"}],
            "promotionsDetails": [{"stopAt": "2026-04-21T00:00:00+00:00"}],
            "specialPrices": [
                {"type": "from", "count": 3, "price": 89.0}
            ],
            "media": [
                "fb656b2d-fefc-46df-9cc2-5cceeb3f553e.png"
            ]
        }

        result = adapter.normalize(raw_json, mock_media_proxy)

        # 1. Базові поля
        assert result["product_id"] == "silpo_886097"
        assert result["canonical_name"] == "Суміш овочева Bauer"
        assert result["brand"] == "Bauer"
        assert result["country"] == "Польща"
        assert result["category"] == "Заморожена продукція > Овочі і фрукти заморожені"

        # 2. Логіка вимірювань та продажу
        assert result["measurements"]["value"] == 400.0
        assert result["measurements"]["unit"] == "g"
        assert result["pricing_logic"]["sales_unit"] == "piece"  # бо ratio == "шт"

        # 3. Ціни та знижки (127 -> 99 це знижка ~22%)
        offer = result["offers"][0]
        assert offer["store_name"] == "Сільпо"
        assert offer["is_in_stock"] is True
        assert offer["pricing"]["current_price"] == 99.0
        assert offer["pricing"]["regular_price"] == 127.0
        assert offer["pricing"]["discount_percent"] == 22
        assert offer["pricing"]["promo_end_date"] == "2026-04-21T00:00:00+00:00"

        # 4. Гуртові знижки (Bulk Discounts)
        assert len(offer["pricing"]["bulk_discounts"]) == 1
        bulk = offer["pricing"]["bulk_discounts"][0]
        assert bulk["discount_type"] == "bulk_price"
        assert bulk["min_quantity"] == 3
        assert bulk["price_per_unit"] == 89.0

        # 5. Специфічні атрибути (БЖВ, Кешбек, Опис)
        spec_attr = result["specific_attributes"]
        assert spec_attr["calories"] == "36/153"
        assert spec_attr["proteins_g"] == "1.9"
        assert spec_attr["is_national_cashback_eligible"] is True
        assert spec_attr["description"] == "Смачна суміш"

        # 6. Медіа
        assert result["media"]["main_image"] == "https://mocked.cloudinary.url/silpo_img.webp"

        # Перевірка, що media_proxy був викликаний з правильним fallback для Сільпо
        mock_media_proxy.process_image.assert_called_with(
            raw_url="https://images.silpo.ua/v2/products/1000x1000/webp/fb656b2d-fefc-46df-9cc2-5cceeb3f553e.png",
            product_sku="silpo_886097",
            suffix="main",
            headers=pytest.approx(mock_media_proxy.process_image.call_args[1]['headers']),
            # Ігноруємо точну перевірку headers тут
            folder_name="silpo_products",
            fallback_replace=("1000x1000/webp/", "")
        )

    def test_normalize_weight_product_no_discount(self, adapter, mock_media_proxy):
        """Перевірка вагового товару без акцій та без гуртових цін"""
        raw_json = {
            "externalProductId": "123",
            "title": "Картопля",
            "price": 25.0,
            "oldPrice": 0,  # Сільпо часто віддає 0 або null для regular price
            "ratio": "кг",
            "displayRatio": "1 кг",
            "attributeGroups": []
        }

        result = adapter.normalize(raw_json, mock_media_proxy)

        assert result["pricing_logic"]["sales_unit"] == "weight"  # бо ratio != "шт"

        offer = result["offers"][0]
        assert offer["pricing"]["current_price"] == 25.0
        assert offer["pricing"]["regular_price"] == 25.0  # Має підтягнути current_price, якщо oldPrice 0
        assert offer["pricing"]["discount_percent"] == 0
        assert len(offer["pricing"]["bulk_discounts"]) == 0

    def test_normalize_nth_item_discount(self, adapter, mock_media_proxy):
        """Специфічний тест для акцій типу 'Кожна друга одиниця зі знижкою'"""
        raw_json = {
            "externalProductId": "999",
            "title": "Піца",
            "price": 100.0,
            "specialPrices": [
                {
                    "type": "every",  # Означає 'кожна N-та'
                    "count": 2,
                    "price": 1.0
                }
            ],
            "ratio": "шт",
            "displayRatio": "1 шт"
        }

        result = adapter.normalize(raw_json, mock_media_proxy)
        bulk = result["offers"][0]["pricing"]["bulk_discounts"]

        assert len(bulk) == 1
        assert bulk[0]["discount_type"] == "nth_item_discount"
        assert bulk[0]["min_quantity"] == 2
        assert bulk[0]["price_for_nth_item"] == 1.0
        assert "Кожна 2-тя одиниця за 1.0 грн" in bulk[0]["description"]

    def test_normalize_online_only_flag(self, adapter, mock_media_proxy):
        """Перевіряє, чи правильно розпізнається товар, який доступний ТІЛЬКИ онлайн"""
        raw_json = {
            "externalProductId": "444",
            "title": "Ексклюзивний товар",
            "price": 500.0,
            "promotions": [
                {"id": "only_online"}  # Мітка Сільпо для онлайн-товарів
            ]
        }

        result = adapter.normalize(raw_json, mock_media_proxy)
        assert result["offers"][0]["pricing"]["is_online_only"] is True