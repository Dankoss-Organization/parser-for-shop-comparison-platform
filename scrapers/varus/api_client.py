import os
import json
import requests
from typing import List, Dict, Any, Optional


class VarusApiClient:
    SHOP_ID = "130551"
    BASE_URL_SEARCH = "https://varus.ua/api/catalog/vue_storefront_catalog_2/product_v2/_search"
    BASE_URL_GRAPHQL = "https://ai.esputnik.com/graphql"

    HEADERS_SEARCH = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    HEADERS_GRAPHQL = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://varus.ua",
        "Referer": "https://varus.ua/"
    }

    # Шлях до файлу кешу (створиться папка cache біля main.py)
    CACHE_DIR = os.path.join(os.getcwd(), "cache")
    CACHE_FILE = os.path.join(CACHE_DIR, "varus_slugs.json")

    @staticmethod
    def fetch_all_slugs() -> List[str]:
        # ==========================================
        # 1. ПЕРЕВІРКА КЕШУ
        # ==========================================
        if os.path.exists(VarusApiClient.CACHE_FILE):
            print(f"📦 Знайдено збережений кеш товарів: {VarusApiClient.CACHE_FILE}")
            try:
                with open(VarusApiClient.CACHE_FILE, "r", encoding="utf-8") as f:
                    slugs = json.load(f)
                print(f"   ✅ Миттєво завантажено {len(slugs)} унікальних товарів з файлу.")
                return slugs
            except Exception as e:
                print(f"   ⚠️ Помилка читання кешу ({e}), збираємо заново...")

        print("🔍 [VARUS] Починаємо збір ВСІХ товарів (Обхід лімітів через ID-пагінацію)...")
        slugs = set()
        size = 1000
        last_seen_id = 0  # Зберігатимемо ID останнього товару

        # ==========================================
        # 2. БЕЗКІНЕЧНИЙ ЦИКЛ ПО ID
        # ==========================================
        while True:
            payload = {
                "_availableFilters": [],
                "_appliedFilters": [
                    {"attribute": "status", "value": {"in": [0, 1]}, "scope": "default"},
                    {"attribute": "visibility", "value": {"in": [2, 4]}, "scope": "default"}
                ],
                # Обов'язково сортуємо по ID, щоб вони йшли по порядку
                "_appliedSort": [{"field": "id", "options": {"order": "asc"}}],
                "_searchText": ""
            }

            # Якщо це не перший запит, просимо товари з ID більшим за останній
            if last_seen_id > 0:
                payload["_appliedFilters"].append(
                    {"attribute": "id", "value": {"gt": last_seen_id}, "scope": "default"}
                )

            params = {
                "_source_include": "id,sku",
                "from": 0,  # Завжди 0! Ми більше не впремося в ліміт 10000
                "size": size,
                "shop_id": VarusApiClient.SHOP_ID,
                "request": json.dumps(payload),
                "request_format": "search-query",
                "response_format": "compact"
            }

            try:
                response = requests.get(VarusApiClient.BASE_URL_SEARCH, params=params,
                                        headers=VarusApiClient.HEADERS_SEARCH, timeout=15)
                response.raise_for_status()
                data = response.json()

                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    hits_outer = data.get("hits", [])
                    if isinstance(hits_outer, list):
                        items = hits_outer
                    elif isinstance(hits_outer, dict):
                        items = hits_outer.get("hits", [])

                if not items:
                    print("   🏁 Нових товарів більше немає. Збір завершено!")
                    break

                current_batch = 0
                for item in items:
                    if not isinstance(item, dict): continue
                    source = item.get("_source", item)

                    product_id = source.get("id") or source.get("sku")
                    if product_id:
                        slugs.add(str(product_id))
                        current_batch += 1

                # Беремо ID найостаннішого товару з пачки для наступного запиту
                last_item_source = items[-1].get("_source", items[-1]) if isinstance(items[-1], dict) else items[-1]
                try:
                    last_seen_id = int(last_item_source.get("id"))
                except:
                    print("   ⚠️ Не вдалося отримати ID останнього товару, зупиняємось.")
                    break

                print(
                    f"   📥 Завантажено пачку {current_batch} шт. (Наступний запит з ID > {last_seen_id}). Всього унікальних: {len(slugs)}")

                # Якщо прийшло менше 1000, значить ми доскребли дно бази
                if len(items) < size:
                    print("   🏁 Це була остання сторінка.")
                    break

            except Exception as e:
                print(f"   ⚠️ Помилка на ID {last_seen_id}: {e}")
                break

        # ==========================================
        # 3. ЗБЕРЕЖЕННЯ У ФАЙЛ (КЕШУВАННЯ)
        # ==========================================
        if slugs:
            os.makedirs(VarusApiClient.CACHE_DIR, exist_ok=True)
            with open(VarusApiClient.CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(list(slugs), f, ensure_ascii=False, indent=4)
            print(
                f"\n💾 БІНГО! Унікальні товари ({len(slugs)} шт.) успішно збережено у файл {VarusApiClient.CACHE_FILE}!")

        return list(slugs)

    @staticmethod
    def fetch_detailed_product(slug: str) -> Optional[Dict[str, Any]]:
        # ==========================================
        # ЄДИНИЙ ЗАПИТ: Elasticsearch (Тепер дістає ВСЕ!)
        # ==========================================
        payload_search = {
            "_availableFilters": [],
            "_appliedFilters": [
                {"attribute": "id", "value": {"in": [slug]}, "scope": "default"}
            ],
            "_searchText": ""
        }

        params_search = {
            # ЗВЕРНИ УВАГУ: тут ми додали brand_data, description, category, countrymanufacturerforsite, image
            "_source_include": "sku,id,name,sqpp_data_region_default,weight,volume,is_18_plus,is_tobacco,brand_data,description,category,countrymanufacturerforsite,image",
            "from": 0,
            "size": 1,
            "shop_id": VarusApiClient.SHOP_ID,
            "request": json.dumps(payload_search),
            "request_format": "search-query",
            "response_format": "compact"
        }

        try:
            resp = requests.get(VarusApiClient.BASE_URL_SEARCH, params=params_search,
                                headers=VarusApiClient.HEADERS_SEARCH, timeout=10)
            if resp.status_code == 200:
                data = resp.json()

                # Наша надійна перевірка JSON, яку ми відшліфували раніше
                items = []
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
            print(f"   ⚠️ Помилка отримання деталей для {slug}: {e}")

        return None