import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from database.models import Product, PriceHistory

load_dotenv()


class DatabaseManager:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("❌ Не знайдено DATABASE_URL у файлі .env!")

        # Налаштовуємо підключення
        self.engine = create_engine(self.db_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def upsert_product(self, product_data: dict):
        """Додає новий товар або оновлює існуючий (Upsert)"""
        session = self.SessionLocal()
        try:
            product_id = product_data.get("product_id")
            # Шукаємо, чи є вже такий товар
            product = session.query(Product).filter(Product.product_id == product_id).first()

            main_offer = product_data['offers'][0]
            current_price = main_offer['pricing']['current_price']
            regular_price = main_offer['pricing']['regular_price']
            scraped_at = main_offer['scraped_at']

            if not product:
                # Створюємо новий товар
                product = Product(
                    product_id=product_id,
                    canonical_name=product_data.get("canonical_name"),
                    brand=product_data.get("brand"),
                    category=product_data.get("category"),
                    country=product_data.get("country"),
                    main_image=product_data.get("media", {}).get("main_image"),
                    current_price=current_price,
                    regular_price=regular_price,
                    last_updated=scraped_at
                )
                session.add(product)
            else:
                # Оновлюємо існуючий
                product.current_price = current_price
                product.regular_price = regular_price
                product.last_updated = scraped_at

            # Додаємо запис в історію цін
            history_entry = PriceHistory(
                product_id=product_id,
                price=current_price,
                scraped_at=scraped_at
            )
            session.add(history_entry)

            session.commit()
            return product
        except Exception as e:
            session.rollback()
            print(f"❌ Помилка при збереженні товару {product_id}: {e}")
            raise e
        finally:
            session.close()

    def get_all_products(self):
        """Повертає всі товари з бази"""
        session = self.SessionLocal()
        try:
            return session.query(Product).all()
        finally:
            session.close()