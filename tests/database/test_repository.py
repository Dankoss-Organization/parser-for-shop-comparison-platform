import pytest
from unittest.mock import MagicMock, patch
from database.repository import Repository
# Імпортуємо класи тільки для того, щоб передати їх у spec
from database.models import Product, Offer

class TestRepository:

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def repository(self, mock_db):
        return Repository(db=mock_db)

    def test_find_offer_by_store_sku(self, repository, mock_db):
        """Використовуємо чистий Mock замість реального класу Offer"""
        mock_offer = MagicMock()
        mock_offer.id = "123"
        mock_offer.store_sku = "sku_99"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_offer

        result = repository.find_offer_by_store_sku("sku_99")

        assert result.id == "123"
        assert result.store_sku == "sku_99"

    def test_update_offer_price_success(self, repository, mock_db):
        """Імітуємо оффер без створення екземпляра класу"""
        mock_offer = MagicMock()
        mock_offer.id = "123"
        mock_offer.current_price = 10.0

        mock_db.query.return_value.filter.return_value.first.return_value = mock_offer

        result = repository.update_offer_price("123", 15.5)

        assert result.current_price == 15.5
        mock_db.commit.assert_called_once()

    def test_find_products_by_brand_and_weight(self, repository, mock_db):
        """Тестуємо фільтрацію на чистих моках"""
        p1 = MagicMock()
        p1.brand = "Milka"
        p1.measurements = {"value": 100}

        p2 = MagicMock()
        p2.brand = "Milka"
        p2.measurements = {"value": 300}

        mock_db.query.return_value.filter.return_value.all.return_value = [p1, p2]

        results = repository.find_products_by_brand_and_weight("Milka", 300.0)

        assert len(results) == 1
        assert results[0].measurements["value"] == 300

    @patch('database.repository.Product')  # Підміняємо сам КЛАС Product у репозиторії
    def test_create_product(self, mock_product_class, repository, mock_db):
        """
        Тут ми йдемо на хитрість: підміняємо клас Product усередині repository.py,
        щоб при виклику Product(...) створювався Mock, а не реальний об'єкт.
        """
        unified_item = {
            "product_id": "test_id",
            "canonical_name": "Test",
            "specific_attributes": {}
        }

        with patch('database.repository.uuid.uuid4', return_value='fixed-uuid'):
            repository.create_product(unified_item)

        # Перевіряємо, що ми хоча б намагалися щось додати в базу
        assert mock_db.add.called
        assert mock_db.commit.called

    def test_create_offer_update_existing(self, repository, mock_db):
        """Оновлення існуючого оффера через Mock"""
        mock_existing = MagicMock()
        mock_existing.id = "old_id"
        mock_existing.current_price = 50.0

        mock_db.query.return_value.filter.return_value.first.return_value = mock_existing

        offer_data = {"pricing": {"current_price": 60.0}}
        res_id = repository.create_offer("prod_1", offer_data, "sku_1")

        assert res_id == "old_id"
        assert mock_existing.current_price == 60.0
        mock_db.commit.assert_called()