import requests
import time
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
    def fetch_all_slugs(filial_id: int = 310, max_pages: int = 2) -> List[str]:
        """
        Discovers and compiles a list of available product slugs from the store catalog.

        This method acts as the discovery phase for the scraper. It performs a multi-step
        API communication process:
        1. Fetches the high-level category tree using the 'GetCategories' method.
        2. Iterates through a limited subset of top-level categories.
        3. Paginates through each category using the 'GetSimpleCatalogItems' method to
           extract individual product slugs.

        Note:
            To prevent excessive API load and rate-limiting, the method includes a small
            sleep interval (0.1s) between pagination requests and uses a `set` to guarantee
            uniqueness of the collected identifiers.

        Args:
            filial_id (int, optional): The branch ID to check for available catalog items.
                Defaults to 310.
            max_pages (int, optional): The maximum number of pagination steps to perform
                per category. Prevents infinite loops and limits the extraction scope.
                Defaults to 2.

        Returns:
            List[str]: A unique list of string slugs representing discovered products
            ready for detailed extraction.
        """
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

        # Limit to the first 3 categories for scope control during discovery
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
                        # Break pagination if no more items are returned
                        break

                    for item in items:
                        slug = item.get('slug')
                        if slug:
                            all_slugs.add(slug)

                    items_count = data.get('itemsCount', 0)
                    if to_item >= items_count:
                        # Break pagination if we have reached the total items count
                        break

                    # Small delay to prevent rate-limiting by the API
                    time.sleep(0.1)

                except Exception as e:
                    print(f"️ Помилка на категорії {cat_slug} (стор. {page + 1}): {e}")
                    break

        return list(all_slugs)