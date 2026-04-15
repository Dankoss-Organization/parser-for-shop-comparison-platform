import requests
from config import HEADERS


def fetch_detailed_product(slug, branch_id="00000000-0000-0000-0000-000000000000"):
    """
    Відправляє GET-запит до API Сільпо для отримання всіх деталей товару.
    """
    url = f'https://sf-ecom-api.silpo.ua/v1/uk/branches/{branch_id}/products/{slug}'

    headers = HEADERS.copy()
    headers['referer'] = f'https://silpo.ua/product/{slug}'

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Помилка завантаження деталей для {slug}: {e}")
        return None