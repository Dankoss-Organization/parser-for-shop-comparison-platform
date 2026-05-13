import re
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from core.base_adapter import BaseAdapter
from scrapers.novus.api_client import NovusApiClient


class NovusAdapter(BaseAdapter):
    def normalize(self, raw_data: Dict[str, Any], media_proxy: Any = None) -> Optional[Dict[str, Any]]:
        if not raw_data or not isinstance(raw_data, dict):
            return None

        # Використовуємо EAN, якщо є, інакше SKU
        original_sku = str(raw_data.get("ean") or raw_data.get("sku") or "")
        if not original_sku:
            return None

        product_sku = f"novus_{original_sku}"
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # ==========================================
        # 1. ЦІНОУТВОРЕННЯ (Ціни в копійках!)
        # ==========================================
        raw_price = raw_data.get("price") or 0
        regular_price = float(raw_price) / 100.0

        discount_info = raw_data.get("discount") or {}
        is_discounted = bool(discount_info.get("status", False))

        if is_discounted:
            current_price = regular_price  # Поточна ціна
            old_price_raw = discount_info.get("old_price") or raw_price
            regular_price = float(old_price_raw) / 100.0  # Стара ціна без знижки
            discount_percent = int(discount_info.get("value") or 0)
            promo_end_date = discount_info.get("due_date") or ""
        else:
            current_price = regular_price
            discount_percent = 0
            promo_end_date = ""

        is_in_stock = bool(raw_data.get("in_stock", False))

        # ==========================================
        # 2. БРЕНД, КРАЇНА, ОПИС
        # ==========================================
        producer = raw_data.get("producer") or {}
        brand_name = producer.get("trademark") or "Без бренду"
        country_name = raw_data.get("country") or "Не вказано"

        raw_description = raw_data.get("description") or ""
        # Чистимо від HTML-тегів (напр. <br>)
        clean_description = re.sub(r'<[^>]+>', '', str(raw_description)).strip()

        # ==========================================
        # 3. ФОТОГРАФІЯ (Найкраща якість s1350x1350)
        # ==========================================
        images = raw_data.get("img") or {}
        raw_main_image_url = images.get("s1350x1350") or images.get("s350x350") or ""

        new_image = None
        if raw_main_image_url and media_proxy:
            try:
                new_image = media_proxy.process_image(
                    raw_url=raw_main_image_url,
                    product_sku=product_sku,
                    suffix="main",
                    folder_name="novus_products",
                    headers=NovusApiClient.HEADERS
                )
            except Exception:
                pass

        # ==========================================
        # 4. ВИМІРЮВАННЯ (Вага, Об'єм, Штуки)
        # ==========================================
        measurements = {"value": 1.0, "unit": "шт"}
        try:
            w = raw_data.get("weight")  # Зазвичай в грамах у Zakaz
            v = raw_data.get("volume")
            unit_type = raw_data.get("unit")  # 'pcs' або 'kg'

            if w and float(w) > 0:
                measurements = {"value": float(w), "unit": "г"}
            elif v and float(v) > 0:
                measurements = {"value": float(v), "unit": "мл"}
            elif unit_type == "kg":
                measurements = {"value": 1000.0, "unit": "г"}
        except:
            pass

        # ==========================================
        # ФІНАЛЬНИЙ СЛОВНИК
        # ==========================================
        return {
            "product_id": product_sku,
            "canonical_name": raw_data.get("title") or "Без назви",
            "brand": brand_name,
            "category": raw_data.get("category_id") or "Інше",  # Novus віддає ID категорії текстом (напр. "juice")
            "country": country_name,
            "media": {
                "raw_main_image": raw_main_image_url,
                "raw_gallery": [raw_main_image_url] if raw_main_image_url else [],
                "main_image": new_image,
                "gallery": [new_image] if new_image else []
            },
            "measurements": measurements,
            "pricing_logic": {"sales_unit": "piece", "unit_step": 1},
            "specific_attributes": {
                "is_tobacco": bool(raw_data.get("is_nicotine", False)),
                "is_18_plus": bool(raw_data.get("is_alcohol", False)),
                "description": clean_description
            },
            "offers": [{
                "store_id": "n_novus",
                "store_name": "Novus",
                "url": raw_data.get("web_url") or "",
                "is_in_stock": is_in_stock,
                "sku": original_sku,
                "scraped_at": current_time,
                "pricing": {
                    "regular_price": regular_price,
                    "current_price": current_price,
                    "discount_percent": discount_percent,
                    "is_online_only": False,
                    "promo_end_date": str(promo_end_date),
                    "bulk_discounts": []
                },
                "price_history": [{"date": current_time, "price": current_price, "regular_price": regular_price}]
            }]
        }