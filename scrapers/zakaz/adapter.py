import re
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from core.base_adapter import BaseAdapter


class ZakazAdapter(BaseAdapter):
    def __init__(self, chain_name: str, display_name: str):
        self.chain_name = chain_name  # 'auchan' або 'novus'
        self.display_name = display_name  # 'Auchan' або 'Novus'

    def normalize(self, raw_data: Dict[str, Any], media_proxy: Any = None) -> Optional[Dict[str, Any]]:
        if not raw_data or not isinstance(raw_data, dict): return None

        original_sku = str(raw_data.get("ean") or raw_data.get("sku") or "")
        if not original_sku: return None

        # Динамічний SKU: auchan_123456 або novus_123456
        product_sku = f"{self.chain_name}_{original_sku}"
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Ціни в копійках
        raw_price = raw_data.get("price") or 0
        regular_price = float(raw_price) / 100.0

        discount_info = raw_data.get("discount") or {}
        if discount_info.get("status", False):
            current_price = regular_price
            regular_price = float(discount_info.get("old_price") or raw_price) / 100.0
            discount_percent = int(discount_info.get("value") or 0)
            promo_end_date = discount_info.get("due_date") or ""
        else:
            current_price = regular_price
            discount_percent = 0
            promo_end_date = ""

        brand_name = (raw_data.get("producer") or {}).get("trademark") or "Без бренду"
        clean_description = self.strip_html(raw_data.get("description") or "")

        # Фото
        images = raw_data.get("img") or {}
        raw_main_image_url = images.get("s1350x1350") or images.get("s350x350") or ""
        new_image = None
        if raw_main_image_url and media_proxy:
            try:
                new_image = media_proxy.process_image(
                    raw_url=raw_main_image_url,
                    product_sku=product_sku,
                    suffix="main",
                    folder_name=f"{self.chain_name}_products"
                )
            except Exception:
                pass

        # Вимірювання
        measurements = {"value": 1.0, "unit": "шт"}
        try:
            w, v, u = raw_data.get("weight"), raw_data.get("volume"), raw_data.get("unit")
            if w and float(w) > 0:
                measurements = {"value": float(w), "unit": "г"}
            elif v and float(v) > 0:
                measurements = {"value": float(v), "unit": "мл"}
            elif u == "kg":
                measurements = {"value": 1000.0, "unit": "г"}
        except:
            pass

        return {
            "product_id": product_sku,
            "canonical_name": raw_data.get("title") or "Без назви",
            "brand": brand_name,
            "category": raw_data.get("category_id") or "Інше",
            "country": raw_data.get("country") or "Не вказано",
            "raw_main_image": raw_main_image_url,
            "main_image": new_image,
            "measurements": measurements,
            "pricing_logic": {"sales_unit": "piece", "unit_step": 1},
            "specific_attributes": {
                "is_tobacco": bool(raw_data.get("is_nicotine", False)),
                "is_18_plus": bool(raw_data.get("is_alcohol", False)),
                "description": clean_description
            },
            "offers": [{
                "store_id": f"z_{self.chain_name}",
                "store_name": self.display_name,
                "url": raw_data.get("web_url") or "",
                "is_in_stock": bool(raw_data.get("in_stock", False)),
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