"""
Unit tests for the db_manager module.

Verifies the correct initialization of the database session generator
and ensures that database connections are properly opened and safely closed.
"""

import pytest
from unittest.mock import patch, MagicMock
from database.db_manager import get_db


class TestDBManager:
    """
    Test suite for database connection utilities.
    """

    @patch('database.db_manager.SessionLocal')
    def test_get_db_yields_session_and_closes(self, mock_session_local):
        """
        Tests the get_db generator function.

        Ensures that a session is yielded for database operations and
        that the session is securely closed in the finally block after use,
        preventing connection leaks.

        Args:
            mock_session_local (MagicMock): Mocked SQLAlchemy sessionmaker.
        """
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Отримуємо генератор
        db_generator = get_db()

        # Робимо перший крок (yield)
        db = next(db_generator)

        # Перевіряємо, що повернулася правильна сесія, і вона ще не закрита
        assert db == mock_session
        mock_session.close.assert_not_called()

        # Імітуємо завершення роботи з базою (спрацьовує блок finally)
        with pytest.raises(StopIteration):
            next(db_generator)

        # Найважливіша перевірка: чи закрилася сесія після використання
        mock_session.close.assert_called_once()