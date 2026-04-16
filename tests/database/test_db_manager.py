"""
Unit tests for the DatabaseManager class.

This module ensures that database connection initialization, data upsertion
(insert/update), and query retrieval function correctly. It utilizes the
`unittest.mock` library to simulate database sessions and transactions,
allowing tests to run safely without requiring a live database connection.
"""

import pytest
from unittest.mock import patch, MagicMock
from database.db_manager import DatabaseManager
from database.models import Product, PriceHistory


class TestDatabaseManager:
    """
    Test suite for the DatabaseManager class.

    This class groups all unit tests related to database operations, verifying
    environment variable validation, session management, transaction commits,
    and error rollback mechanisms.
    """

    @pytest.fixture
    def mock_product_data(self):
        """
        A fixture providing a standard dictionary of scraped product data.

        Returns:
            dict: A mock product payload mimicking the scraper's output.
        """
        return {
            "product_id": "test_123",
            "canonical_name": "Test Chocolate",
            "brand": "TestBrand",
            "category": "Snacks",
            "country": "Ukraine",
            "media": {"main_image": "https://example.com/image.png"},
            "offers": [
                {
                    "pricing": {
                        "current_price": 45.0,
                        "regular_price": 50.0
                    },
                    "scraped_at": "2026-04-16T12:00:00Z"
                }
            ]
        }

    @patch("database.db_manager.os.getenv")
    def test_init_missing_database_url(self, mock_getenv):
        """
        Tests the initialization guard against missing environment variables.

        Verifies that instantiating the DatabaseManager raises a ValueError
        if the 'DATABASE_URL' is not found in the environment setup.
        """
        mock_getenv.return_value = None

        with pytest.raises(ValueError) as exc_info:
            DatabaseManager()

        assert "DATABASE_URL" in str(exc_info.value)

    @patch("database.db_manager.sessionmaker")
    @patch("database.db_manager.create_engine")
    @patch("database.db_manager.os.getenv")
    def test_init_success(self, mock_getenv, mock_create_engine, mock_sessionmaker):
        """
        Tests the successful initialization of the database engine and session factory.

        Ensures that the engine is created with the correct URL and that
        the session factory is successfully bound to the engine.
        """
        mock_getenv.return_value = "postgresql+psycopg2://user:pass@localhost/db"

        manager = DatabaseManager()

        assert manager.db_url == "postgresql+psycopg2://user:pass@localhost/db"
        mock_create_engine.assert_called_once_with(manager.db_url, pool_pre_ping=True)
        mock_sessionmaker.assert_called_once()

    @patch("database.db_manager.create_engine")
    @patch("database.db_manager.os.getenv")
    def test_upsert_new_product(self, mock_getenv, mock_create_engine, mock_product_data):
        """
        Tests the insertion logic for a completely new product.

        Simulates a scenario where the product does not exist in the database.
        Verifies that both a new Product instance and a PriceHistory instance
        are created, added to the session, and successfully committed.
        """
        mock_getenv.return_value = "sqlite:///:memory:"
        manager = DatabaseManager()

        # Mock the database session and query
        mock_session = MagicMock()
        manager.SessionLocal = MagicMock(return_value=mock_session)
        mock_session.query().filter().first.return_value = None  # Product not found

        manager.upsert_product(mock_product_data)

        # Assertions
        assert mock_session.add.call_count == 2  # Once for Product, once for PriceHistory
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("database.db_manager.create_engine")
    @patch("database.db_manager.os.getenv")
    def test_upsert_existing_product(self, mock_getenv, mock_create_engine, mock_product_data):
        """
        Tests the update (upsert) logic for an existing product.

        Simulates a scenario where the product already exists. Verifies that
        the existing product's attributes are updated, a new PriceHistory
        entry is created, and the transaction is committed without inserting
        a duplicate product row.
        """
        mock_getenv.return_value = "sqlite:///:memory:"
        manager = DatabaseManager()

        # Create a fake existing product
        existing_product = MagicMock()
        existing_product.product_id = "test_123"
        existing_product.current_price = 40.0

        mock_session = MagicMock()
        manager.SessionLocal = MagicMock(return_value=mock_session)
        mock_session.query().filter().first.return_value = existing_product  # Product found

        manager.upsert_product(mock_product_data)

        # Assertions: We only add PriceHistory (1 call), because Product is updated in place
        assert mock_session.add.call_count == 1
        assert existing_product.current_price == 45.0  # Verify price updated
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("database.db_manager.create_engine")
    @patch("database.db_manager.os.getenv")
    def test_upsert_transaction_rollback_on_error(self, mock_getenv, mock_create_engine, mock_product_data):
        """
        Tests the transaction rollback mechanism during a database failure.

        Forces a simulated database exception during the commit phase.
        Verifies that the session correctly rolls back the transaction to
        prevent data corruption and safely closes the session.
        """
        mock_getenv.return_value = "sqlite:///:memory:"
        manager = DatabaseManager()

        mock_session = MagicMock()
        manager.SessionLocal = MagicMock(return_value=mock_session)

        # Force the commit to fail
        mock_session.commit.side_effect = Exception("Simulated Database Error")

        with pytest.raises(Exception) as exc_info:
            manager.upsert_product(mock_product_data)

        assert "Simulated Database Error" in str(exc_info.value)
        mock_session.rollback.assert_called_once()  # CRITICAL: Ensures data safety
        mock_session.close.assert_called_once()

    @patch("database.db_manager.create_engine")
    @patch("database.db_manager.os.getenv")
    def test_get_all_products(self, mock_getenv, mock_create_engine):
        """
        Tests the retrieval of all products from the database.

        Verifies that the session queries the Product model correctly
        and safely closes the connection afterward.
        """
        mock_getenv.return_value = "sqlite:///:memory:"
        manager = DatabaseManager()

        mock_session = MagicMock()
        manager.SessionLocal = MagicMock(return_value=mock_session)

        # Mock the returned data
        mock_session.query().all.return_value = ["Product1", "Product2"]

        results = manager.get_all_products()

        assert results == ["Product1", "Product2"]
        mock_session.query.assert_called_once_with(Product)
        mock_session.close.assert_called_once()