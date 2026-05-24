from typing import Dict, Any, Optional
from datetime import datetime, timezone
from core.base_adapter import BaseAdapter
from config import FORA_HEADERS


class ForaAdapter(BaseAdapter):
    """
    Adapter responsible for transforming raw Fora supermarket API responses
    into the platform's unified product schema.

    This class extends `BaseAdapter` and implements the specific parsing logic
    required to handle Fora's unique backend structure. It extracts nested
    attributes, computes pricing logic, identifies promotional flags, and
    delegates image handling to the media proxy.
    """

    def normalize(self, json_response: Dict[str, Any], media_proxy: Any) -> Optional[Dict[str, Any]]:
        """
        Normalizes a single product's raw JSON data from the Fora API.

        Logic Flow:
        1. **Data Validation:** Checks for the presence of the root 'item' node.
           If absent, it aborts processing and returns None.
        2. **Attribute Extraction:** Iterates through the 'parameters' list to
           extract crucial nested data such as 'country', 'trademark' (brand),
           and 'calorie' values.
        3. **Pricing Calculation:** Evaluates 'price' and 'oldPrice'. If an old
           price exists and is greater than the current price, it automatically
           calculates the exact discount percentage.
        4. **Promotional Flags:** Scans the 'bubbles' array to detect if the item
           qualifies for the "National Cashback" program ('natsionalnyi-keshbek').
        5. **Media Processing:** Iterates over available raw images, forwarding
           them to the `media_proxy` for download and Cloudinary upload.
        6. **Schema Construction:** Assembles all extracted data into the
           standardized dictionary format required by the resolution pipeline.

        Args:
            json_response (Dict[str, Any]): The raw JSON dictionary returned by
                the Fora API endpoint.
            media_proxy (Any): An instance of the media proxy service (e.g.,
                CloudinaryImageProxy) used to process and host images.

        Returns:
            Optional[Dict[str, Any]]: The fully populated and standardized
            product dictionary, or None if the input data is invalid/empty.
        """
        raw_data = json_response.get('item')
        if not raw_data:
            return None

        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        product_sku = f"fora_{raw_data.get('id')}"

        attributes = {
            "country": None,
            "brand": None,
            "calories": None,
            "proteins_g": None,
            "fats_g": None,
            "carbohydrates_g": None
        }

        for param in (raw_data.get('parameters') or []):
            k = param.get('key')
            v = param.get('value')
            if k == 'country':
                attributes['country'] = v
            elif k == 'trademark':
                attributes['brand'] = v
            elif k == 'calorie':
                attributes['calories'] = v

        category_path = raw_data.get('category', {}).get('name') if raw_data.get('category') else "Невідома категорія"

        current_price = raw_data.get('price', 0)
        old_price = raw_data.get('oldPrice')

        if old_price and old_price > current_price:
            regular_price = old_price
            discount_percent = round((1 - (current_price / old_price)) * 100)
        else:
            regular_price = current_price
            discount_percent = 0

        is_national_cashback = any(b.get('id') == 'natsionalnyi-keshbek' for b in (raw_data.get('bubbles') or []))

        raw_main_image_url = raw_data.get('mainImage')

        if not raw_main_image_url and raw_data.get('images'):
            raw_main_image_url = raw_data['images'][0].get('path')

        cloud_main_image_url = None
        if raw_main_image_url:
            cloud_main_image_url = media_proxy.process_image(
                raw_url=raw_main_image_url,
                product_sku=product_sku,
                suffix="main",
                headers=FORA_HEADERS,
                folder_name="fora_products"
            )

        return {
            "product_id": product_sku,
            "canonical_name": raw_data.get('name'),
            "brand": attributes['brand'],
            "category": category_path,
            "country": attributes['country'],
            "media": {
                "raw_main_image": raw_main_image_url,
                "raw_gallery": [],
                "main_image": cloud_main_image_url,
                "gallery": []
            },
            "measurements": self.parse_measurements(raw_data.get('unit')),
            "pricing_logic": {
                "sales_unit": "weight" if raw_data.get('isWeightedProduct') else "piece",
                "unit_step": raw_data.get('unitStep', 1)
            },
            "specific_attributes": {
                "calories": attributes['calories'],
                "is_national_cashback_eligible": is_national_cashback
            },
            "offers": [{
                "store_id": "f_fora",
                "store_name": "Фора",
                "url": f"https://fora.ua/product/{raw_data.get('slug')}",
                "is_in_stock": raw_data.get('calcStoreQuantity', 0) > 0,
                "sku": str(raw_data.get('id')),
                "scraped_at": current_time,
                "store_rating": {
                    "rating": raw_data.get('rating'),
                    "reviews_count": raw_data.get('votesCount')
                },
                "pricing": {
                    "regular_price": regular_price,
                    "current_price": current_price,
                    "discount_percent": discount_percent,
                    "is_online_only": False,
                    "promo_end_date": None,
                    "bulk_discounts": []
                },
                "price_history": [{
                    "date": current_time,
                    "price": current_price,
                    "regular_price": regular_price
                }]
            }]
        }