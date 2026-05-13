from typing import List, Dict, Any, Optional
from core.base_scraper import BaseScraper
from scrapers.zakaz.api_client import ZakazApiClient

class ZakazScraper(BaseScraper):
    def __init__(self, api_client: ZakazApiClient, adapter: Any, media_proxy: Any = None):
        # Передаємо ТІЛЬКИ адаптер та проксі, як того вимагає BaseScraper
        super().__init__(adapter, media_proxy)
        self.api_client = api_client

    def discover_slugs(self) -> List[str]:
        return self.api_client.fetch_all_slugs()

    def fetch_data(self, slug: str) -> Optional[Dict[str, Any]]:
        return self.api_client.fetch_detailed_product(slug)