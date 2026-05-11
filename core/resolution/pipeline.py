from typing import Optional, Any
from .normalizer import clean_text
from .ml_matcher import MLMatcher


class SlowTrackPipeline:
    """
    A sophisticated resolution pipeline for identifying products using multi-stage filtering.

    The 'Slow Track' is triggered when a product is not immediately identified by its
    store-specific SKU (Fast Track). It employs a layered approach—starting from
    exact identifiers (barcodes) to strict attribute filters (brand and weight),
    and finally to advanced semantic NLP matching.

    Attributes:
        repo (Any): The data repository instance used for database lookups.
        ml_matcher (MLMatcher): A singleton NLP engine used for semantic similarity analysis.
    """

    def __init__(self, repo: Any) -> None:
        """
        Initializes the pipeline with a repository and the ML matching engine.

        Args:
            repo (Any): An instance of the Repository class to interact with the database.
        """
        self.repo = repo
        self.ml_matcher = MLMatcher()

    def find_match(self, item: dict) -> Optional[str]:
        """
        Attempts to find a matching global product in the database for a scraped item.

        Logic Flow:
        1. **Barcode Check (The Holy Grail):** Attempts to match the item using a
           unique barcode. This is the most reliable identification method and
           results in an immediate match if found in the database.
        2. **Hard Attribute Filtering:** Extracts the 'brand' and 'weight/volume'
           value. If either is missing, the system aborts matching to prevent
           incorrect merges (safety first policy).
        3. **Candidate Selection:** Queries the database for all existing products
           sharing the exact same brand and numerical measurement value.
        4. **Text Normalization:** Cleans the canonical name of the new item and
           all identified    candidates to remove promotional noise and stop-words.
        5. **Semantic ML Analysis:** Compares the cleaned names using deep
           learning embeddings. If the similarity score (Cosine Similarity) meets
           or exceeds the threshold (0.96), a match is confirmed.

        Args:
            item (dict): The standardized product dictionary produced by an adapter.

        Returns:
            Optional[str]: The internal UUID of the matching global product,
            or `None` if no reliable match could be determined.
        """
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

        if score >= 0.96:
            return best_match_id

        return None