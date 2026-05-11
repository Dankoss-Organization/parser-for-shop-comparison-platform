from core.factory import ParserFactory
from core.resolution.router import EntityRouter


def process_store(store_name, router):
    print(f"\n{'=' * 50}\n[{store_name.upper()}] Починаємо повний цикл парсингу...\n{'=' * 50}")
    scraper = ParserFactory.create_scraper(store_name)
    processed_count = 0

    try:
        slugs = scraper.discover_slugs()
        print(f"✅ Знайдено {len(slugs)} унікальних товарів для обробки.")

        if not slugs:
            print(f"⚠️ Список товарів для {store_name} порожній. Переходимо далі.")
            return

        for idx, slug in enumerate(slugs, 1):
            print(f"\n⏳ [{idx}/{len(slugs)}] Обробляємо: {slug}...")

            try:
                product = scraper.process_product(slug)
                if product:
                    router.process_scraped_item(product)
                    processed_count += 1
                else:
                    print(f"⚠️ Товар не знайдено: {slug}")

            except Exception as e:
                print(f"🛑 КРИТИЧНА ПОМИЛКА на товарі {slug}! Парсинг магазину зупинено.")
                print(f"Деталі помилки: {e}")
                router.db.rollback()
                break

    except NotImplementedError as e:
        print(f"⏭️ ПРОПУСК: {e}")
    except Exception as e:
        print(f"🛑 Помилка під час збору списку товарів (Discovery): {e}")

    print(f"🚀 Парсинг {store_name} завершено (або перервано)! Оброблено товарів: {processed_count}.")


if __name__ == "__main__":
    print("🧠 Ініціалізація ядра метчингу та підключення до бази даних...")
    router = EntityRouter()

    try:
        process_store("varus", router)
        process_store("silpo", router)
        process_store("fora", router)

    finally:
        print("\n🔒 Закриття з'єднання з базою даних...")
        router.close()