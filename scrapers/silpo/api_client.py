import requests
from typing import List, Dict, Any
from config import SILPO_HEADERS


class SilpoApiClient:
    """
    A dedicated HTTP client for interacting with the Silpo supermarket API.

    This class provides static methods to communicate with Silpo's internal
    e-commerce backend. It handles catalog discovery through paginated requests
    and detailed product metadata extraction using branch-specific identifiers
    and product slugs.
    """

    @staticmethod
    def fetch_all_slugs(branch_id: str = "1edee42f-ece6-6e12-8d91-d3a7e392bfd1", max_pages: int = 2) -> List[str]:
        """
        Discovers and retrieves a list of product slugs from the Silpo catalog.

        This method implements the 'Discovery Phase' of the scraper by performing
        paginated GET requests to the Silpo products endpoint. It navigates
        through the store's inventory using limit and offset parameters.

        Logic Flow:
        1. **Request Setup:** Copies global Silpo headers and defines the default
           pagination limit (50 items per page).
        2. **Pagination Loop:** Iterates through pages up to the specified `max_pages`.
        3. **Parameter Construction:** Defines precise filters including delivery
           type, category filtering (defaults to 'frukty-ovochi-4788'), and
           stock availability.
        4. **Data Extraction:** Parses the 'items' array from the JSON response
           and collects the 'slug' field for each valid product.
        5. **Error Handling:** Gracefully stops discovery if a page returns no
           items or if a network exception occurs.

        Args:
            branch_id (str): The unique UUID identifying a specific physical store
                branch. This is required to ensure catalog and pricing consistency.
                Defaults to a verified branch UUID.
            max_pages (int): The maximum number of pagination steps to perform.
                Defaults to 2.

        Returns:
            List[str]: A unique list of discovered product slugs ready for
            individual extraction.
        """
        url = f'https://sf-ecom-api.silpo.ua/v1/uk/branches/{branch_id}/products'
        headers = SILPO_HEADERS.copy()

        all_slugs = []
        limit = 50
        categories = [
            "frukty-ovochi-4788",
            "molochni-produkty-ta-iaitsia-3913",
            "khlib-ta-khlibobulochni-vyroby-4061",
            "syry-3882",
            "miaso-4296",
            "ryba-ta-moreprodukty-3306",
            "kulinariia-829",
            "solodoshchi-ta-torti-3841",
            "napoi-8195",
            "alkohol-5423",
            "zamorozheni-produkty-4444",
            "bakaliia-ta-konservy-4330",
            "dytiache-kharchuvannia-7171",
            "krasa-ta-dohliad-4876",
            "tovary-dlia-tvaryn-5800",
            "pobutova-khimiia-5095",
            "dlia-kykhni-ta-domu-6691"
        ]

        print("🔍 [СІЛЬПО] Починаємо збір загального списку товарів (Discovery Phase)...")

        for category in categories:
            print(f"   📂 Скануємо категорію: {category}...")
            for page in range(1, max_pages + 1):
                params = {
                    "limit": limit,
                    "offset": (page - 1) * limit,
                    "deliveryType": "DeliveryHome",
                    "category": category,
                    "includeChildCategories": "true",
                    "inStock": "true"
                }

                try:
                    response = requests.get(url, headers=headers, params=params, timeout=10)
                    response.raise_for_status()
                    data = response.json()

                    items = data.get('items', [])
                    if not items:
                        print(f"      ℹ️ Товари закінчилися (категорія {category}, сторінка {page}).")
                        break

                    for item in items:
                        if 'slug' in item:
                            all_slugs.append(item['slug'])

                except requests.exceptions.RequestException as e:
                    print(f"⚠️ Помилка на сторінці {page} (категорія {category}): {e}")
                    break

        unique_slugs = list(set(all_slugs))
        print(f"   ✅ Загалом зібрано {len(unique_slugs)} унікальних товарів.")
        return unique_slugs

    @staticmethod
    def fetch_detailed_product(slug: str, branch_id: str = "1edee42f-ece6-6e12-8d91-d3a7e392bfd1") -> Dict[str, Any]:
        """
        Retrieves comprehensive metadata for a single product by its slug.

        This method targets the specific product detail endpoint. It provides the
        full data structure required by the adapter, including price history,
        detailed attribute groups, and promotional details.

        Args:
            slug (str): The unique string identifier for the product
                (e.g., "sumish-ovocheva-886097").
            branch_id (str): The branch ID used to fetch accurate local
                availability and current pricing. Defaults to a verified branch UUID.

        Returns:
            Dict[str, Any]: The raw JSON dictionary containing the product's
            complete metadata as provided by the Silpo API.

        Raises:
            Exception: If the API request fails or returns an error status.
        """
        url = f'https://sf-ecom-api.silpo.ua/v1/uk/branches/{branch_id}/products/{slug}'
        headers = SILPO_HEADERS.copy()
        headers['referer'] = f'https://silpo.ua/product/{slug}'

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Відмова API Сільпо: {e}")