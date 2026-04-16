from database.repository import Repository
from database.db_manager import SessionLocal
from .pipeline import SlowTrackPipeline


class EntityRouter:
    def __init__(self):
        self.db = SessionLocal()
        self.repo = Repository(self.db)
        self.slow_track = SlowTrackPipeline(self.repo)

    def process_scraped_item(self, scraped_item: dict):
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

    def close(self):
        self.db.close()