from core.base_scraper import BaseScraper
from .api_client import SilpoApiClient

class SilpoScraper(BaseScraper):
    def discover_slugs(self) -> list:
        return SilpoApiClient.fetch_all_slugs(max_pages=2)

    def fetch_data(self, slug):
        return SilpoApiClient.fetch_detailed_product(slug)