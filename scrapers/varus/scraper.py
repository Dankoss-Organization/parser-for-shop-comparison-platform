from typing import List, Dict, Any, Optional
from core.base_scraper import BaseScraper
from scrapers.varus.api_client import VarusApiClient

class VarusScraper(BaseScraper):
    """
    Реалізація скрейпера для супермаркету Varus.
    Використовує шаблонний метод BaseScraper для проходження повного циклу.
    """

    def discover_slugs(self) -> List[str]:
        """
        Крок 1: Збирає список ідентифікаторів (url_key) товарів через API клієнт.
        """
        # Можеш змінити max_items, щоб тягнути більше товарів
        return VarusApiClient.fetch_all_slugs(max_items=100)

    def fetch_data(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Крок 2: Завантажує сирі дані конкретного товару для передачі в Адаптер.
        """
        return VarusApiClient.fetch_detailed_product(slug)