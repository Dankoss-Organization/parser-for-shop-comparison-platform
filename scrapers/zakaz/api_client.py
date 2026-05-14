import os
import json
import requests
from typing import List, Dict, Any, Optional


class ZakazApiClient:
    def __init__(self, store_id: str, chain_name: str):
        self.store_id = store_id
        self.chain_name = chain_name  # напр. 'novus' або 'auchan'
        self.base_url = f"https://stores-api.zakaz.ua/stores/{self.store_id}"

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Origin": f"https://{self.chain_name}.zakaz.ua",
            "Referer": f"https://{self.chain_name}.zakaz.ua/",
            "x-chain": self.chain_name
        }

        self.cache_dir = os.path.join(os.getcwd(), "cache")
        self.cache_file = os.path.join(self.cache_dir, f"{self.chain_name}_slugs.json")

    def fetch_all_slugs(self) -> List[str]:
        if os.path.exists(self.cache_file):
            print(f"📦 Знайдено кеш товарів {self.chain_name.upper()}: {self.cache_file}")
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    slugs = json.load(f)
                return slugs
            except Exception as e:
                print(f"   ⚠️ Помилка читання кешу: {e}")

        print(f"🔍 [{self.chain_name.upper()}] Починаємо збір товарів...")
        slugs = set()

        try:
            cat_resp = requests.get(f"{self.base_url}/categories/", headers=self.headers, timeout=10)
            cat_resp.raise_for_status()
            categories = cat_resp.json()
        except Exception as e:
            print(f"❌ Помилка завантаження категорій: {e}")
            return []

        for idx, cat in enumerate(categories, 1):
            cat_id = cat.get("id")
            if not cat_id: continue

            print(f"   ⬇️ [{idx}/{len(categories)}] Категорія '{cat_id}'...", end="", flush=True)
            page = 1
            added_in_cat = 0

            while True:
                url = f"{self.base_url}/categories/{cat_id}/products/?page={page}"
                try:
                    resp = requests.get(url, headers=self.headers, timeout=15)
                    if resp.status_code != 200: break

                    results = resp.json().get("results") or []
                    if not results: break

                    start_count = len(slugs)
                    for item in results:
                        product_id = item.get("ean") or item.get("sku")
                        if product_id: slugs.add(str(product_id))

                    if len(slugs) == start_count: break  # Захист від зациклення

                    added_in_cat += (len(slugs) - start_count)
                    page += 1
                except Exception as e:
                    print(f" (помилка: {e})", end="")
                    break

            print(f" Знайдено: {added_in_cat} шт.")

        if slugs:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(list(slugs), f, ensure_ascii=False, indent=4)

        return list(slugs)

    def fetch_detailed_product(self, slug: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/products/{slug}/"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("product")
        except Exception as e:
            pass
        return None