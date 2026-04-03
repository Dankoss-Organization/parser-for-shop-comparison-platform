import requests
from config import FORA_HEADERS


def fetch_detailed_product_fora(slug, filial_id=310):
    """
    Відправляє POST-запит до GraphQL API Фори для отримання деталей товару.
    """
    url = 'https://api.catalog.ecom.fora.ua/api/2.0/exec/EcomCatalogGlobal'

    headers = FORA_HEADERS.copy()
    headers['referer'] = f'https://fora.ua/product/{slug}'

    # Структура запиту (Payload), яку ми знайшли в Network tab
    payload = {
        "method": "GetDetailedCatalogItem",
        "data": {
            "deliveryType": 2,
            "filialId": filial_id,
            "slug": slug,
            "merchantId": 2
        },
        "headers": {}
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Помилка завантаження деталей для {slug}: {e}")
        return None


def fetch_fora_categories(filial_id=310):
    """
    Завантажує ПОВНЕ дерево категорій (включно з підкатегоріями) з API Фори.
    """
    url = 'https://api.catalog.ecom.fora.ua/api/2.0/exec/EcomCatalogGlobal'

    # Твій новий ідеальний payload
    payload = {
        "method": "GetCategories",
        "data": {
            "deliveryType": 2,
            "filialId": filial_id,
            "merchantId": 2
        }
    }

    try:
        from config import FORA_HEADERS
        response = requests.post(url, headers=FORA_HEADERS, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()

        category_map = {}

        # Тепер ми проходимося по масиву "tree", де лежить абсолютно все!
        for item in data.get('tree', []):
            cat_id = int(item.get('id'))
            cat_name = item.get('name')
            category_map[cat_id] = cat_name

        return category_map

    except Exception as e:
        print(f"❌ Помилка завантаження повного дерева категорій Фори: {e}")
        return {}