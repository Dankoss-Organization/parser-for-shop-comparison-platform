import json
from core.factory import ParserFactory


def process_store(store_name, slugs, output_file):
    print(f"\n[{store_name.upper()}] Починаємо парсинг...")
    scraper = ParserFactory.create_scraper(store_name)
    results = []

    for slug in slugs:
        print(f"⏳ Обробляємо: {slug}...")

        try:
            product = scraper.process_product(slug)
            if product:
                results.append(product)
                print(f"✅ Успішно! Товар: {product['canonical_name']}")
            else:
                print(f"⚠️ Товар не знайдено: {slug}")

        except Exception as e:
            # ЦЕЙ БЛОК ТЕПЕР ЛОВИТЬ АБСОЛЮТНО ВСЕ!
            print(f"🛑 КРИТИЧНА ПОМИЛКА! Парсинг магазину {store_name} зупинено.")
            print(f"Деталі помилки: {e}")
            break  # Негайно виходимо з циклу, не йдемо до наступних товарів

    # Зберігаємо те, що встигли зібрати ДО помилки
    if results:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"🚀 Парсинг {store_name} завершено (або перервано)! Збережено {len(results)} товарів у {output_file}.")
    else:
        print(f"❌ Жодного товару не було зібрано. Файл {output_file} не створено.")


if __name__ == "__main__":
    # Тестові дані Сільпо
    silpo_slugs = [
        "sumish-ovocheva-bauer-mediterranean-style-886097",
        "kava-zernova-brazyliia-naturalna-smazhena-939991"
    ]
    process_store("silpo", silpo_slugs, "silpo_parsed_results.json")

    # Тестові дані Фори
    fora_slugs = [
        "shokolad-molochnyi-milka-bez-dobavok-581713",
        "shokolad-molochnyi-milka-bubbles-porystyi-523478"
    ]
    process_store("fora", fora_slugs, "fora_parsed_results.json")