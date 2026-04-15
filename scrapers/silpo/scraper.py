from core.base_scraper import BaseScraper
from .api_client import SilpoApiClient

class SilpoScraper(BaseScraper):
    def fetch_data(self, slug):
        return SilpoApiClient.fetch_detailed_product(slug)
    