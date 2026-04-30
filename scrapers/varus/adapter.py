from typing import Dict, Any, Optional
from datetime import datetime, timezone
from core.base_adapter import BaseAdapter


class VarusAdapter(BaseAdapter):
    """
    Адаптер для перетворення сирих JSON-відповідей API Varus
    в уніфіковану схему платформи із захистом типів даних.
    """

    def normalize(self, raw_data: Dict[str, Any], media_proxy: Any = None) -> Optional[Dict[str, Any]]:
        if not raw_data:
            return None

        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        original_sku = str(raw_data.get("sku") or raw_data.get("id"))
        product_sku = f"varus_{original_sku}"

        regular_price = float(raw_data.get("regular_price", 0) or 0)
        special_price = raw_data.get("special_price_discount")
        current_price = float(special_price) if special_price else regular_price

        discount_percent = 0
        if regular_price > current_price:
            discount_percent = round((1 - (current_price / regular_price)) * 100)

        # Обробка зображень
        raw_image_path = raw_data.get("image")
        raw_main_image_url = None
        if raw_image_path:
            raw_main_image_url = f"https://varus.ua/img/product/{raw_image_path}" if not str(raw_image_path).startswith(
                "http") else raw_image_path

        new_image = None
        if raw_main_image_url and media_proxy:
            new_image = media_proxy.process_image(
                raw_url=raw_main_image_url,
                product_sku=product_sku,
                suffix="main",
                folder_name="varus_products"
            )

        # === ВИПРАВЛЕННЯ 1: Форматування measurements ===
        # Varus віддає вагу як int (напр. 500). MLMatcher очікує словник.
        measurements = None
        weight = raw_data.get("weight")
        volume = raw_data.get("volume")
        if weight:
            measurements = {"value": float(weight), "unit": "g"}
        elif volume:
            measurements = {"value": float(volume), "unit": "ml"}

        # === ВИПРАВЛЕННЯ 2: Захист від int/string у вкладених об'єктах ===
        brand_data = raw_data.get("brand_data")
        brand_name = brand_data.get("name") if isinstance(brand_data, dict) else str(brand_data) if brand_data else None

        stock_data = raw_data.get("stock")
        is_in_stock = stock_data.get("is_in_stock", True) if isinstance(stock_data, dict) else True

        return {
            "product_id": product_sku,
            "canonical_name": raw_data.get("name"),
            "brand": brand_name,
            "category": None,
            "country": None,
            "media": {
                "raw_main_image": raw_main_image_url,
                "raw_gallery": [raw_main_image_url] if raw_main_image_url else [],
                "main_image": new_image,
                "gallery": [new_image] if new_image else []
            },
            "measurements": measurements,  # <-- Тепер тут правильний словник або None
            "pricing_logic": {
                "sales_unit": "piece",
                "unit_step": 1
            },
            "specific_attributes": {
                "is_tobacco": bool(raw_data.get("is_tobacco", False)),
                "is_18_plus": bool(raw_data.get("is_18_plus", False)),
                "description": raw_data.get("description")
            },
            "offers": [{
                "store_id": "s_varus",
                "store_name": "Varus",
                "url": f"https://varus.ua/product/{raw_data.get('url_key')}",
                "is_in_stock": is_in_stock,
                "sku": original_sku,
                "scraped_at": current_time,
                "store_rating": None,
                "pricing": {
                    "regular_price": regular_price,
                    "current_price": current_price,
                    "discount_percent": discount_percent,
                    "is_online_only": False,
                    "promo_end_date": raw_data.get("special_price_to_date"),
                    "bulk_discounts": []
                },
                "price_history": [{"date": current_time, "price": current_price, "regular_price": regular_price}]
            }]
        }