from typing import Dict, Any, Optional
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import re
from core.base_adapter import BaseAdapter


class AtbAdapter(BaseAdapter):

    def normalize(self, raw_data: Dict[str, Any], media_proxy: Any) -> Optional[Dict[str, Any]]:

        if not raw_data or "html" not in raw_data:
            return None

        soup = BeautifulSoup(raw_data["html"], 'html.parser')
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        cart_data = soup.find('div', class_='b-addToCart')
        if not cart_data:
            return None

        product_id = cart_data.get('data-productid')
        product_sku = f"atb_{product_id}"
        brand = cart_data.get('data-brand', "Невідомо")
        category = cart_data.get('data-category', "")

        title_elem = soup.find('div', class_='catalog-item__title')
        title = title_elem.text.strip() if title_elem else "Невідомий товар"

        url_elem = title_elem.find('a') if title_elem else None
        product_url = f"https://www.atbmarket.com{url_elem['href']}" if url_elem and 'href' in url_elem.attrs else ""

        price_top_elem = soup.find('data', class_='product-price__top')
        price_bottom_elem = soup.find('data', class_='product-price__bottom')

        current_price = float(price_top_elem['value']) if price_top_elem else 0.0
        regular_price = float(price_bottom_elem['value']) if price_bottom_elem else current_price

        discount_percent = 0
        if regular_price > current_price:
            discount_percent = round((1 - (current_price / regular_price)) * 100)

        img_elem = soup.find('img', class_='catalog-item__img')
        img_url = img_elem['src'] if img_elem else ""
        if img_url and not img_url.startswith('http'):
            img_url = f"https://www.atbmarket.com{img_url}"

        raw_gallery_urls = [img_url] if img_url else []

        new_gallery = []
        if raw_gallery_urls and media_proxy:
            new_img = media_proxy.process_image(
                raw_url=img_url,
                product_sku=product_sku,
                suffix="main",
                headers={},
                folder_name="atb_products"
            )
            if new_img:
                new_gallery.append(new_img)

        is_national_cashback = bool(soup.find('span', string=re.compile(r'Національний Кешбек', re.I)))

        weight_str = cart_data.get('data-weight', "0")
        weight_val = float(weight_str) * 1000 if weight_str else 0
        measurements = {"value": weight_val, "unit": "g"} if weight_val > 0 else {"value": 1.0, "unit": "pcs"}

        return {
            "product_id": product_sku,
            "canonical_name": title,
            "brand": brand,
            "category": category,
            "country": "Україна",
            "media": {
                "raw_main_image": img_url,
                "raw_gallery": raw_gallery_urls,
                "main_image": new_gallery[0] if new_gallery else None,
                "gallery": new_gallery
            },
            "measurements": measurements,
            "pricing_logic": {"sales_unit": "piece", "unit_step": 1},
            "specific_attributes": {
                "calories": None,
                "proteins_g": None,
                "fats_g": None,
                "carbohydrates_g": None,
                "alcohol_percentage": None,
                "is_tobacco": False,
                "is_18_plus": False,
                "is_national_cashback_eligible": is_national_cashback,
                "description": "no desc yet"
            },
            "offers": [{
                "store_id": "a_atb",
                "store_name": "АТБ",
                "url": product_url,
                "is_in_stock": True,
                "sku": str(product_id),
                "scraped_at": current_time,
                "store_rating": {"rating": 5.0, "reviews_count": 0},
                "pricing": {
                    "regular_price": regular_price,
                    "current_price": current_price,
                    "discount_percent": discount_percent,
                    "is_online_only": False,
                    "promo_end_date": None,
                    "bulk_discounts": []
                },
                "price_history": [{"date": current_time, "price": current_price, "regular_price": regular_price}]
            }]
        }