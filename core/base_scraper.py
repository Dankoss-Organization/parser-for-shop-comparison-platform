from typing import List, Dict, Any, Optional


class BaseScraper:
    """
    An abstract base class that defines the core workflow for all store scrapers.

    This class strictly implements the **Template Method** design pattern. It enforces
    a standardized pipeline for processing products across all supermarkets, while
    delegating the specific, store-dependent implementation details (like API calls
    and pagination) to its child classes.

    Attributes:
        adapter (Any): An instance of a store-specific adapter (subclass of BaseAdapter)
            used to convert raw scraped data into the unified schema.
        media_proxy (Any): A proxy service (e.g., CloudinaryImageProxy) used to
            download, cache, and upload product images to the cloud.
    """

    def __init__(self, adapter: Any, media_proxy: Any) -> None:
        """
        Initializes the scraper with its required dependencies for data transformation
        and media handling.

        Args:
            adapter (Any): The adapter instance responsible for normalizing the raw
                store data.
            media_proxy (Any): The service responsible for managing image uploads.
        """
        self.adapter = adapter
        self.media_proxy = media_proxy

    def discover_slugs(self) -> List[str]:
        """
        Step 1 (Discovery Phase): Gathers a comprehensive list of all available
        product identifiers from the target store's catalog.

        This abstract method must be implemented by the specific store's scraper.
        It traverses categories, handles API pagination, and collects the unique
        slugs or SKUs needed to fetch individual product details later.

        Returns:
            List[str]: A list of unique string identifiers for the products.

        Raises:
            NotImplementedError: If the child class fails to implement this method.
        """
        raise NotImplementedError(f"Method discover_slugs is not implemented for {self.__class__.__name__}!")

    def process_product(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        The Template Method: Executes the unchangeable pipeline for a single product.

        This method acts as the rigid skeleton of the scraping algorithm and ensures
        that every product from every store goes through the exact same lifecycle:
        1. Invokes `fetch_data` to get the raw JSON/HTML for the given slug.
        2. Validates that the data was actually retrieved.
        3. Passes the raw data and the media proxy to the `adapter.normalize`
           method for transformation.
        4. Returns the final, unified data structure.

        Args:
            slug (str): The unique identifier (SKU/slug) for the product being processed.

        Returns:
            Optional[Dict[str, Any]]: The standardized product dictionary ready to be
            saved to the database, or `None` if the raw data could not be fetched.
        """
        raw_data = self.fetch_data(slug)
        if not raw_data:
            return None

        unified_data = self.adapter.normalize(raw_data, self.media_proxy)
        return unified_data

    def fetch_data(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the raw, unformatted data for a specific product from the store's servers.

        This abstract method handles the actual network request (e.g., calling an API
        endpoint) for a given identifier. It separates the network logic from the
        processing logic.

        Args:
            slug (str): The unique identifier of the product to fetch.

        Returns:
            Optional[Dict[str, Any]]: The raw JSON response or parsed dictionary
            straight from the store's backend. Should return `None` if the product
            is not found (e.g., a 404 error).

        Raises:
            NotImplementedError: If the child class fails to implement this method.
        """
        raise NotImplementedError("This method must be implemented by specific store scraper classes.")