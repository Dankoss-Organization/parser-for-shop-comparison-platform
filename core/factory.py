from typing import Any
from scrapers.silpo.scraper import SilpoScraper
from scrapers.silpo.adapter import SilpoAdapter
from scrapers.fora.scraper import ForaScraper
from scrapers.fora.adapter import ForaAdapter
from core.media_proxy import CloudinaryImageProxy


class ParserFactory:
    """
    A factory class responsible for instantiating store-specific scrapers.

    This class strictly implements the **Factory Method** design pattern. It centralizes
    the creation logic for all web scrapers in the Shop Comparison Platform.
    Instead of hardcoding scraper initializations throughout the main application,
    the system delegates object creation to this factory.

    The factory ensures that every scraper is properly assembled and injected with
    its mandatory dependencies:
    1. A store-specific data adapter (e.g., `SilpoAdapter`).
    2. A shared media proxy service (`CloudinaryImageProxy`).
    """

    @staticmethod
    def create_scraper(store_name: str) -> Any:
        """
        Creates and returns a fully configured scraper instance for the specified store.

        Logic Flow:
        1. Initializes the `CloudinaryImageProxy` to handle external image caching.
        2. Evaluates the requested `store_name` (case-sensitive).
        3. Instantiates the matching data adapter for the required store schema.
        4. Injects both the adapter and the media proxy into the specific Scraper class.
        5. Returns the ready-to-use scraper.

        Args:
            store_name (str): The internal string identifier for the supermarket chain.
                Currently supported values are:
                - `"silpo"`
                - `"fora"`

        Returns:
            Any: An instantiated store scraper object (e.g., `SilpoScraper` or `ForaScraper`).
            These objects inherently implement the interface defined by `BaseScraper`.

        Raises:
            ValueError: If the provided `store_name` does not match any registered
                parsers in the factory.

        Examples:
            >>> scraper = ParserFactory.create_scraper("silpo")
            >>> type(scraper).__name__
            'SilpoScraper'

            >>> ParserFactory.create_scraper("atb")
            Traceback (most recent call last):
                ...
            ValueError: Магазин atb не підтримується
        """
        media_proxy = CloudinaryImageProxy()

        if store_name == "silpo":
            return SilpoScraper(SilpoAdapter(), media_proxy)
        elif store_name == "fora":
            return ForaScraper(ForaAdapter(), media_proxy)
        else:
            raise ValueError(f"Магазин {store_name} не підтримується")