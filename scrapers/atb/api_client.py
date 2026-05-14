import cloudscraper


class AtbApiClient:
    def __init__(self):
        self.base_url = "https://www.atbmarket.com"
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )

    def fetch_catalog_page(self, category_slug: str, page: int) -> str:

        url = f"{self.base_url}/catalog/{category_slug}?page={page}"

        try:
            response = self.scraper.get(url, timeout=15.0)
            response.raise_for_status()

            return response.text

        except Exception as e:
            print(f"⚠️ Помилка завантаження сторінки {url}: {e}")
            return ""