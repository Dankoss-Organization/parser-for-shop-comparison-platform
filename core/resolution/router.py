from typing import Dict, Any
from database.repository import Repository
from database.db_manager import SessionLocal
from .pipeline import SlowTrackPipeline


class EntityRouter:
    """
    The central traffic controller for routing scraped data into the database.

    This class acts as a Facade over the database repository and the complex
    product resolution pipeline. It determines the most efficient path for
    saving or updating a product based on its existing state in the system.

    **Architecture (Two-Track System):**
    - **Fast Track:** If a product's store-specific SKU is already known, the
      system bypasses all heavy processing and performs an O(1) database update
      just to refresh the current price.
    - **Slow Track:** If the SKU is unknown, the item is sent to the
      `SlowTrackPipeline` for deep ML-based semantic matching to decide if it
      is a completely new product or an alternative offer for an existing one.
    """

    def __init__(self) -> None:
        """
        Initializes the database session and core routing components.

        It establishes a localized SQLAlchemy session (`SessionLocal`), instantiates
        the data access layer (`Repository`), and sets up the heavy NLP pipeline
        (`SlowTrackPipeline`) for deep matching.
        """
        self.db = SessionLocal()
        self.repo = Repository(self.db)
        self.slow_track = SlowTrackPipeline(self.repo)

    def process_scraped_item(self, scraped_item: Dict[str, Any]) -> None:
        """
        Processes a single unified product dictionary and persists it to the database.

        Logic Flow:
        1. **Extraction:** Extracts the primary offer and its store-specific SKU.
        2. **Fast Track Execution:** Queries the database for an existing offer
           using the `store_sku`. If found, updates the price and exits immediately.
        3. **Slow Track Execution:** If the SKU is not found, passes the item to
           the ML matcher to find a global product ID.
        4. **Creation/Linking:** - If no match is found, creates a brand new global product entry.
           - If a match is found, links the new offer to the existing global product.
        5. **Offer Creation:** Finally, records the new offer under the resolved
           global product ID.

        Args:
            scraped_item (Dict[str, Any]): A standardized dictionary containing
                product details, metrics, and an 'offers' list. Typically generated
                by a store adapter (e.g., `SilpoAdapter`).

        Raises:
            KeyError: If the `scraped_item` is malformed and missing critical keys
                like 'offers', 'sku', or 'pricing'.
            SQLAlchemyError: If a database transaction fails during creation or update.
        """
        offer_data = scraped_item["offers"][0]
        store_sku = offer_data["sku"]
        current_price = offer_data["pricing"]["current_price"]

        # ⚡ FAST TRACK
        existing_offer = self.repo.find_offer_by_store_sku(store_sku)
        if existing_offer:
            print(f"⚡ Fast Track: Оновлюємо ціну ({current_price} грн) для SKU {store_sku}")
            self.repo.update_offer_price(existing_offer.id, current_price)
            return

        # 🐌 SLOW TRACK
        print(f"🐌 Slow Track: Аналіз товару '{scraped_item['canonical_name']}'")
        global_product_id = self.slow_track.find_match(scraped_item)

        if not global_product_id:
            print("   ✨ Створюємо новий глобальний товар у базі.")
            global_product_id = self.repo.create_product(scraped_item)
        else:
            print(f"   🔗 Прив'язуємо до існуючого товару: {global_product_id}")

        # Створюємо оффер
        self.repo.create_offer(global_product_id, offer_data, store_sku)

    def close(self) -> None:
        """
        Safely closes the active database session.

        It is critical to call this method at the end of the scraping cycle to
        release connection pool resources and prevent memory leaks.
        """
        self.db.close()