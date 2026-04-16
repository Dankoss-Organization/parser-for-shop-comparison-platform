from core.base_scraper import BaseScraper
from .api_client import ForaApiClient


class ForaScraper(BaseScraper):

    def discover_slugs(self) -> list:

        print(" [ФОРА] Збираємо список товарів з каталогу...")
        slugs = ForaApiClient.fetch_all_slugs(max_pages=2)
        print(f" [ФОРА] Знайдено {len(slugs)} унікальних товарів для обробки.")
        return slugs

    def fetch_data(self, slug):
        raw_json = ForaApiClient.fetch_detailed_product(slug)
        if raw_json and not raw_json.get('EComError', {}).get('ErrorCode'):
            return raw_json
        return None