from typing import List, Dict, Any, Optional
from core.base_scraper import BaseScraper
from scrapers.varus.api_client import VarusApiClient

class VarusScraper(BaseScraper):
    def __init__(self, adapter, media_proxy=None):
        super().__init__(adapter, media_proxy)
        self.adapter.media_proxy = media_proxy

    def discover_slugs(self) -> List[str]:

        # Можеш змінити max_items, щоб тягнути більше товарів
        return VarusApiClient.fetch_all_slugs()

    def fetch_data(self, slug: str) -> Optional[Dict[str, Any]]:

        return VarusApiClient.fetch_detailed_product(slug)