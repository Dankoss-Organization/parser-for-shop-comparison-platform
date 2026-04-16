from core.factory import ParserFactory
from core.resolution.router import EntityRouter


def process_store(store_name, slugs, router):
    print(f"\n[{store_name.upper()}] Починаємо парсинг...")
    scraper = ParserFactory.create_scraper(store_name)
    processed_count = 0

    for slug in slugs:
        print(f"\n⏳ Обробляємо: {slug}...")

        try:
            product = scraper.process_product(slug)
            if product:
                # ВІДПРАВЛЯЄМО В МАРШРУТИЗАТОР ЗАМІСТЬ ЗБЕРЕЖЕННЯ В JSON
                router.process_scraped_item(product)
                processed_count += 1
            else:
                print(f"⚠️ Товар не знайдено: {slug}")

        except Exception as e:
            # ЦЕЙ БЛОК ЛОВИТЬ АБСОЛЮТНО ВСЕ
            print(f"🛑 КРИТИЧНА ПОМИЛКА! Парсинг магазину {store_name} зупинено.")
            print(f"Деталі помилки: {e}")
            break  # Негайно виходимо з циклу, не йдемо до наступних товарів

    print(f"🚀 Парсинг {store_name} завершено (або перервано)! Оброблено товарів: {processed_count}.")


if __name__ == "__main__":
    print("🧠 Ініціалізація ядра метчингу та підключення до бази даних...")
    # Ініціалізуємо Роутер ОДИН РАЗ на початку.
    # Це важливо, щоб підключення до БД і ML-модель не завантажувалися двічі.
    router = EntityRouter()

    try:
        # Тестові дані Сільпо
        silpo_slugs = [
            "sumish-ovocheva-bauer-mediterranean-style-886097",
            "kava-zernova-brazyliia-naturalna-smazhena-939991"
        ]
        process_store("silpo", silpo_slugs, router)

        # Тестові дані Фори
        fora_slugs = [
            "shokolad-molochnyi-milka-bez-dobavok-581713",
            "shokolad-molochnyi-milka-bubbles-porystyi-523478"
        ]
        process_store("fora", fora_slugs, router)

    finally:
        # Блок finally гарантує, що з'єднання з базою закриється правильно,
        # навіть якщо програма впаде з помилкою.
        print("\n🔒 Закриття з'єднання з базою даних...")
        router.close()