class BaseScraper:
    def __init__(self, adapter, media_proxy):
        self.adapter = adapter
        self.media_proxy = media_proxy

    # Це і є Template Method - жорсткий каркас
    def process_product(self, slug):
        raw_data = self.fetch_data(slug)
        if not raw_data:
            return None

        unified_data = self.adapter.normalize(raw_data, self.media_proxy)
        return unified_data

    def fetch_data(self, slug):
        raise NotImplementedError("Цей метод мають реалізувати дочірні класи")