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