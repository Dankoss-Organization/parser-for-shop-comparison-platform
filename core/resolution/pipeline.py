from .normalizer import clean_text
from .ml_matcher import MLMatcher


class SlowTrackPipeline:
    def __init__(self, repo):
        self.repo = repo
        self.ml_matcher = MLMatcher()

    def find_match(self, item: dict):
        # Етап 1: Штрихкод (Святий Грааль)
        barcode = item.get("specific_attributes", {}).get("barcode")
        if barcode:
            match = self.repo.find_product_by_barcode(barcode)
            if match:
                print(f"   🎯 Знайдено за штрихкодом: {barcode}")
                return match.id

        # Етап 2: Жорсткі фільтри (Бренд + Вага)
        brand = item.get("brand")
        weight_val = item.get("measurements", {}).get("value")

        # Якщо немає бренду або ваги, безпечніше створити новий товар, ніж випадково злити два різних
        if not brand or not weight_val:
            return None

        candidates = self.repo.find_products_by_brand_and_weight(brand, weight_val)
        if not candidates:
            return None  # Жодного кандидата в БД, це 100% новий товар

        # Етап 3: Нормалізація
        new_item_clean = clean_text(item["canonical_name"])
        candidate_names_clean = [clean_text(c.canonical_name) for c in candidates]

        # Етап 4: ML Embeddings
        best_match_id, score = self.ml_matcher.get_best_match(
            new_item_clean,
            candidate_names_clean,
            candidates
        )

        print(f"   🤖 ML Аналіз: '{new_item_clean}' -> Збіг {score * 100:.1f}%")

        if score >= 0.85:  # Наш жорсткий поріг (85%)
            return best_match_id

        return None