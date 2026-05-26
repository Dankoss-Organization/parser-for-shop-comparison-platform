import os
import json
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from core.base_scraper import BaseScraper
from .api_client import AtbApiClient


class AtbScraper(BaseScraper):
    def __init__(self, adapter, media_proxy):
        super().__init__(adapter, media_proxy)
        self.client = AtbApiClient()
        self.categories = [
            "287-ovochi-ta-frukti",
            "285-bakaliya",
            "molocni-produkti-ta-ajca",
            "siri",
            "maso",
            "360-kovbasa-i-m-yasni-delikatesi",
            "353-riba-i-moreprodukti",
            "299-konditers-ki-virobi",
            "325-khlibobulochni-virobi",
            "322-zamorozheni-produkti",
            "kava-caj",
            "cipsi-sneki",
            "294-napoi-bezalkogol-ni",
            "292-alkogol-i-tyutyun",
            "502-kulinariya",
            "415-yapons-ka-kukhnya",
            "339-dityache-kharchuvannya"
        ]
        self.cache_file = "cache/atb_slugs.json"

    def discover_slugs(self) -> List[str]:
        os.makedirs("cache", exist_ok=True)

        if os.path.exists(self.cache_file):
            print("📦 Завантажуємо слаги АТБ з кешу...")
            with open(self.cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

        print("🔍 Починаємо глобальне сканування категорій АТБ...")
        slugs_set = set()

        for category in self.categories:
            print(f"📁 Скануємо категорію: {category}...")
            page = 1
            previous_page_slugs = set()

            while True:
                html = self.client.fetch_catalog_page(category, page)
                if not html:
                    print("   ❌ HTML порожній, переходимо до наступної категорії.")
                    break

                soup = BeautifulSoup(html, 'html.parser')
                items = soup.find_all('article', class_='catalog-item')

                if not items:
                    print(f"   🏁 Товарів більше немає (сторінка {page}), категорія закінчилась.")
                    break

                current_page_slugs = set()
                added_on_page = 0

                for item in items:
                    title_elem = item.find('div', class_='catalog-item__title')
                    if not title_elem:
                        continue

                    url_elem = title_elem.find('a')
                    if url_elem and 'href' in url_elem.attrs:
                        product_url = url_elem['href']
                        current_page_slugs.add(product_url)
                        slugs_set.add(product_url)
                        added_on_page += 1

                if current_page_slugs == previous_page_slugs:
                    print(f"   🏁 Сторінки почали дублюватися. Кінець категорії {category}.")
                    break

                previous_page_slugs = current_page_slugs

                print(f"   ✅ Сторінка {page}: знайдено {added_on_page} товарів.")
                page += 1

        slugs_list = list(slugs_set)
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(slugs_list, f, ensure_ascii=False, indent=4)

        print(f"🎉 Сканування завершено! Знайдено унікальних товарів: {len(slugs_list)}")
        return slugs_list

    def fetch_data(self, slug: str) -> Optional[Dict[str, Any]]:
        html = self.client.fetch_product_page(slug)
        if not html:
            return None

        return {
            "html": html,
            "url_slug": slug
        }