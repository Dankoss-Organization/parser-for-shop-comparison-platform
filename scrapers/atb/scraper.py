from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from core.base_scraper import BaseScraper
from .api_client import AtbApiClient


class AtbScraper(BaseScraper):
    def __init__(self, adapter, media_proxy):
        super().__init__(adapter, media_proxy)
        self.client = AtbApiClient()
        self.categories = ["siri", "maso", "285-bakaliya"]
        self._products_cache = {}

    def discover_slugs(self, max_pages: int = 2) -> List[str]:
        slugs = []
        for category in self.categories:
            print(f"🔍 Скануємо категорію: {category}...")
            page = 1

            while page <= max_pages:
                print(f"   📥 Завантажуємо сторінку {page}...")
                html = self.client.fetch_catalog_page(category, page)

                if not html:
                    print("   ❌ Не вдалося отримати HTML.")
                    break

                soup = BeautifulSoup(html, 'html.parser')
                items = soup.find_all('article', class_='catalog-item')

                if not items:
                    print("   🏁 Товарів більше немає, категорія закінчилась.")
                    break

                added_on_page = 0
                for item in items:
                    cart_div = item.find('div', class_='b-addToCart')
                    if not cart_div:
                        continue

                    product_id = cart_div.get('data-productid')
                    self._products_cache[product_id] = str(item)
                    slugs.append(product_id)
                    added_on_page += 1

                print(f"   ✅ Знайдено {added_on_page} товарів на сторінці {page}.")
                page += 1

        return slugs

    def fetch_data(self, slug: str) -> Optional[Dict[str, Any]]:
        raw_html = self._products_cache.get(slug)
        if not raw_html:
            return None

        return {"html": raw_html}