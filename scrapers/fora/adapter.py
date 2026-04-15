from datetime import datetime, timezone
from core.base_adapter import BaseAdapter
from config import FORA_HEADERS

class ForaAdapter(BaseAdapter):
    def normalize(self, json_response, media_proxy):
        raw_data = json_response.get('item')
        if not raw_data: return None

        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        product_sku = f"fora_{raw_data.get('id')}"

        attributes = {"country": None, "brand": None, "calories": None, "proteins_g": None, "fats_g": None, "carbohydrates_g": None}
        for param in raw_data.get('parameters', []):
            k = param.get('key')
            v = param.get('value')
            if k == 'country': attributes['country'] = v
            elif k == 'trademark': attributes['brand'] = v
            elif k == 'calorie': attributes['calories'] = v

        category_path = raw_data.get('category', {}).get('name')
        current_price = raw_data.get('price', 0)
        old_price = raw_data.get('oldPrice')

        if old_price and old_price > current_price:
            regular_price = old_price
            discount_percent = round((1 - (current_price / old_price)) * 100)
        else:
            regular_price = current_price
            discount_percent = 0

        is_national_cashback = any(b.get('id') == 'natsionalnyi-keshbek' for b in raw_data.get('bubbles', []))

        raw_main_image_url = raw_data.get('mainImage')
        raw_gallery_urls = [img.get('path') for img in raw_data.get('images', []) if img.get('path')]
        if not raw_gallery_urls and raw_main_image_url:
            raw_gallery_urls = [raw_main_image_url]

        new_gallery = []
        for idx, raw_img_url in enumerate(raw_gallery_urls):
            suffix = "main" if idx == 0 else f"gallery_{idx}"
            new_gallery_img = media_proxy.process_image(
                raw_url=raw_img_url, product_sku=product_sku, suffix=suffix,
                headers=FORA_HEADERS, folder_name="fora_products"
            )
            if new_gallery_img: new_gallery.append(new_gallery_img)

        return {
            "product_id": product_sku, "canonical_name": raw_data.get('name'), "brand": attributes['brand'],
            "category": category_path, "country": attributes['country'],
            "media": {"raw_main_image": raw_main_image_url, "raw_gallery": raw_gallery_urls, "main_image": new_gallery[0] if new_gallery else None, "gallery": new_gallery},
            "measurements": self.parse_measurements(raw_data.get('unit')),
            "pricing_logic": {"sales_unit": "weight" if raw_data.get('isWeightedProduct') else "piece", "unit_step": raw_data.get('unitStep', 1)},
            "specific_attributes": {"calories": attributes['calories'], "is_national_cashback_eligible": is_national_cashback},
            "offers": [{
                "store_id": "f_fora", "store_name": "Фора", "url": f"https://fora.ua/product/{raw_data.get('slug')}",
                "is_in_stock": raw_data.get('calcStoreQuantity', 0) > 0, "sku": str(raw_data.get('id')),
                "scraped_at": current_time,
                "store_rating": {"rating": raw_data.get('rating'), "reviews_count": raw_data.get('votesCount')},
                "pricing": {"regular_price": regular_price, "current_price": current_price, "discount_percent": discount_percent, "is_online_only": False, "promo_end_date": None, "bulk_discounts": []},
                "price_history": [{"date": current_time, "price": current_price, "regular_price": regular_price}]
            }]
        }