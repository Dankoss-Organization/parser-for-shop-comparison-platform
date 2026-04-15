import json
from api_client import fetch_detailed_product_fora
from parser import build_unified_product_fora

if __name__ == "__main__":
    # Сюди можна додавати будь-які slug товарів з Фори
    test_slugs = [
        "shokolad-molochnyi-milka-bez-dobavok-581713",
        "shokolad-molochnyi-milka-bubbles-porystyi-523478"
    ]

    results = []

    for slug in test_slugs:
        print(f"\n⏳ Обробляємо: {slug}...")
        raw_json = fetch_detailed_product_fora(slug)

        if raw_json and not raw_json.get('EComError', {}).get('ErrorCode'):
            unified_json = build_unified_product_fora(raw_json)
            if unified_json:
                results.append(unified_json)
                print(f"✅ Успішно! Товар: {unified_json['canonical_name']}")
            else:
                print(f"❌ Помилка парсингу для {slug}")
        else:
            print(f"❌ Не вдалося отримати дані для {slug}")

    with open("fora_parsed_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n🚀 Парсинг завершено! Дані збережено в fora_parsed_results.json.")