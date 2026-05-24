"""
SQLAlchemy ORM models for the Shop Comparison Platform.

This module defines the database schema using declarative mapping. It represents
the core relationships between global products, store-specific offers, and
historical pricing data stored in a PostgreSQL database.
"""

from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, timezone
import uuid

Base = declarative_base()

class Category(Base):
    __tablename__ = 'pr_categories'  # Твоя таблиця

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    parent_id = Column(String, ForeignKey('pr_categories.id'), nullable=True)

    # Relationship для отримання підкатегорій (опціонально, але корисно)
    subcategories = relationship("Category")
    products = relationship("Product", back_populates="category", foreign_keys="[Product.category_id]")


class Product(Base):
    """
    Represents a unified, global product in the comparison platform.

    This is the core entity that aggregates identical items found across different
    supermarkets. It stores canonical information (name, brand, country) and
    flexible data structures (JSONB) for varying product attributes.

    Attributes:
        id (String): The primary key (UUID) generated internally.
        productId (String): The original or composite identifier for the product.
        canonical_name (String): The normalized, human-readable name of the product.
        brand (String): The brand name (indexed for faster searching and filtering).
        country (String): The country of origin.
        media (JSONB): A flexible dictionary storing raw and processed image URLs.
        measurements (JSONB): Stores parsed weight/volume data (e.g., {'value': 100, 'unit': 'g'}).
        pricing_logic (JSONB): Information on how the item is sold (e.g., per piece or weighted).
        calories (String): Stored as a String because some stores provide ranges or
            dual values (e.g., "532/2225" kcal/kJ).
        offers (relationship): A one-to-many relationship linking this global
            product to its various store-specific offers.
    """
    __tablename__ = 'product'

    id = Column(String, primary_key=True)
    productId = Column(String)
    canonical_name = Column(String)
    brand = Column(String, index=True)
    country = Column(String)
    category_id = Column(String, ForeignKey('pr_categories.id'), nullable=True)
    category = relationship("Category", back_populates="products")

    # JSON fields for flexible schemaless data
    media = Column(JSONB)
    measurements = Column(JSONB)
    pricing_logic = Column(JSONB)

    description = Column(String)

    # Nutrition facts stored as Strings to accommodate non-standard API formats
    calories = Column(String)
    proteins_g = Column(String)
    fats_g = Column(String)
    carbohydrates_g = Column(String)
    alcohol_percentage = Column(String)

    # Boolean flags for UI filtering and legal compliance
    is_tobacco = Column(Boolean, default=False)
    is_18_plus = Column(Boolean, default=False)
    is_national_cashback_eligible = Column(Boolean, default=False)

    # Timestamps
    createdAt = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updatedAt = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    offers = relationship("Offer", back_populates="product")


class Offer(Base):
    """
    Represents a store-specific offer for a global product.

    While `Product` holds the static canonical details, the `Offer` table tracks
    the dynamic, store-dependent details such as the current price, availability,
    and the specific SKU used by that supermarket (e.g., "silpo_12345").

    Attributes:
        id (String): The primary key (UUID) for this specific offer.
        store_id (String): The identifier of the supermarket (e.g., 's_silpo', 'f_fora').
        product_id (String): A foreign key linking to the `Product` table.
        store_sku (String): The exact item ID used by the store's internal system (indexed).
        current_price (Float): The absolute current selling price in UAH.
    """
    __tablename__ = 'offers'

    id = Column(String, primary_key=True)
    store_id = Column(String)
    product_id = Column(String, ForeignKey('product.id'))

    store_sku = Column(String, index=True, nullable=True)

    current_price = Column(Float)  # Price is strictly numerical for calculations

    createdAt = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updatedAt = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                       onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    product = relationship("Product", back_populates="offers")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    offer_id = Column(String, ForeignKey("offers.id"), nullable=False)

    price = Column(Float, nullable=False)
    regular_price = Column(Float, nullable=False)

    # Інтервали дії ціни
    start_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    end_date = Column(DateTime, nullable=True)  # Поки ціна актуальна, це поле пусте

    offer = relationship("Offer", backref="price_history")