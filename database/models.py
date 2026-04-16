from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone

Base = declarative_base()


class Product(Base):
    __tablename__ = 'product'

    id = Column(String, primary_key=True)
    productId = Column(String)
    canonical_name = Column(String)
    brand = Column(String, index=True)
    country = Column(String)

    # JSON поля
    media = Column(JSONB)
    measurements = Column(JSONB)
    pricing_logic = Column(JSONB)

    description = Column(String)

    # 🔥 БУЛО Float, СТАЛО String (бо Postgres зберігає тут текст)
    calories = Column(String)
    proteins_g = Column(String)
    fats_g = Column(String)
    carbohydrates_g = Column(String)
    alcohol_percentage = Column(String)

    # Булеві поля
    is_tobacco = Column(Boolean, default=False)
    is_18_plus = Column(Boolean, default=False)
    is_national_cashback_eligible = Column(Boolean, default=False)

    # Дати
    createdAt = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updatedAt = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))

    category_id = Column(String)

    # Зв'язок
    offers = relationship("Offer", back_populates="product")


class Offer(Base):
    __tablename__ = 'offers'

    id = Column(String, primary_key=True)
    store_id = Column(String)
    product_id = Column(String, ForeignKey('product.id'))

    store_sku = Column(String, index=True, nullable=True)

    current_price = Column(Float)  # А ось ціна дійсно завжди число

    createdAt = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updatedAt = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))

    # Зв'язок
    product = relationship("Product", back_populates="offers")