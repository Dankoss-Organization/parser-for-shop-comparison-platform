import requests
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