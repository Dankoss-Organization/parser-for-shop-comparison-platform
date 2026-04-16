class BaseScraper:
    def __init__(self, adapter, media_proxy):
        self.adapter = adapter
        self.media_proxy = media_proxy

    def discover_slugs(self) -> list:
        """
        КРОК 1 (Discovery): Збирає список всіх доступних slugs (або ID) товарів.
        Якщо програміст не написав цей метод для свого магазину, система викине помилку.
        """
        raise NotImplementedError(f"Метод discover_slugs ще не реалізовано для {self.__class__.__name__}!")

    # Це і є Template Method - жорсткий каркас
    def process_product(self, slug):
        raw_data = self.fetch_data(slug)
        if not raw_data:
            return None

        unified_data = self.adapter.normalize(raw_data, self.media_proxy)
        return unified_data

    def fetch_data(self, slug):
        raise NotImplementedError("Цей метод мають реалізувати дочірні класи")