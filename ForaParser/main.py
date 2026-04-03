import json
from api_client import fetch_detailed_product_fora, fetch_fora_categories
from parser import build_unified_product_fora

if __name__ == "__main__":
    test_slugs = [
        "shokolad-molochnyi-milka-bez-dobavok-581713",
        "shokolad-molochnyi-milka-bubbles-porystyi-523478",
        "vyno-igryste-shabo-primo-secco-rozheve-briut-966588",
        "plastivtsi-dobele-vivsiani-podribneni-960385"  # додала вівсянку для тесту
    ]

    results = []

    print("⏳ Завантажуємо довідник категорій з Фори...")
    category_map = fetch_fora_categories()
    print(f"✅ Довідник готовий! Отримано {len(category_map)} категорій.\n")

    for slug in test_slugs:
        print(f"\n⏳ Обробляємо: {slug}...")
        raw_json = fetch_detailed_product_fora(slug)

        if raw_json and not raw_json.get('EComError', {}).get('ErrorCode'):
            # ТУТ ТЕПЕР ПЕРЕДАЄМО НАШ СЛОВНИК category_map
            unified_json = build_unified_product_fora(raw_json, category_map)

            if unified_json:
                results.append(unified_json)
                print(f"✅ Успішно! Товар: {unified_json['canonical_name']}")
                print(f"   📂 Категорія: {unified_json['category']}")
            else:
                print(f"❌ Помилка парсингу для {slug}")
        else:
            print(f"❌ Не вдалося отримати дані для {slug}")

    with open("fora_parsed_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n🚀 Парсинг завершено! Дані збережено в fora_parsed_results.json.")