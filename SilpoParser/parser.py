import re
from datetime import datetime, timezone
from config import SILPO_BASE_IMG_URL
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


def build_unified_product(raw_data):
    if not raw_data:
        return None

    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    product_sku = f"silpo_{raw_data.get('externalProductId')}"

    # Збираємо атрибути
    attributes = {"country": None, "brand": raw_data.get('brandTitle'), "calories": None, "proteins_g": None,
                  "fats_g": None, "carbohydrates_g": None, "alcohol_percentage": None}
    for group in raw_data.get('attributeGroups', []):
        for attr in group.get('attributes', []):
            k = attr.get('attribute', {}).get('key')
            v = attr.get('value', {}).get('title')
            if k == 'country':
                attributes['country'] = v
            elif k == 'brand' and not attributes['brand']:
                attributes['brand'] = v
            elif k == 'alcoholcontent':
                attributes['alcohol_percentage'] = v
            elif k == 'calorie':
                attributes['calories'] = attr.get('value', {}).get('key') or v
            elif k == 'proteins':
                attributes['proteins_g'] = v
            elif k == 'fats':
                attributes['fats_g'] = v
            elif k == 'carbohydrates':
                attributes['carbohydrates_g'] = v

    category_path = " > ".join([p.get('title') for p in raw_data.get('path', []) if p.get('title')])

    # Ціни та акції
    current_price = raw_data.get('price', 0)
    old_price = raw_data.get('oldPrice') or 0
    regular_price = old_price if old_price > 0 else current_price
    discount_percent = round((1 - (current_price / old_price)) * 100) if old_price > current_price else 0

    promo_end = raw_data['promotionsDetails'][0].get('stopAt') if raw_data.get('promotionsDetails') else None

    is_national_cashback = any(p.get('id') == 'national-cashback' for p in raw_data.get('promotions', []))
    is_online_only = any(p.get('id') == 'only_online' for p in raw_data.get('promotions', []))

    # Оптові знижки (bulk discounts)
    bulk_discounts = []
    for sp in raw_data.get('specialPrices', []):
        sp_type = sp.get('type')
        if sp_type == 'from':
            bulk_discounts.append(
                {"discount_type": "bulk_price", "min_quantity": sp.get('count'), "price_per_unit": sp.get('price'),
                 "description": f"Ціна {sp.get('price')} грн при купівлі від {sp.get('count')} шт"})
        elif sp_type == 'every':
            bulk_discounts.append({"discount_type": "nth_item_discount", "min_quantity": sp.get('count'),
                                   "price_for_nth_item": sp.get('price'),
                                   "description": f"Кожна {sp.get('count')}-тя одиниця за {sp.get('price')} грн"})

    # Зображення
    raw_images = raw_data.get('media', [])
    raw_gallery_urls = [f"{SILPO_BASE_IMG_URL}{img}" for img in raw_images]
    raw_main_image_url = raw_gallery_urls[0] if raw_gallery_urls else None

    new_gallery = []
    for idx, raw_img_url in enumerate(raw_gallery_urls):
        suffix = "main" if idx == 0 else f"gallery_{idx}"
        new_gallery_img = download_and_save_image(raw_img_url, product_sku, suffix)
        if new_gallery_img:
            new_gallery.append(new_gallery_img)

    new_main_image = new_gallery[0] if new_gallery else None

    return {
        "product_id": product_sku,
        "canonical_name": raw_data.get('title'),
        "brand": attributes['brand'],
        "category": category_path,
        "country": attributes['country'],
        "media": {
            "raw_main_image": raw_main_image_url,
            "raw_gallery": raw_gallery_urls,
            "main_image": new_main_image,
            "gallery": new_gallery
        },
        "measurements": parse_measurements(raw_data.get('displayRatio')),
        "pricing_logic": {"sales_unit": "piece" if raw_data.get('ratio') == "шт" else "weight",
                          "unit_step": raw_data.get('addToBasketStep', 1)},
        "specific_attributes": {
            "calories": attributes['calories'], "proteins_g": attributes['proteins_g'], "fats_g": attributes['fats_g'],
            "carbohydrates_g": attributes['carbohydrates_g'], "alcohol_percentage": attributes['alcohol_percentage'],
            "is_tobacco": raw_data.get('isTobacco', False), "is_18_plus": raw_data.get('blurForUnderAged', False),
            "is_national_cashback_eligible": is_national_cashback,
            "description": raw_data.get('descriptionRich') or raw_data.get('description')
        },
        "offers": [{
            "store_id": "s_silpo", "store_name": "Сільпо", "url": f"https://silpo.ua/product/{raw_data.get('slug')}",
            "is_in_stock": raw_data.get('stock', 0) > 0, "sku": str(raw_data.get('externalProductId')),
            "scraped_at": current_time,
            "store_rating": {
                "rating": raw_data.get('guestProductRating'),
                "reviews_count": raw_data.get('guestProductRatingCount')
            },
            "pricing": {
                "regular_price": regular_price, "current_price": current_price,
                "discount_percent": discount_percent, "is_online_only": is_online_only,
                "promo_end_date": promo_end, "bulk_discounts": bulk_discounts
            },
            "price_history": [{
                "date": current_time,
                "price": current_price,
                "regular_price": regular_price
            }]
        }]
    }