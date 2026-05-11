import json
import re
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from core.base_adapter import BaseAdapter
from scrapers.varus.api_client import VarusApiClient


class VarusAdapter(BaseAdapter):
    # Словник для розшифровки країн (додавай сюди нові ID, які бачиш в консолі)
    COUNTRY_MAP = {
        "11073": "Україна",
        "11111": "Італія",
        "11858": "Польща",
        "11235": "Франція",
        "11135": "Німеччина",
        "11130": "Нідерланди",
        "11133": "Туреччина",
        "11124": "Китай",
    }

    def normalize(self, raw_data: Dict[str, Any], media_proxy: Any = None) -> Optional[Dict[str, Any]]:
        if not raw_data or not isinstance(raw_data, dict):
            return None

        product_id = str(raw_data.get("id", ""))
        price_data = raw_data.get("sqpp_data_region_default")
        if price_data is None:
            return None

        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        original_sku = str(raw_data.get("sku") or product_id)
        product_sku = f"varus_{original_sku}"

        # 1. ЦІНИ
        regular_price = float(price_data.get("sort_price") or price_data.get("price") or 0.0)
        special_price = price_data.get("special_price")
        current_price = float(special_price) if special_price else regular_price
        discount_percent = int(price_data.get("special_price_discount") or 0)
        is_in_stock = bool(price_data.get("in_stock", False))

        # 2. БРЕНД ТА КРАЇНА (Розшифровка ID)
        brand_obj = raw_data.get("brand_data") or {}
        brand_name = brand_obj.get("name") if isinstance(brand_obj, dict) else "Без бренду"

        # Розшифровуємо країну за словником, якщо немає в словнику - лишаємо ID як рядок
        country_id = str(raw_data.get("countrymanufacturerforsite") or "")
        country_name = self.COUNTRY_MAP.get(country_id, country_id if country_id else "Не вказано")

        # 3. ОПИС
        raw_description = raw_data.get("description") or ""
        clean_description = re.sub(r'<[^>]+>', '', str(raw_description)).strip()

        # 4. КАТЕГОРІЇ
        category_name = "Інше"
        raw_categories = raw_data.get("category")
        if isinstance(raw_categories, list):
            valid_cats = [c for c in raw_categories if isinstance(c, dict)]
            if valid_cats:
                try:
                    deepest_cat = max(valid_cats, key=lambda c: int(c.get("level", 0)))
                    category_name = deepest_cat.get("name")
                except:
                    pass

        # 5. ФОТО
        image_path = raw_data.get("image")
        if image_path and str(image_path).strip() and image_path != "null":
            raw_main_image_url = f"https://varus.ua/img/product/origin/{str(image_path).lstrip('/')}"
        else:
            raw_main_image_url = f"https://varus.ua/img/product/feed/420/420/{original_sku}.png"

        new_image = None
        if raw_main_image_url and media_proxy:
            try:
                new_image = media_proxy.process_image(
                    raw_url=raw_main_image_url,
                    product_sku=product_sku,
                    suffix="main",
                    folder_name="varus_products",
                    headers=VarusApiClient.HEADERS_SEARCH
                )
            except Exception:
                pass

        # 6. ВИМІРЮВАННЯ (ФІКС NULL ЗНАЧЕНЬ)
        measurements = {"value": 1.0, "unit": "шт"}  # Дефолт - штуки
        try:
            w = raw_data.get("weight")
            v = raw_data.get("volume")
            if w and float(w) > 0:
                measurements = {"value": float(w), "unit": "г"}
            elif v and float(v) > 0:
                measurements = {"value": float(v), "unit": "мл"}
        except:
            pass

        return {
            "product_id": product_sku,
            "canonical_name": raw_data.get("name") or "Без назви",
            "brand": brand_name,
            "category": category_name,
            "country": country_name,
            "media": {
                "raw_main_image": raw_main_image_url,
                "raw_gallery": [raw_main_image_url],
                "main_image": new_image,
                "gallery": [new_image] if new_image else []
            },
            "measurements": measurements,
            "pricing_logic": {"sales_unit": "piece", "unit_step": 1},
            "specific_attributes": {
                "is_tobacco": bool(raw_data.get("is_tobacco", False)),
                "is_18_plus": bool(raw_data.get("is_18_plus", False)),
                "description": clean_description
            },
            "offers": [{
                "store_id": "v_varus",
                "store_name": "Varus",
                "url": f"https://varus.ua/{raw_data.get('url_key') or ''}",
                "is_in_stock": is_in_stock,
                "sku": original_sku,
                "scraped_at": current_time,
                "pricing": {
                    "regular_price": regular_price,
                    "current_price": current_price,
                    "discount_percent": discount_percent,
                    "is_online_only": False,
                    "promo_end_date": price_data.get("special_price_to_date") or "",
                    "bulk_discounts": []
                },
                "price_history": [{"date": current_time, "price": current_price, "regular_price": regular_price}]
            }]
        }