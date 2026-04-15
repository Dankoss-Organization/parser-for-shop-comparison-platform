from scrapers.silpo.scraper import SilpoScraper
from scrapers.silpo.adapter import SilpoAdapter
from scrapers.fora.scraper import ForaScraper
from scrapers.fora.adapter import ForaAdapter
from core.media_proxy import CloudinaryImageProxy


class ParserFactory:
    @staticmethod
    def create_scraper(store_name: str):
        media_proxy = CloudinaryImageProxy()

        if store_name == "silpo":
            return SilpoScraper(SilpoAdapter(), media_proxy)
        elif store_name == "fora":
            return ForaScraper(ForaAdapter(), media_proxy)
        else:
            raise ValueError(f"Магазин {store_name} не підтримується")