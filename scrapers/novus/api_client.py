import os
import json
import requests
from typing import List, Dict, Any, Optional


class NovusApiClient:
    STORE_ID = "48201031"  # ID магазину Novus (Zakaz.ua)
    BASE_URL = f"https://stores-api.zakaz.ua/stores/{STORE_ID}"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Origin": "https://novus.zakaz.ua",
        "Referer": "https://novus.zakaz.ua/"
    }

    CACHE_DIR = os.path.join(os.getcwd(), "cache")
    CACHE_FILE = os.path.join(CACHE_DIR, "novus_slugs.json")

    @staticmethod
    def fetch_all_slugs() -> List[str]:
        # ==========================================
        # 1. ПЕРЕВІРКА КЕШУ
        # ==========================================
        if os.path.exists(NovusApiClient.CACHE_FILE):
            print(f"📦 Знайдено кеш товарів Novus: {NovusApiClient.CACHE_FILE}")
            try:
                with open(NovusApiClient.CACHE_FILE, "r", encoding="utf-8") as f:
                    slugs = json.load(f)
                print(f"   ✅ Миттєво завантажено {len(slugs)} товарів Novus.")
                return slugs
            except Exception as e:
                print(f"   ⚠️ Помилка читання кешу: {e}")

        print("🔍 [NOVUS] Починаємо збір товарів через Zakaz.ua API...")
        slugs = set()

        # ==========================================
        # 2. ОТРИМАННЯ КАТЕГОРІЙ
        # ==========================================
        try:
            cat_resp = requests.get(f"{NovusApiClient.BASE_URL}/categories/", headers=NovusApiClient.HEADERS,
                                    timeout=10)
            cat_resp.raise_for_status()
            categories = cat_resp.json()
        except Exception as e:
            print(f"❌ Помилка завантаження категорій Novus: {e}")
            return []

        print(f"   📁 Знайдено {len(categories)} категорій. Завантажуємо товари...")

        # ==========================================
        # 3. ЗБІР ТОВАРІВ ПО КАТЕГОРІЯХ (З ЗАХИСТОМ ВІД ЦИКЛІВ)
        # ==========================================
        for idx, cat in enumerate(categories, 1):
            cat_id = cat.get("id")
            if not cat_id:
                continue

            # Виводимо в консоль, щоб бачити, що процес іде
            print(f"   ⬇️ [{idx}/{len(categories)}] Категорія '{cat_id}'...", end="", flush=True)

            page = 1
            added_in_cat = 0

            while True:
                url = f"{NovusApiClient.BASE_URL}/categories/{cat_id}/products/?page={page}"
                try:
                    resp = requests.get(url, headers=NovusApiClient.HEADERS, timeout=15)
                    if resp.status_code != 200:
                        break

                    data = resp.json()
                    results = data.get("results") or []

                    if not results:
                        break  # Сторінки закінчилися чесно

                    # ЗАХИСТ ВІД НЕСКІНЧЕННОГО ЦИКЛУ
                    start_count = len(slugs)

                    for item in results:
                        product_id = item.get("ean") or item.get("sku")
                        if product_id:
                            slugs.add(str(product_id))

                    # Якщо ми розпарсили сторінку, а нових унікальних товарів не додалося -
                    # значить API віддає дублікати (зациклилось). Зупиняємо сторінки!
                    if len(slugs) == start_count:
                        break

                    added_in_cat += (len(slugs) - start_count)
                    page += 1

                except Exception as e:
                    print(f" (помилка: {e})", end="")
                    break

            # Пишемо, скільки товарів витягли з цієї категорії
            print(f" Знайдено: {added_in_cat} шт.")

        # ==========================================
        # 4. ЗБЕРЕЖЕННЯ У ФАЙЛ (КЕШУВАННЯ)
        # ==========================================
        if slugs:
            os.makedirs(NovusApiClient.CACHE_DIR, exist_ok=True)
            with open(NovusApiClient.CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(list(slugs), f, ensure_ascii=False, indent=4)
            print(f"\n💾 Успішно збережено {len(slugs)} унікальних товарів Novus у файл кешу!")

        return list(slugs)

    @staticmethod
    def fetch_detailed_product(slug: str) -> Optional[Dict[str, Any]]:
        # API Zakaz.ua дозволяє витягувати деталі конкретного товару
        url = f"{NovusApiClient.BASE_URL}/products/{slug}/"
        try:
            resp = requests.get(url, headers=NovusApiClient.HEADERS, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("product")  # Zakaz загортає дані в ключ "product"
        except Exception as e:
            print(f"   ⚠️ Помилка отримання деталей Novus для {slug}: {e}")

        return None