import os
import json
from typing import List, Dict, Any, Optional
from core.base_scraper import BaseScraper
from scrapers.varus.api_client import VarusApiClient

class VarusScraper(BaseScraper):
    def __init__(self, adapter, media_proxy=None):
        super().__init__(adapter, media_proxy)
        self.adapter.media_proxy = media_proxy

        self.cache_file = "cache/varus_slugs.json"


    def discover_slugs(self) -> List[str]:
        if os.path.exists(self.cache_file):
            print(f"📦 Знайдено кеш товарів VARUS: {self.cache_file}")
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    slugs = json.load(f)
                return slugs
            except Exception as e:
                print(f"⚠️ Помилка читання кешу: {e}")
        print("🔍 Кеш не знайдено, починаємо збір слагів Varus...")
        slugs = VarusApiClient.fetch_all_slugs()

        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(slugs, f, ensure_ascii=False, indent=4)
            print(f"💾 Успішно збережено {len(slugs)} товарів у {self.cache_file}")
        except Exception as e:
            print(f"❌ Не вдалося зберегти кеш: {e}")

        return slugs

    def fetch_data(self, slug: str) -> Optional[Dict[str, Any]]:
        return VarusApiClient.fetch_detailed_product(slug)