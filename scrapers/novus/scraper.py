from typing import List, Dict, Any, Optional
from core.base_scraper import BaseScraper
from scrapers.novus.api_client import NovusApiClient

class NovusScraper(BaseScraper):
    """
    Парсер для мережі Novus (через API zakaz.ua).
    Використовує шаблонний метод з BaseScraper.
    """

    # ФІКС: Змінили назву методу на ту, яку очікує BaseScraper
    def discover_slugs(self) -> List[str]:
        return NovusApiClient.fetch_all_slugs()

    def fetch_data(self, slug: str) -> Optional[Dict[str, Any]]:
        return NovusApiClient.fetch_detailed_product(slug)