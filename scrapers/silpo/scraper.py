from typing import List, Dict, Any, Optional
from core.base_scraper import BaseScraper
from .api_client import SilpoApiClient

class SilpoScraper(BaseScraper):
    """
    A concrete scraper implementation for the 'Silpo' supermarket chain.

    This class extends the `BaseScraper` framework, implementing the specific
    methods required to discover and fetch product data from Silpo's internal API.
    It orchestrates the scraping workflow by coordinating between the
    discovery logic and the detailed data extraction phase.
    """

    def discover_slugs(self) -> List[str]:
        """
        Discovers product slugs from the Silpo catalog using the API client.

        This method fulfills the first step of the scraping pipeline (Discovery)
        by calling the `SilpoApiClient` to gather unique product identifiers.
        It is currently configured to scan a limited range of the catalog
        defined by the `max_pages` parameter.

        Returns:
            List[str]: A list of unique string identifiers (slugs) found during
            the discovery process.
        """
        return SilpoApiClient.fetch_all_slugs(max_pages=2)

    def fetch_data(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the complete raw metadata for a specific Silpo product.

        This method performs a detailed lookup for a single item using its
        unique slug. The resulting raw data is intended to be
        passed to the `SilpoAdapter` for normalization into the platform's
        unified schema.

        Args:
            slug (str): The unique product identifier string used in the
                Silpo URL and API.

        Returns:
            Optional[Dict[str, Any]]: The raw JSON response from the Silpo
            API containing product attributes, pricing, and media, or `None`
            if the data could not be retrieved.
        """
        return SilpoApiClient.fetch_detailed_product(slug)