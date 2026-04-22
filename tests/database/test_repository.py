"""
Unit tests for the database Repository class.

This module provides a suite of tests for the repository layer, using
`unittest.mock.MagicMock` to isolate the repository logic from the actual
SQLAlchemy database session. It verifies querying, updating, and inserting
logic for products and offers without requiring a live database connection.
"""

import pytest
from unittest.mock import MagicMock, patch
from database.repository import Repository
# Importing classes specifically in case they need to be passed as specs to mocks
from database.models import Product, Offer


class TestRepository:
    """
    Test suite for the Repository methods.

    Validates the interactions between the repository layer and the
    database session, ensuring correct SQLAlchemy query chaining,
    data updates, and transaction commits using mocked environments.
    """

    @pytest.fixture
    def mock_db(self):
        """
        Creates a mock SQLAlchemy database session.

        Returns:
            MagicMock: A mocked database session object.
        """
        return MagicMock()

    @pytest.fixture
    def repository(self, mock_db):
        """
        Initializes the Repository with a mocked database session.

        Args:
            mock_db (MagicMock): The mocked database session provided by the fixture.

        Returns:
            Repository: An instance of the repository using the mock session.
        """
        return Repository(db=mock_db)

    def test_find_offer_by_store_sku(self, repository, mock_db):
        """
        Tests retrieving an offer by its store SKU using a pure Mock.

        Simulates the SQLAlchemy query chain (`query().filter().first()`)
        and verifies that the repository correctly returns the mocked offer.

        Args:
            repository (Repository): The repository instance under test.
            mock_db (MagicMock): The mocked database session.
        """
        # Using a pure Mock instead of a real Offer class instance
        mock_offer = MagicMock()
        mock_offer.id = "123"
        mock_offer.store_sku = "sku_99"

        # Simulating the behavior of session.query(Offer).filter(...).first()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_offer

        result = repository.find_offer_by_store_sku("sku_99")

        assert result.id == "123"
        assert result.store_sku == "sku_99"

    def test_update_offer_price_success(self, repository, mock_db):
        """
        Tests successfully updating the price of an existing offer.

        Simulates an offer object without instantiating the actual class,
        verifies that the `current_price` attribute is updated, and ensures
        that the database transaction is committed.

        Args:
            repository (Repository): The repository instance under test.
            mock_db (MagicMock): The mocked database session.
        """
        # Simulating an offer without creating a class instance
        mock_offer = MagicMock()
        mock_offer.id = "123"
        mock_offer.current_price = 10.0

        mock_db.query.return_value.filter.return_value.first.return_value = mock_offer

        result = repository.update_offer_price("123", 15.5)

        assert result.current_price == 15.5
        mock_db.commit.assert_called_once()

    def test_find_products_by_brand_and_weight(self, repository, mock_db):
        """
        Tests filtering products by brand and weight using mocked data.

        Simulates multiple product records returned from the database and
        verifies that the repository correctly filters them based on the
        nested `measurements` dictionary.

        Args:
            repository (Repository): The repository instance under test.
            mock_db (MagicMock): The mocked database session.
        """
        # Testing filtering on pure mocks
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

    @patch('database.repository.Product')  # Mocking the actual Product CLASS in the repository
    def test_create_product(self, mock_product_class, repository, mock_db):
        """
        Tests the creation of a new product and its insertion into the database.

        Uses `unittest.mock.patch` to replace the `Product` model class within
        the repository file. This ensures that when `Product(...)` is called,
        a Mock is created instead of a real SQLAlchemy model object.

        Args:
            mock_product_class (MagicMock): The mocked Product class constructor.
            repository (Repository): The repository instance under test.
            mock_db (MagicMock): The mocked database session.
        """
        unified_item = {
            "product_id": "test_id",
            "canonical_name": "Test",
            "specific_attributes": {}
        }

        with patch('database.repository.uuid.uuid4', return_value='fixed-uuid'):
            repository.create_product(unified_item)

        # Verifying that an attempt was made to add and commit the item to the database
        assert mock_db.add.called
        assert mock_db.commit.called

    def test_create_offer_update_existing(self, repository, mock_db):
        """
        Tests updating an existing offer during the creation process.

        If an offer for the same product and store already exists, the repository
        should update its price instead of attempting to insert a duplicate row.

        Args:
            repository (Repository): The repository instance under test.
            mock_db (MagicMock): The mocked database session.
        """
        # Updating an existing offer through a Mock
        mock_existing = MagicMock()
        mock_existing.id = "old_id"
        mock_existing.current_price = 50.0

        mock_db.query.return_value.filter.return_value.first.return_value = mock_existing

        offer_data = {"pricing": {"current_price": 60.0}}
        res_id = repository.create_offer("prod_1", offer_data, "sku_1")

        assert res_id == "old_id"
        assert mock_existing.current_price == 60.0
        mock_db.commit.assert_called()