import pytest
from core.factory import ParserFactory
from scrapers.silpo.scraper import SilpoScraper
from scrapers.fora.scraper import ForaScraper


class TestParserFactory:

    def test_factory_creates_silpo_scraper(self):
        """Перевіряє правильне створення парсера для Сільпо"""
        scraper = ParserFactory.create_scraper("silpo")
        # assert isinstance перевіряє, чи дійсно об'єкт належить до вказаного класу
        assert isinstance(scraper, SilpoScraper)

    def test_factory_creates_fora_scraper(self):
        """Перевіряє правильне створення парсера для Фори"""
        scraper = ParserFactory.create_scraper("fora")
        assert isinstance(scraper, ForaScraper)

    def test_factory_raises_error_for_unknown_store(self):
        """Перевіряє, що фабрика безпечно 'падає' при невідомому магазині"""
        with pytest.raises(ValueError) as exc_info:
            ParserFactory.create_scraper("atb")

        # Перевіряємо не тільки сам факт помилки, а й текст повідомлення
        assert "Магазин atb не підтримується" in str(exc_info.value)

    def test_factory_is_case_sensitive(self):
        """Перевіряє, що фабрика сувора до регістру (захист від помилок у назві)"""
        with pytest.raises(ValueError) as exc_info:
            ParserFactory.create_scraper("SILPO")  # Має бути написано тільки маленькими

        assert "Магазин SILPO не підтримується" in str(exc_info.value)