from core.base_scraper import BaseScraper
from .api_client import ForaApiClient

class ForaScraper(BaseScraper):
    def fetch_data(self, slug):
        raw_json = ForaApiClient.fetch_detailed_product(slug)
        if raw_json and not raw_json.get('EComError', {}).get('ErrorCode'):
            return raw_json
        return None