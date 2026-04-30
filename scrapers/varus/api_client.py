import requests
import json
from typing import List, Dict, Any, Optional


class VarusApiClient:
    """
    HTTP-клієнт для взаємодії з API Varus (Vue Storefront / Elasticsearch).
    Відповідає за збір списку товарів (Discovery) та отримання деталей конкретного товару.
    """

    SHOP_ID = "130694"
    BASE_URL = "https://varus.ua/api/catalog/vue_storefront_catalog_2/product_v2/_search"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    @staticmethod
    def fetch_all_slugs(category_id: int = 52866, max_items: int = 50) -> List[str]:
        print("🔍 [VARUS] Починаємо збір загального списку товарів (Discovery Phase)...")

        payload = {
            "_availableFilters": [],
            "_appliedFilters": [
                {"attribute": "category_ids", "value": {"eq": category_id}, "scope": "default"},
                {"attribute": "sqpp_data_region_1.in_stock", "value": {"eq": True}, "scope": "default"}
            ],
            "_searchText": ""
        }

        params = {
            "_source_include": "url_key",
            "from": 0,
            "size": max_items,
            "shop_id": VarusApiClient.SHOP_ID,
            "request": json.dumps(payload),
            "request_format": "search-query",
            "response_format": "compact"
        }

        slugs = []
        try:
            response = requests.get(VarusApiClient.BASE_URL, params=params, headers=VarusApiClient.HEADERS, timeout=10)
            response.raise_for_status()

            data = response.json()
            items = []

            # Захищена перевірка будь-якої структури JSON
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                hits_outer = data.get("hits", [])
                if isinstance(hits_outer, list):
                    items = hits_outer  # Формат {"hits": [...]}
                elif isinstance(hits_outer, dict):
                    items = hits_outer.get("hits", [])  # Формат {"hits": {"hits": [...]}}

            for item in items:
                if not isinstance(item, dict):
                    continue

                source = item.get("_source", item)
                if isinstance(source, dict) and "url_key" in source:
                    slugs.append(source["url_key"])

            print(f"   📥 Зібрано {len(slugs)} товарів для обробки.")

            if not slugs:
                # Якщо нічого не знайдено, виводимо шматок відповіді для дебагу
                print(f"   ⚠️ Слизняки не знайдено. Відповідь сервера: {str(data)[:200]}...")

        except Exception as e:
            print(f"⚠️ Помилка API Varus при зборі списку: {e}")

        return list(set(slugs))

    @staticmethod
    def fetch_detailed_product(slug: str) -> Optional[Dict[str, Any]]:
        payload = {
            "_availableFilters": [],
            "_appliedFilters": [
                {"attribute": "url_key", "value": {"eq": slug}, "scope": "default"}
            ],
            "_searchText": ""
        }

        params = {
            "from": 0,
            "size": 1,
            "shop_id": VarusApiClient.SHOP_ID,
            "request": json.dumps(payload),
            "request_format": "search-query",
            "response_format": "compact"
        }

        try:
            response = requests.get(VarusApiClient.BASE_URL, params=params, headers=VarusApiClient.HEADERS, timeout=10)
            response.raise_for_status()

            data = response.json()
            items = []

            # Така ж захищена перевірка для деталей товару
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                hits_outer = data.get("hits", [])
                if isinstance(hits_outer, list):
                    items = hits_outer
                elif isinstance(hits_outer, dict):
                    items = hits_outer.get("hits", [])

            if items and isinstance(items[0], dict):
                return items[0].get("_source", items[0])

        except Exception as e:
            print(f"⚠️ Відмова API Varus (деталі товару {slug}): {e}")

        return None