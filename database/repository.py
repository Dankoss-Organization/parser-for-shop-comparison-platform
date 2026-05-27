import uuid
from datetime import datetime, timezone  # ДОДАНО: для фіксації часу
from sqlalchemy.orm import Session
from sqlalchemy import cast, Float
from .models import Product, Offer, Category, PriceHistory  # ДОДАНО: імпорт PriceHistory


class Repository:
    """
    Data Access Layer (DAL) for the Shop Comparison Platform.

    This class abstracts all direct database interactions using SQLAlchemy.
    It provides a clean interface for querying, creating, and updating
    products and their store-specific offers, ensuring that business logic
    (like routers and pipelines) is completely decoupled from SQL queries.
    """

    def __init__(self, db: Session):
        """
        Initializes the repository with an active database session.

        Args:
            db (Session): The active SQLAlchemy session instance used to execute
                transactions and queries.
        """
        self.db = db
        self.session = db

    def _record_price_history(self, offer_id: str, new_price: float, regular_price: float):
        """
        Смарт-логіка історії цін: записуємо новий рядок ТІЛЬКИ якщо ціна змінилась.
        """
        # 1. Знаходимо поточний активний запис для цього магазину (де end_date ще порожній)
        active_history = self.db.query(PriceHistory).filter(
            PriceHistory.offer_id == offer_id,
            PriceHistory.end_date == None
        ).first()

        # 2. Якщо ціни не змінилися — нічого не робимо (економимо місце в базі!)
        if active_history and float(active_history.price) == float(new_price) and float(
                active_history.regular_price) == float(regular_price):
            return

        now_utc = datetime.now(timezone.utc)

        # 3. Якщо ціна змінилась (або якщо це найперша фіксація), закриваємо старий період ціни
        if active_history:
            active_history.end_date = now_utc

        # 4. Відкриваємо новий період ціни
        new_history = PriceHistory(
            id=str(uuid.uuid4()),
            offer_id=offer_id,
            price=new_price,
            regular_price=regular_price,
            start_date=now_utc,
            end_date=None
        )
        self.db.add(new_history)

    def find_offer_by_store_sku(self, store_sku: str):
        """
        Retrieves an existing offer based on its store-specific SKU.
        """
        return self.db.query(Offer).filter(Offer.store_sku == store_sku).first()

    def update_offer_price(self, offer_id: str, new_price: float, regular_price: float = None,
                           discount_condition: str = None):
        """
        Updates the prices and conditions of an existing offer AND records it in PriceHistory.
        """
        try:
            offer = self.db.query(Offer).filter(Offer.id == offer_id).first()
            if offer:
                reg_p = regular_price if regular_price is not None else new_price

                # Логіка мапінгу під твою структуру:
                # Якщо регулярна ціна більша за поточну — у нас є акція
                if reg_p > new_price:
                    offer.current_price = reg_p  # Ціна без знижки
                    offer.discount_price = new_price  # Ціна зі знижкою
                else:
                    offer.current_price = new_price
                    offer.discount_price = None  # Знижки немає

                # Записуємо умову акції (якщо передана з парсера)
                if hasattr(offer, 'discount_condition'):
                    offer.discount_condition = discount_condition

                if hasattr(offer, 'updatedAt'):
                    offer.updatedAt = datetime.now(timezone.utc)

                # Записуємо актуальні зміни в історію цін
                self._record_price_history(offer.id, offer.current_price, offer.discount_price or offer.current_price)

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
        """
        Creates and persists a new global product entry in the database.
        """
        try:
            new_id = str(uuid.uuid4())
            spec_attr = unified_item.get('specific_attributes', {})

            cat_id = self.get_or_create_category_tree(unified_item.get('category'))

            product = Product(
                id=new_id,
                productId=unified_item.get('product_id'),
                canonical_name=unified_item.get('canonical_name'),
                brand=unified_item.get('brand'),
                country=unified_item.get('country'),
                category_id=cat_id,
                raw_main_image=unified_item.get('raw_main_image'),
                main_image=unified_item.get('main_image'),
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
            self.db.rollback()
            raise e

    def get_or_create_category_tree(self, category_string: str) -> int | None:
        """
        Розбиває рядок категорії з парсера, створює дерево в БД.
        """
        if not category_string:
            return None

        categories = [cat.strip() for cat in category_string.split('>')]

        parent_id = None
        last_cat_id = None

        for cat_name in categories:
            existing_category = self.db.query(Category).filter_by(
                name=cat_name,
                parent_id=parent_id
            ).first()

            if existing_category:
                parent_id = existing_category.id
                last_cat_id = existing_category.id
            else:
                new_category = Category(name=cat_name, parent_id=parent_id)
                self.db.add(new_category)
                self.db.flush()

                parent_id = new_category.id
                last_cat_id = new_category.id

        return last_cat_id

    def create_offer(self, product_id: str, offer_data: dict, store_sku: str):
        """
        Creates a new store offer or updates an existing one with full discount support.
        """
        try:
            # 1. Дістаємо сирі ціни з уніфікованого словника парсера
            parsed_current = offer_data['pricing']['current_price']
            parsed_regular = offer_data['pricing']['regular_price']

            # 2. Автоматично витягуємо умову акції з гуртових знижок (bulk_discounts), якщо вони є
            discount_condition = None
            bulk_discounts = offer_data['pricing'].get('bulk_discounts', [])
            if bulk_discounts and isinstance(bulk_discounts, list):
                # Беремо опис першої гуртової умови (наприклад: "Ціна 44.9 грн при купівлі від 2 шт")
                discount_condition = bulk_discounts[0].get('description')

            # 3. Розподіляємо ціни під твою логіку:
            # Якщо регулярна ціна більша за поточну, regular — це база, а current — акція
            if parsed_regular > parsed_current:
                base_price = parsed_regular
                promo_price = parsed_current
            else:
                base_price = parsed_current
                promo_price = None

            existing_offer = self.db.query(Offer).filter(
                Offer.product_id == product_id,
                Offer.store_id == offer_data.get('store_id')
            ).first()

            if existing_offer:
                # 4. Оновлюємо існуючий оффер
                existing_offer.current_price = base_price
                existing_offer.discount_price = promo_price
                existing_offer.store_sku = store_sku

                if hasattr(existing_offer, 'discount_condition'):
                    existing_offer.discount_condition = discount_condition

                if hasattr(existing_offer, 'updatedAt'):
                    existing_offer.updatedAt = datetime.now(timezone.utc)

                offer_id = existing_offer.id
                print(f"   🔄 Оновлено пропозицію та умови акції (ID: {offer_id})")
            else:
                offer_id = str(uuid.uuid4())
                offer = Offer(
                    id=offer_id,
                    product_id=product_id,
                    store_sku=store_sku,
                    store_id=offer_data.get('store_id'),
                    current_price=base_price,
                    discount_price=promo_price
                )

                if hasattr(offer, 'discount_condition'):
                    offer.discount_condition = discount_condition

                if hasattr(offer, 'updatedAt'):
                    offer.updatedAt = datetime.now(timezone.utc)

                self.db.add(offer)

            # 6. Фіксуємо поточний стан ціни в розумну історію змін
            self._record_price_history(offer_id, base_price, promo_price or base_price)

            self.db.commit()
            return offer_id

        except Exception as e:
            self.db.rollback()
            raise e
    # ────────────────────────────────────────────────────────────────── #
    #  BATCH OPERATIONS (для паралельної обробки у DB Consumer)           #
    # ────────────────────────────────────────────────────────────────── #

    def find_offers_by_store_skus(self, store_skus: list):
        """
        Retrieves multiple offers by their store SKUs in a single query.

        Advantages:
        - O(1) query instead of O(n) individual lookups
        - Significantly faster for batch processing

        Args:
            store_skus (list): List of store-specific SKU strings.

        Returns:
            list[Offer]: Found offer objects.
        """
        if not store_skus:
            return []
        return self.db.query(Offer).filter(Offer.store_sku.in_(store_skus)).all()

    def update_offer_price_by_sku(self, store_sku: str, new_price: float):
        """
        Updates the price of an offer identified by its store SKU.

        Fast path for Fast Track processing: no ML inference needed, just
        update the current_price field and record history.

        Args:
            store_sku (str): Store-specific SKU.
            new_price (float): New price to set.
        """
        offer = self.db.query(Offer).filter(Offer.store_sku == store_sku).first()
        if offer:
            offer.current_price = new_price
            if hasattr(offer, 'updatedAt'):
                offer.updatedAt = datetime.now(timezone.utc)
            self._record_price_history(offer.id, new_price, new_price)