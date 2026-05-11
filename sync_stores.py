import requests
import json
import os
import re


def sync_varus_stores():
    print("🔄 Отримання актуального списку магазинів Varus...")

    url = "https://varus.ua/api/catalog/vue_storefront_catalog_2/product_v2/_search"

    # Імітуємо реальний пошук, щоб сервер згенерував метадані фільтрів
    payload = {
        "_availableFilters": [
            {"field": "has_promotion_in_stores", "scope": "catalog", "options": {"size": 10000}}
        ],
        "_appliedFilters": [
            {"attribute": "status", "value": {"in": [1]}, "scope": "default"}  # Імітація: "дай активні товари"
        ],
        "_searchText": ""
    }

    params = {
        "from": 0,
        "size": 1,  # Просимо хоча б 1 товар, щоб бекенд не відкинув генерацію фільтрів
        "shop_id": 3,
        "request": json.dumps(payload),
        "request_format": "search-query",
        "response_format": "compact"
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        # Витягуємо магазини з метаданих
        stores_list = []
        metadata = data.get("attribute_metadata", [])

        for attr in metadata:
            if attr.get("attribute_code") == "has_promotion_in_stores":
                stores_list = attr.get("options", [])
                break

        if not stores_list:
            print("❌ Не вдалося знайти список магазинів у відповіді API. Сервер повернув ключі:", list(data.keys()))
            return

        # Формуємо словник: { "Гарна_Назва": "ID" }
        formatted_stores = {}
        for store in stores_list:
            raw_label = store['label']
            clean_label = re.sub(r'\(ID=.*\)', '', raw_label).strip()
            key = re.sub(r'[^a-zA-Zа-яА-ЯіїєІЇЄ0-9]+', '_', clean_label).strip('_')
            formatted_stores[key] = store['value']

        sorted_stores = dict(sorted(formatted_stores.items()))

        # ==========================================
        # ЗАПИС У CONFIG.PY
        # ==========================================
        config_path = os.path.join(os.getcwd(), "config.py")
        if not os.path.exists(config_path):
            print(f"❌ Файл {config_path} не знайдено! Переконайся, що запускаєш з кореня проєкту.")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        stores_string = "VARUS_STORES = {\n"
        for k, v in sorted_stores.items():
            stores_string += f"    \"{k}\": \"{v}\",\n"
        stores_string += "}"

        if "VARUS_STORES =" in content:
            new_content = re.sub(r'VARUS_STORES\s*=\s*\{.*?\}', stores_string, content, flags=re.DOTALL)
        else:
            new_content = content + "\n\n" + stores_string

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"✅ Успішно оновлено! Додано {len(sorted_stores)} магазинів у config.py")

    except Exception as e:
        print(f"❌ Помилка під час оновлення: {e}")


if __name__ == "__main__":
    sync_varus_stores()