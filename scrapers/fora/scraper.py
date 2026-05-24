import os
import json
from typing import List, Dict, Any, Optional
from core.base_scraper import BaseScraper
from .api_client import ForaApiClient


class ForaScraper(BaseScraper):
    """
    A concrete scraper implementation for the 'Fora' supermarket chain.

    This class inherits from `BaseScraper` and fulfills the required Template Method
    contracts (`discover_slugs` and `fetch_data`). It acts as the orchestrator
    for Fora-specific data extraction, utilizing the `ForaApiClient` to communicate
    with the store's backend APIs.
    """
    CACHE_FILE = "cache/fora_slugs.json"

    def discover_slugs(self) -> List[str]:
        """
        Discovers product slugs. Uses local file cache to prevent
        re-fetching the entire catalog on every run.
        """
        if os.path.exists(self.CACHE_FILE):
            print(f"📦 [ФОРА] Знайдено локальний кеш! Завантажуємо слаги з {self.CACHE_FILE}...")
            with open(self.CACHE_FILE, "r", encoding="utf-8") as f:
                slugs = json.load(f)
                print(f"   ✅ Завантажено {len(slugs)} товарів з кешу.")
                return slugs

        print("🔍 [ФОРА] Кеш не знайдено. Починаємо збір з API (Discovery Phase)...")
        slugs = ForaApiClient.fetch_all_slugs(max_pages=9999)

        os.makedirs(os.path.dirname(self.CACHE_FILE), exist_ok=True)
        with open(self.CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(slugs, f, ensure_ascii=False, indent=2)

        print(f"💾 [ФОРА] Успішно збережено {len(slugs)} товарів у {self.CACHE_FILE}")
        return slugs

    def fetch_data(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the complete raw metadata for a specific Fora product.
        """
        raw_json = ForaApiClient.fetch_detailed_product(slug)

        if raw_json and not raw_json.get('EComError', {}).get('ErrorCode'):
            return raw_json

        return None

    def fetch_data(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the raw, detailed JSON data for a specific Fora product.

        This method requests the complete metadata for a single item using its slug.
        Crucially, it includes an error-handling layer specific to Fora's API:
        Even if the HTTP status code is 200 (OK), the Fora API might return an
        internal error inside the JSON payload under the 'EComError' key. This
        method validates the absence of such application-level errors before
        returning the data.

        Args:
            slug (str): The specific product identifier (e.g., "kava-zernova-123").

        Returns:
            Optional[Dict[str, Any]]: The raw JSON dictionary containing the
            product details if the request is successful and error-free. Returns
            `None` if the API returns an application-level error.
        """
        raw_json = ForaApiClient.fetch_detailed_product(slug)

        # Validate that the response is not empty and does not contain internal API errors
        if raw_json and not raw_json.get('EComError', {}).get('ErrorCode'):
            return raw_json

        return None