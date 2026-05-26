import requests
import time
import random
from typing import Dict, Any, List
from config import FORA_HEADERS


class ForaApiClient:
    """
    A dedicated HTTP client for interacting with the internal Fora e-commerce API.

    This class provides static methods to communicate directly with Fora's backend
    services, bypassing standard HTML scraping. It handles the specific JSON payloads,
    headers, and endpoint structures required to retrieve structured product data
    and catalog inventory.
    """

    @staticmethod
    def fetch_detailed_product(slug: str, filial_id: int = 310) -> Dict[str, Any]:
        """
        Retrieves the comprehensive metadata for a single product.

        This method sends a targeted POST request to the 'GetDetailedCatalogItem'
        API method. It constructs the necessary payload to simulate a real frontend
        client requesting product details for a specific branch (filial).

        Args:
            slug (str): The unique URL-friendly string identifier for the product
                (e.g., "shokolad-molochnyi-milka-581713").
            filial_id (int, optional): The physical store/branch ID used to determine
                local availability and pricing. Defaults to 310.

        Returns:
            Dict[str, Any]: A raw JSON dictionary containing extensive product details,
            pricing, attributes, and promotional flags directly from the backend.

        Raises:
            Exception: If the HTTP request fails, times out, or returns an error status code.
        """
        url = 'https://api.catalog.ecom.fora.ua/api/2.0/exec/EcomCatalogGlobal'
        headers = FORA_HEADERS.copy()
        headers['referer'] = f'https://fora.ua/product/{slug}'

        payload = {
            "method": "GetDetailedCatalogItem",
            "data": {"deliveryType": 2, "filialId": filial_id, "slug": slug, "merchantId": 2},
            "headers": {}
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Відмова API Фори: {e}")

    @staticmethod
    def debug_category(cat_slug: str, filial_id: int = 310):
        """Перевіряє перші 3 товари з категорії — їх slug та назву"""
        url = 'https://api.catalog.ecom.fora.ua/api/2.0/exec/EcomCatalogGlobal'
        headers = FORA_HEADERS.copy()

        # Витягуємо ID категорії (все, що після останнього дефіса)
        cat_id = int(cat_slug.split('-')[-1])

        payload = {
            "method": "GetSimpleCatalogItems",
            "data": {
                "merchantId": 2,
                "deliveryType": 2,
                "filialId": filial_id,
                "categoryId": cat_id,  # 👈 ТЕПЕР ПЕРЕДАЄМО ID КАТЕГОРІЇ
                "From": 1,
                "To": 5,
                "businessId": 1
            }
        }

        response = requests.post(url, headers=headers, json=payload, timeout=10)
        data = response.json()
        items = data.get('items', [])

        print(f"\n=== {cat_slug} (ID: {cat_id}) ===")
        for item in items:
            print(f"  slug: {item.get('slug')}")
            print(f"  name: {item.get('name') or item.get('title')}")
            print()

    @staticmethod
    def fetch_all_slugs(filial_id: int = 310, max_pages: int = 200) -> List[str]:
        url = 'https://api.catalog.ecom.fora.ua/api/2.0/exec/EcomCatalogGlobal'
        headers = FORA_HEADERS.copy()
        all_slugs = set()
        step = 50
        max_empty_pages = 3  # скільки сторінок без нових товарів перед виходом

        # Тепер debug покаже правильні товари!
        ForaApiClient.debug_category("pitsa-ta-kulinariia-3268")
        ForaApiClient.debug_category("frukty-ovochi-ta-solinnia-2790")

        categories = [
            "pitsa-ta-kulinariia-3268",
            "frukty-ovochi-ta-solinnia-2790",
            "molochni-produkty-ta-iaitsia-2656",
            "bakaliia-konservy-ta-sousy-2492",
            "kovbasy-ta-m-iasni-delikatesy-2738",
            "khlib-ta-khlibobulochni-vyroby-2902",
            "vlasna-vypichka-5358",
            "svizhe-m-iaso-5401",
            "ryba-2699",
            "syry-5392",
            "solodoshchi-2913",
            "mineralna-i-pytna-voda-3642",
            "soky-ta-napoi-2479",
            "alkogol-2451",
            "sneky-2730",
            "sygarety-stiky-zhuiky-2886",
            "kava-chai-2775",
            "zamorozhena-produktsiia-2686"
        ]

        print(f"🔍 [ФОРА] Починаємо парсинг {len(categories)} вибраних категорій...")

        for i, cat_slug in enumerate(categories):
            print(f"\n   📂 [{i + 1}/{len(categories)}] {cat_slug}")

            # Витягуємо числовий ID категорії зі слага
            try:
                cat_id = int(cat_slug.split('-')[-1])
            except ValueError:
                print(f"   ⚠️ Не вдалося витягти ID з {cat_slug}, пропускаємо...")
                continue

            slugs_before = len(all_slugs)
            empty_streak = 0

            for page in range(max_pages):
                payload = {
                    "method": "GetSimpleCatalogItems",
                    "data": {
                        "merchantId": 2,
                        "deliveryType": 2,
                        "filialId": filial_id,
                        "categoryId": cat_id,
                        "From": page * step + 1,
                        "To": (page + 1) * step,
                        "businessId": 1
                    }
                }

                try:
                    start = time.time()
                    response = requests.post(url, headers=headers, json=payload, timeout=10)
                    response.raise_for_status()
                    elapsed = time.time() - start

                    data = response.json()
                    items = data.get('items', [])

                    if not items:
                        print(f"   📄 Стор. {page + 1}: порожньо — кінець категорії")
                        break

                    before = len(all_slugs)
                    for item in items:
                        if item.get('slug'):
                            all_slugs.add(item['slug'])
                    truly_new = len(all_slugs) - before

                    print(
                        f"   📄 Стор. {page + 1}: +{truly_new} нових / {len(items)} отримано | Всього: {len(all_slugs)} | ⏱ {elapsed:.1f}с")

                    if truly_new == 0:
                        empty_streak += 1
                        if empty_streak >= max_empty_pages:
                            print(f"   ⏭ {max_empty_pages} сторінки поспіль без нових товарів — пропускаємо категорію")
                            break
                    else:
                        empty_streak = 0

                    if len(items) < step:
                        break

                    time.sleep(0.1)

                except Exception as e:
                    print(f"\n   ⚠️ Помилка стор. {page + 1}: {e}")
                    break

            new_slugs = len(all_slugs) - slugs_before
            print(f"   ✅ Готово. Нових у цій категорії: {new_slugs} | Всього унікальних: {len(all_slugs)}")

        print(f"\n✅ Парсинг завершено. Зібрано {len(all_slugs)} унікальних товарів.")
        return list(all_slugs)