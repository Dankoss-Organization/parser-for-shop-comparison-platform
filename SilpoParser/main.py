import json
from api_client import fetch_detailed_product
from parser import build_unified_product

if __name__ == "__main__":
    # Я додав сюди каву, щоб ти одразу побачив, як красиво лягає рейтинг та історія цін
    test_slugs = [
        "sumish-ovocheva-bauer-mediterranean-style-886097",
        "sumish-ovochiv-premiia-zamorozhena-po-italiisky-325891",
        "kava-zernova-brazyliia-naturalna-smazhena-939991"
    ]

    results = []

    for slug in test_slugs:
        print(f"\n⏳ Обробляємо: {slug}...")
        raw_json = fetch_detailed_product(slug)

        if raw_json:
            unified_json = build_unified_product(raw_json)
            results.append(unified_json)
            print(f"✅ Успішно! Товар: {unified_json['canonical_name']}")
        else:
            print(f"❌ Не вдалося отримати дані для {slug}")

    with open("silpo_parsed_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n🚀 Парсинг завершено! Дані збережено в silpo_parsed_results.json.")