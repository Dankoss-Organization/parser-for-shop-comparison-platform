from typing import List, Dict, Any, Optional
from core.base_scraper import BaseScraper
from .api_client import ForaApiClient


class ForaScraper(BaseScraper):
    """
    A concrete scraper implementation for the 'Fora' supermarket chain.

    This class inherits from `BaseScraper` and fulfills the required Template Method
    contracts (`discover_slugs` and `fetch_data`). It acts as the orchestrator
    for Fora-specific data extraction, utilizing the `ForaApiClient` to communicate
    with the store's backend APIs.
    """

    def discover_slugs(self) -> List[str]:
        """
        Discovers and retrieves a list of all available product slugs from Fora.

        This method implements the first step of the scraping pipeline (Discovery).
        It delegates the actual network requests and pagination logic to the
        `ForaApiClient.fetch_all_slugs()` method.

        Note:
            Currently, the scraping is limited to `max_pages=2` per category
            as defined in the API client call, which controls the scope of
            the discovery phase.

        Returns:
            List[str]: A list of unique product slugs (string identifiers) ready
            to be processed individually.
        """
        print(" [ФОРА] Збираємо список товарів з каталогу...")
        slugs = ForaApiClient.fetch_all_slugs(max_pages=2)
        print(f" [ФОРА] Знайдено {len(slugs)} унікальних товарів для обробки.")
        return slugs

    def fetch_data(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the raw, detailed JSON data for a specific Fora product.

        This method requests the complete metadata for a single item using its slug.
        Crucially, it includes an error-handling layer specific to Fora's API:
        Even if the HTTP status code is 200 (OK), the Fora API might return an
        internal error inside the JSON payload under the 'EComError' key. This
        method validates the absence of such application-level errors before
        returning the data.

        Args:
            slug (str): The specific product identifier (e.g., "kava-zernova-123").

        Returns:
            Optional[Dict[str, Any]]: The raw JSON dictionary containing the
            product details if the request is successful and error-free. Returns
            `None` if the API returns an application-level error.
        """
        raw_json = ForaApiClient.fetch_detailed_product(slug)

        # Validate that the response is not empty and does not contain internal API errors
        if raw_json and not raw_json.get('EComError', {}).get('ErrorCode'):
            return raw_json

        return None