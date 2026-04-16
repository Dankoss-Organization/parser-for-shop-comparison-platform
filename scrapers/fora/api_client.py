import requests
import time
from config import FORA_HEADERS


class ForaApiClient:
    @staticmethod
    def fetch_detailed_product(slug, filial_id=310):
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
    def fetch_all_slugs(filial_id=310, max_pages=2) -> list:

        url = 'https://api.catalog.ecom.fora.ua/api/2.0/exec/EcomCatalogGlobal'
        headers = FORA_HEADERS.copy()
        all_slugs = set()

        try:
            cat_payload = {
                "method": "GetCategories",
                "data": {"deliveryType": 2, "filialId": filial_id, "merchantId": 2}
            }
            cat_resp = requests.post(url, headers=headers, json=cat_payload, timeout=10)
            cat_resp.raise_for_status()
            categories_tree = cat_resp.json().get('tree', [])
            category_slugs = [c.get('slug') for c in categories_tree if c.get('slug')]
        except Exception as e:
            print(f" Помилка завантаження категорій для Discovery: {e}")
            return []

        category_slugs = category_slugs[:3]

        for cat_slug in category_slugs:
            print(f"   Категорія: {cat_slug}")
            step = 30

            for page in range(max_pages):
                from_item = page * step + 1
                to_item = (page + 1) * step

                payload = {
                    "method": "GetSimpleCatalogItems",
                    "data": {
                        "merchantId": 2,
                        "deliveryType": 2,
                        "filialId": filial_id,
                        "slug": cat_slug,
                        "From": from_item,
                        "To": to_item,
                        "businessId": 1
                    }
                }

                try:
                    response = requests.post(url, headers=headers, json=payload, timeout=10)
                    response.raise_for_status()
                    data = response.json()

                    items = data.get('items', [])
                    if not items:
                        break

                    for item in items:
                        slug = item.get('slug')
                        if slug:
                            all_slugs.add(slug)

                    items_count = data.get('itemsCount', 0)
                    if to_item >= items_count:
                        break

                    time.sleep(0.1)

                except Exception as e:
                    print(f"️ Помилка на категорії {cat_slug} (стор. {page + 1}): {e}")
                    break

        return list(all_slugs)