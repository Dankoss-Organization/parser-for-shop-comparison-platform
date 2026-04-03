import re
from datetime import datetime, timezone
from media_manager import download_and_save_image


def parse_measurements(ratio_str):
    if not ratio_str:
        return {"value": 1.0, "unit": "pcs"}

    match = re.match(r"([\d\.,]+)\s*([а-яa-zA-Z]+)", ratio_str.lower().strip().replace(',', '.'))
    if match:
        val = float(match.group(1))
        unit = match.group(2)
        unit_map = {"г": "g", "g": "g", "кг": "kg", "kg": "kg", "л": "l", "l": "l", "мл": "ml", "ml": "ml", "шт": "pcs",
                    "pcs": "pcs"}
        return {"value": val, "unit": unit_map.get(unit, unit)}

    return {"value": 1.0, "unit": "pcs"}


def safe_float(val):
    """Конвертує рядок типу '1.5' або '0' у float. Повертає None у разі помилки."""
    if val is None:
        return None
    try:
        return float(str(val).replace(',', '.'))
    except ValueError:
        return None


def build_unified_product_fora(json_response):
    item = json_response.get('item')
    if not item:
        return None

    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    product_sku = f"fora_{item.get('id')}"

    # Збираємо атрибути з "parameters"
    attributes = {
        "country": None, "brand": None, "calories": None,
        "proteins_g": None, "fats_g": None, "carbohydrates_g": None,
        "alcohol_percentage": None, "warning_type": None
    }

    for param in item.get('parameters', []):
        k = param.get('key')
        v = param.get('value')
        if k == 'country':
            attributes['country'] = v
        elif k == 'trademark':
            attributes['brand'] = v
        elif k == 'calorie':
            attributes['calories'] = v
        elif k == 'proteins':
            attributes['proteins_g'] = safe_float(v)
        elif k == 'fats':
            attributes['fats_g'] = safe_float(v)
        elif k == 'carbohydrates':
            attributes['carbohydrates_g'] = safe_float(v)
        elif k == 'alcoholContent':
            attributes['alcohol_percentage'] = str(v)
        elif k == 'warningType':
            attributes['warning_type'] = v

    # Логіка для 18+ та тютюну
    is_tobacco = attributes['warning_type'] == 'tobacco'
    is_18_plus = attributes['warning_type'] in ['alcohol', 'tobacco'] or attributes['alcohol_percentage'] is not None

    # Категорії (у Форі вони часто null в масиві, тому беремо вкладений об'єкт category)
    cat_names = [c.get('name') for c in item.get('categories', []) if c.get('name')]
    if cat_names:
        category_path = " > ".join(cat_names)
    else:
        category_path = item.get('category', {}).get('name')

    # Ціни
    current_price = item.get('price', 0)
    old_price = item.get('oldPrice') or 0
    regular_price = old_price if old_price > 0 else current_price

    # Вираховуємо відсоток знижки (беремо готове поле priceDiscountValue або рахуємо)
    discount_percent = 0
    discount_data = item.get('priceDiscountValue')
    if discount_data and discount_data.get('value'):
        try:
            discount_percent = abs(int(discount_data.get('value')))
        except ValueError:
            discount_percent = round((1 - (current_price / old_price)) * 100) if old_price > current_price else 0
    elif old_price > current_price:
        discount_percent = round((1 - (current_price / old_price)) * 100)

    # Дата кінця акції
    promo_end_raw = item.get('priceStopAfter')
    promo_end = None
    if promo_end_raw:
        try:
            # Перетворюємо "30.04.2026" у "2026-04-30T23:59:59Z"
            promo_end = datetime.strptime(promo_end_raw, "%d.%m.%Y").strftime("%Y-%m-%dT23:59:59Z")
        except ValueError:
            promo_end = promo_end_raw

    # Інші специфічні дані
    is_national_cashback = any(b.get('id') == 'natsionalnyi-keshbek' for b in item.get('bubbles', []))

    description = "no desc yet"
    if item.get('promotion') and item.get('promotion').get('description'):
        description = item.get('promotion').get('description')

    # Зображення
    raw_main_image_url = item.get('mainImage')
    raw_gallery_urls = [img.get('path') for img in item.get('images', []) if img.get('path')]
    if not raw_gallery_urls and raw_main_image_url:
        raw_gallery_urls = [raw_main_image_url]

    new_gallery = []
    for idx, raw_img_url in enumerate(raw_gallery_urls):
        suffix = "main" if idx == 0 else f"gallery_{idx}"
        new_gallery_img = download_and_save_image(raw_img_url, product_sku, suffix)
        if new_gallery_img:
            new_gallery.append(new_gallery_img)

    new_main_image = new_gallery[0] if new_gallery else None

    return {
        "product_id": product_sku,
        "canonical_name": item.get('name'),
        "brand": attributes['brand'],
        "category": category_path,
        "country": attributes['country'],
        "media": {
            "raw_main_image": raw_main_image_url,
            "raw_gallery": raw_gallery_urls,
            "main_image": new_main_image,
            "gallery": new_gallery
        },
        "measurements": parse_measurements(item.get('unit')),
        "pricing_logic": {
            "sales_unit": "weight" if item.get('isWeightedProduct') else "piece",
            "unit_step": item.get('unitStep', 1)
        },
        "specific_attributes": {
            "calories": attributes['calories'],
            "proteins_g": attributes['proteins_g'],
            "fats_g": attributes['fats_g'],
            "carbohydrates_g": attributes['carbohydrates_g'],
            "alcohol_percentage": attributes['alcohol_percentage'],
            "is_tobacco": is_tobacco,
            "is_18_plus": is_18_plus,
            "is_national_cashback_eligible": is_national_cashback,
            "description": description
        },
        "offers": [{
            "store_id": "f_fora",
            "store_name": "Фора",
            "url": f"https://fora.ua/product/{item.get('slug')}",
            "is_in_stock": item.get('calcStoreQuantity', 0) > 0,
            "sku": str(item.get('id')),
            "scraped_at": current_time,
            "store_rating": {
                "rating": item.get('rating'),
                "reviews_count": item.get('votesCount')
            },
            "pricing": {
                "regular_price": regular_price,
                "current_price": current_price,
                "discount_percent": discount_percent,
                "is_online_only": False,
                "promo_end_date": promo_end,
                "bulk_discounts": []
            },
            "price_history": [{
                "date": current_time,
                "price": current_price,
                "regular_price": regular_price
            }]
        }]
    }
