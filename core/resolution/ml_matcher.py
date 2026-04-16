from typing import List, Tuple, Optional, Any
from sentence_transformers import SentenceTransformer, util
import torch


class MLMatcher:
    """
    A machine learning-based semantic matching engine for product resolution.

    This class utilizes a pre-trained Natural Language Processing (NLP) model to
    understand the semantic meaning of product names. It is heavily used in the
    'Slow Track' pipeline to resolve new scraped items against existing database
    records when strict exact-match filters fail.

    **Design Pattern:** Implements the **Singleton** pattern. Loading a transformer
    model into memory is a computationally expensive and slow operation. By using a
    Singleton, the system ensures the model is loaded exactly once during the
    application's entire lifecycle.
    """

    _instance = None
    _model = None

    def __new__(cls) -> "MLMatcher":
        """
        Creates or returns the single global instance of the MLMatcher.

        During the first initialization, it downloads (if necessary) and loads
        the `paraphrase-multilingual-MiniLM-L12-v2` model into memory. This
        specific model is chosen for its excellent multilingual capabilities,
        including deep semantic understanding of the Ukrainian language.

        Returns:
            MLMatcher: The singleton instance of the class.
        """
        if cls._instance is None:
            cls._instance = super(MLMatcher, cls).__new__(cls)
            print("🧠 Завантаження NLP-моделі (це відбудеться лише один раз)...")
            # Мультимовна модель, яка чудово розуміє українську семантику
            cls._model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        return cls._instance

    def get_best_match(
            self,
            new_item_name: str,
            candidate_names: List[str],
            candidates: List[Any]
    ) -> Tuple[Optional[str], float]:
        """
        Calculates the semantic similarity between a new product name and a list
        of candidate names to find the closest match.

        Logic Flow:
        1. **Vectorization (Embedding):** Converts the `new_item_name` and all
           `candidate_names` into high-dimensional mathematical vectors (tensors)
           using the loaded NLP model.
        2. **Similarity Calculation:** Computes the Cosine Similarity between the
           new item's vector and the candidates' vectors. Cosine similarity
           measures the angle between two vectors, returning a score from -1.0
           to 1.0 (where 1.0 represents an exact semantic match).
        3. **Scoring:** Identifies the candidate with the highest similarity score.

        Args:
            new_item_name (str): The canonical name of the newly scraped product
                after normalization.
            candidate_names (List[str]): A list of normalized names from existing
                database products that passed initial hard filters (e.g., brand/weight).
            candidates (List[Any]): A list of the actual database models/objects
                corresponding to the `candidate_names`. These objects must have
                an `.id` attribute.

        Returns:
            Tuple[Optional[str], float]: A tuple containing:
                - `best_candidate.id` (str): The database ID of the best matching
                  candidate (or None if no candidates exist).
                - `best_score` (float): The similarity score of the best match,
                  typically falling between 0.0 and 1.0.
        """
        if not candidate_names:
            return None, 0.0

        # Перетворюємо текст на вектори (математичний сенс)
        new_item_embedding = self._model.encode(new_item_name, convert_to_tensor=True)
        candidates_embeddings = self._model.encode(candidate_names, convert_to_tensor=True)

        # Рахуємо відсоток схожості (Cosine Similarity)
        cosine_scores = util.cos_sim(new_item_embedding, candidates_embeddings)[0]

        # Знаходимо кандидата з найвищим балом
        best_score_idx = torch.argmax(cosine_scores).item()
        best_score = cosine_scores[best_score_idx].item()
        best_candidate = candidates[best_score_idx]

        return best_candidate.id, best_score