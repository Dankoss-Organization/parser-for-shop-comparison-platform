from typing import Dict, Any, Optional
from datetime import datetime, timezone
from core.base_adapter import BaseAdapter
from config import SILPO_BASE_IMG_URL, SILPO_HEADERS

class SilpoAdapter(BaseAdapter):
    """
    Adapter responsible for transforming raw Silpo supermarket API responses
    into the platform's unified product schema.

    This class extends `BaseAdapter` and implements the specific parsing logic
    required to handle Silpo's complex backend structure. It extracts nested
    attribute groups, computes dynamic pricing logic (including bulk discounts),
    identifies promotional flags, and delegates image handling to the media proxy.
    """

    def normalize(self, raw_data: Dict[str, Any], media_proxy: Any) -> Optional[Dict[str, Any]]:
        """
        Normalizes a single product's raw JSON data from the Silpo API.

        Logic Flow:
        1. **Data Validation:** Checks for the presence of `raw_data`. Returns
           None if the input is empty or invalid.
        2. **Attribute Extraction:** Iterates through nested `attributeGroups` to
           extract crucial nested data such as 'country', 'brand', and detailed
           nutritional facts ('calorie', 'proteins', 'fats', 'carbohydrates').
        3. **Pricing Calculation:** Evaluates 'price' and 'oldPrice'. Safely
           calculates the regular price and the exact discount percentage.
        4. **Promotions & Bulk Logic:** Scans the 'promotions' array for tags like
           "national-cashback" and "only_online". Parses the 'specialPrices' array
           to extract complex bulk discount rules (e.g., "buy N for X price"
           or "every Nth item discounted").
        5. **Media Processing:** Iterates over available raw images, forwarding
           them to the `media_proxy` for download and Cloudinary upload. It utilizes
           a specific `fallback_replace` parameter ("1000x1000/webp/") to handle
           Silpo's specific 404 image resolution errors on the fly.
        6. **Schema Construction:** Assembles all extracted data into the
           standardized dictionary format required by the resolution pipeline.

        Args:
            raw_data (Dict[str, Any]): The raw JSON dictionary returned by
                the Silpo API endpoint.
            media_proxy (Any): An instance of the media proxy service (e.g.,
                CloudinaryImageProxy) used to process, cache, and host images.

        Returns:
            Optional[Dict[str, Any]]: The fully populated and standardized
            product dictionary ready for the routing pipeline, or None if the
            input data is empty.
        """
        if not raw_data: return None

        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        product_sku = f"silpo_{raw_data.get('externalProductId')}"

        attributes = {"country": None, "brand": raw_data.get('brandTitle'), "calories": None, "proteins_g": None, "fats_g": None, "carbohydrates_g": None, "alcohol_percentage": None}
        for group in raw_data.get('attributeGroups', []):
            for attr in group.get('attributes', []):
                k = attr.get('attribute', {}).get('key')
                v = attr.get('value', {}).get('title')
                if k == 'country': attributes['country'] = v
                elif k == 'brand' and not attributes['brand']: attributes['brand'] = v
                elif k == 'alcoholcontent': attributes['alcohol_percentage'] = v
                elif k == 'calorie': attributes['calories'] = attr.get('value', {}).get('key') or v
                elif k == 'proteins': attributes['proteins_g'] = v
                elif k == 'fats': attributes['fats_g'] = v
                elif k == 'carbohydrates': attributes['carbohydrates_g'] = v

        category_path = " > ".join([p.get('title') for p in raw_data.get('path', []) if p.get('title')])

        current_price = raw_data.get('price', 0)
        old_price = raw_data.get('oldPrice') or 0
        regular_price = old_price if old_price > 0 else current_price
        discount_percent = round((1 - (current_price / old_price)) * 100) if old_price > current_price else 0

        promo_end = raw_data['promotionsDetails'][0].get('stopAt') if raw_data.get('promotionsDetails') else None
        is_national_cashback = any(p.get('id') == 'national-cashback' for p in raw_data.get('promotions', []))
        is_online_only = any(p.get('id') == 'only_online' for p in raw_data.get('promotions', []))

        bulk_discounts = []
        for sp in raw_data.get('specialPrices', []):
            sp_type = sp.get('type')
            if sp_type == 'from':
                bulk_discounts.append({"discount_type": "bulk_price", "min_quantity": sp.get('count'), "price_per_unit": sp.get('price'), "description": f"Ціна {sp.get('price')} грн при купівлі від {sp.get('count')} шт"})
            elif sp_type == 'every':
                bulk_discounts.append({"discount_type": "nth_item_discount", "min_quantity": sp.get('count'), "price_for_nth_item": sp.get('price'), "description": f"Кожна {sp.get('count')}-тя одиниця за {sp.get('price')} грн"})

        raw_images = raw_data.get('media', [])
        raw_main_image_url = f"{SILPO_BASE_IMG_URL}{raw_images[0]}" if raw_images else None
        cloud_main_image_url = None
        if raw_main_image_url:
            cloud_main_image_url = media_proxy.process_image(
                raw_url=raw_main_image_url,
                product_sku=product_sku,
                suffix="main",
                headers=SILPO_HEADERS,
                folder_name="silpo_products",
                fallback_replace=("1000x1000/webp/", "")
            )

        return {
            "product_id": product_sku, "canonical_name": raw_data.get('title'), "brand": attributes['brand'],
            "category": category_path, "country": attributes['country'],
            "media": {"raw_main_image": raw_main_image_url, "raw_gallery": [], "main_image": cloud_main_image_url, "gallery": []},
            "measurements": self.parse_measurements(raw_data.get('displayRatio')),
            "pricing_logic": {"sales_unit": "piece" if raw_data.get('ratio') == "шт" else "weight", "unit_step": raw_data.get('addToBasketStep', 1)},
            "specific_attributes": {
                "calories": attributes['calories'], "proteins_g": attributes['proteins_g'], "fats_g": attributes['fats_g'],
                "carbohydrates_g": attributes['carbohydrates_g'], "alcohol_percentage": attributes['alcohol_percentage'],
                "is_tobacco": raw_data.get('isTobacco', False), "is_18_plus": raw_data.get('blurForUnderAged', False),
                "is_national_cashback_eligible": is_national_cashback, "description": raw_data.get('descriptionRich') or raw_data.get('description')
            },
            "offers": [{
                "store_id": "s_silpo", "store_name": "Сільпо", "url": f"https://silpo.ua/product/{raw_data.get('slug')}",
                "is_in_stock": raw_data.get('stock', 0) > 0, "sku": str(raw_data.get('externalProductId')),
                "scraped_at": current_time,
                "store_rating": {"rating": raw_data.get('guestProductRating'), "reviews_count": raw_data.get('guestProductRatingCount')},
                "pricing": {"regular_price": regular_price, "current_price": current_price, "discount_percent": discount_percent, "is_online_only": is_online_only, "promo_end_date": promo_end, "bulk_discounts": bulk_discounts},
                "price_history": [{"date": current_time, "price": current_price, "regular_price": regular_price}]
            }]
        }