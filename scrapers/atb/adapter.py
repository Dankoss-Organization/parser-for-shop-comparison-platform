import json
import re
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from core.base_adapter import BaseAdapter


class AtbAdapter(BaseAdapter):

    def normalize(self, raw_data: Dict[str, Any], media_proxy: Any) -> Optional[Dict[str, Any]]:

        if not raw_data or "html" not in raw_data:
            return None

        soup = BeautifulSoup(raw_data["html"], 'html.parser')
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        url_slug = raw_data.get("url_slug", "")
        product_url = f"https://www.atbmarket.com{url_slug}" if url_slug else ""

        # Шукаємо блок кошика (він є і на сторінці товару)
        cart_data = soup.find('div', class_='b-addToCart')
        if not cart_data:
            return None

        # Базові дані з дата-атрибутів кошика
        product_id = cart_data.get('data-productid')
        product_sku = f"atb_{product_id}"
        brand = cart_data.get('data-brand', "Невідомо")
        category = cart_data.get('data-category', "")

        # Назва товару (на сторінці товару це H1)
        title_elem = soup.find('h1', class_='product-page__title')
        title = title_elem.text.strip() if title_elem else "Невідомий товар"

        # Ініціалізуємо змінні, які спробуємо дістати з JSON-LD
        img_url = ""
        regular_price = 0.0
        description = "Немає опису"

        # Витягуємо точні дані з JSON-LD (мікродані сторінки)
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    if not img_url:
                        img_url = data.get('image', '')
                    if 'offers' in data and isinstance(data['offers'], dict):
                        regular_price = float(data['offers'].get('price', 0.0))
                    if 'description' in data:
                        description = data.get('description', description)
                    if 'brand' in data and isinstance(data['brand'], dict) and brand == "Невідомо":
                        brand = data['brand'].get('name', brand)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

        # Якщо JSON-LD не відпрацював, шукаємо ціну в HTML (як у твоєму старому коді)
        if regular_price == 0.0:
            price_top_elem = soup.find('data', class_='product-price__top')
            if price_top_elem and price_top_elem.has_attr('value'):
                regular_price = float(price_top_elem['value'])

        # Перевіряємо чи є ціна по картці АТБ (це буде current_price, а regular_price - без знижки)
        current_price = regular_price
        card_price_elem = soup.find('data', class_='atbcard-sale__price-top')
        if card_price_elem and card_price_elem.has_attr('value'):
            try:
                current_price = float(card_price_elem['value'])
            except ValueError:
                pass

        # Рахуємо знижку
        discount_percent = 0
        if regular_price > current_price:
            discount_percent = round((1 - (current_price / regular_price)) * 100)

        # Обробка зображення
        if img_url and not img_url.startswith('http'):
            img_url = f"https://www.atbmarket.com{img_url}"

        cloud_main_image_url = None
        if img_url and media_proxy:
            cloud_main_image_url = media_proxy.process_image(
                raw_url=img_url,
                product_sku=product_sku,
                suffix="main",
                headers={},
                folder_name="atb_products"
            )

        # Перевірка на Національний Кешбек
        is_national_cashback = bool(soup.find('span', string=re.compile(r'Національний Кешбек', re.I)))

        # Вага
        weight_str = cart_data.get('data-weight', "0")
        weight_val = float(weight_str) * 1000 if weight_str else 0
        measurements = {"value": weight_val, "unit": "g"} if weight_val > 0 else {"value": 1.0, "unit": "pcs"}

        # Повертаємо твій фірмовий словник
        return {
            "product_id": product_sku,
            "canonical_name": title,
            "brand": brand,
            "category": category,
            "country": "Україна",
            "media": {
                "raw_main_image": img_url,
                "raw_gallery": [],
                "main_image": cloud_main_image_url,
                "gallery": []
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
                "is_18_plus": "алкоголь" in category.lower() or "тютюн" in category.lower(),
                "is_national_cashback_eligible": is_national_cashback,
                "description": description
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