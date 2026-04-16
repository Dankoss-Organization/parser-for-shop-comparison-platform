import uuid
from sqlalchemy.orm import Session
from sqlalchemy import cast, Float
from .models import Product, Offer


class Repository:
    def __init__(self, db: Session):
        self.db = db

    def find_offer_by_store_sku(self, store_sku: str):
        return self.db.query(Offer).filter(Offer.store_sku == store_sku).first()

    def update_offer_price(self, offer_id: str, new_price: float):
        try:
            offer = self.db.query(Offer).filter(Offer.id == offer_id).first()
            if offer:
                offer.current_price = new_price
                self.db.commit()
            return offer
        except Exception as e:
            self.db.rollback()
            raise e

    def find_product_by_barcode(self, barcode: str):
        return None

    def find_products_by_brand_and_weight(self, brand: str, weight_value: float):
        if not brand or not weight_value:
            return []

        candidates = self.db.query(Product).filter(Product.brand == brand).all()

        valid_candidates = []
        for c in candidates:
            if c.measurements and isinstance(c.measurements, dict):
                val = c.measurements.get('value')
                if val is not None:
                    try:
                        if float(val) == float(weight_value):
                            valid_candidates.append(c)
                    except (ValueError, TypeError):
                        pass
        return valid_candidates

    def create_product(self, unified_item: dict) -> str:
        try:
            new_id = str(uuid.uuid4())
            spec_attr = unified_item.get('specific_attributes', {})

            product = Product(
                id=new_id,
                productId=unified_item.get('product_id'),
                canonical_name=unified_item.get('canonical_name'),
                brand=unified_item.get('brand'),
                country=unified_item.get('country'),

                media=unified_item.get('media'),
                measurements=unified_item.get('measurements'),
                pricing_logic=unified_item.get('pricing_logic'),

                description=spec_attr.get('description'),

                calories=str(spec_attr.get('calories')) if spec_attr.get('calories') is not None else None,
                proteins_g=str(spec_attr.get('proteins_g')) if spec_attr.get('proteins_g') is not None else None,
                fats_g=str(spec_attr.get('fats_g')) if spec_attr.get('fats_g') is not None else None,
                carbohydrates_g=str(spec_attr.get('carbohydrates_g')) if spec_attr.get(
                    'carbohydrates_g') is not None else None,
                alcohol_percentage=str(spec_attr.get('alcohol_percentage')) if spec_attr.get(
                    'alcohol_percentage') is not None else None,

                is_tobacco=spec_attr.get('is_tobacco', False),
                is_18_plus=spec_attr.get('is_18_plus', False),
                is_national_cashback_eligible=spec_attr.get('is_national_cashback_eligible', False)
            )
            self.db.add(product)
            self.db.commit()
            return new_id
        except Exception as e:
            self.db.rollback()  # Відкочуємо транзакцію при збої
            raise e

    def create_offer(self, product_id: str, offer_data: dict, store_sku: str):
        try:
            offer_id = str(uuid.uuid4())
            offer = Offer(
                id=offer_id,
                product_id=product_id,
                store_sku=store_sku,
                store_id=offer_data.get('store_id'),
                current_price=offer_data['pricing']['current_price']
            )
            self.db.add(offer)
            self.db.commit()
            return offer_id
        except Exception as e:
            self.db.rollback()  # Відкочуємо транзакцію при збої
            raise e