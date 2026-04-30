import uuid
from sqlalchemy.orm import Session
from sqlalchemy import cast, Float
from .models import Product, Offer


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

    def find_offer_by_store_sku(self, store_sku: str):
        """
        Retrieves an existing offer based on its store-specific SKU.

        Used primarily in the 'Fast Track' resolution process to quickly find
        if an item from a specific store is already being tracked.

        Args:
            store_sku (str): The exact unique identifier used by the store
                (e.g., "silpo_886097").

        Returns:
            Offer | None: The matched Offer model instance, or None if not found.
        """
        return self.db.query(Offer).filter(Offer.store_sku == store_sku).first()

    def update_offer_price(self, offer_id: str, new_price: float):
        """
        Updates the current price of an existing offer.

        Args:
            offer_id (str): The internal UUID primary key of the offer to update.
            new_price (float): The newly scraped current price in UAH.

        Returns:
            Offer | None: The updated Offer instance, or None if the offer
            with the provided ID does not exist.

        Raises:
            Exception: Re-raises any database errors after rolling back the transaction.
        """
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
        """
        Searches for a global product using a standardized barcode (EAN/UPC).

        Note:
            This method is currently a stub for future implementation. Barcodes
            represent the highest confidence match in the Slow Track pipeline.

        Args:
            barcode (str): The product barcode string.

        Returns:
            None: Currently returns None as the functionality is not yet implemented.
        """
        return None

    def find_products_by_brand_and_weight(self, brand: str, weight_value: float):
        """
        Finds potential global product matches using strict brand and weight filters.

        This acts as the preliminary filter in the 'Slow Track' pipeline before
        handing candidates over to the expensive NLP Machine Learning matcher.

        Logic Flow:
        1. Queries all products matching the exact brand string.
        2. Iterates through the results to safely extract and compare the nested
           JSONB `measurements` value against the target `weight_value`.

        Args:
            brand (str): The exact brand name of the product.
            weight_value (float): The numeric value of the product's weight or volume.

        Returns:
            list[Product]: A list of candidate Product objects that match both criteria.
        """
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

        This method extracts canonical data, media arrays, and deeply nested
        specific attributes from the normalized dictionary and maps them to
        the SQLAlchemy `Product` model.

        Args:
            unified_item (dict): The standardized dictionary produced by a
                scraper's adapter.

        Returns:
            str: The newly generated UUID primary key of the created product.

        Raises:
            Exception: Rolls back the transaction and re-raises any DB errors.
        """
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
        """
        Creates a new store offer or updates an existing one for a global product.

        This method follows an "Upsert" logic pattern:
        - It checks if the specific store already has an offer for the given `product_id`.
        - If yes, it updates the `current_price` and `store_sku`.
        - If no, it creates a brand new `Offer` record linked to the product.

        Args:
            product_id (str): The UUID of the global parent Product.
            offer_data (dict): The dictionary containing pricing and store info.
            store_sku (str): The exact item identifier from the store's backend.

        Returns:
            str: The UUID of the created or updated Offer.

        Raises:
            Exception: Rolls back the transaction and re-raises any DB errors.
        """
        try:
            # Спочатку перевіряємо, чи вже є оффер для цього товару в цьому магазині
            existing_offer = self.db.query(Offer).filter(
                Offer.product_id == product_id,
                Offer.store_id == offer_data.get('store_id')
            ).first()

            if existing_offer:
                # Якщо оффер є, просто оновлюємо ціну та SKU
                existing_offer.current_price = offer_data['pricing']['current_price']
                existing_offer.store_sku = store_sku
                self.db.commit()
                print(f"   🔄 Оновлено існуючу пропозицію в магазині (ID: {existing_offer.id})")
                return existing_offer.id

            # Якщо офферу немає, створюємо новий
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
            self.db.rollback()
            raise e