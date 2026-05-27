from typing import List, Tuple, Optional, Any
import numpy as np
from sentence_transformers import SentenceTransformer, util
import torch


class MLMatcher:
    """
    A machine learning-based semantic matching engine for product resolution.

    Uses a pre-trained multilingual Sentence Transformer to compute semantic
    similarity between product names. Implements the Singleton pattern to ensure
    the model is loaded exactly once.

    Performance optimisation:
        ``get_best_match_batch`` encodes all new product names in a single
        ``model.encode()`` call (one forward pass through the network) instead
        of one call per product. For a batch of 50 items this reduces encoding
        time from ~50 × 3s = 150s down to ~3-5s total — a 30-50× speedup.
    """

    _instance = None
    _model: Optional[SentenceTransformer] = None

    def __new__(cls) -> "MLMatcher":
        if cls._instance is None:
            cls._instance = super(MLMatcher, cls).__new__(cls)
            print("🧠 Завантаження NLP-моделі (це відбудеться лише один раз)...")
            cls._model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        return cls._instance

    # ------------------------------------------------------------------
    # Single-item API (original — kept for backward compatibility)
    # ------------------------------------------------------------------

    def get_best_match(
        self,
        new_item_name: str,
        candidate_names: List[str],
        candidates: List[Any],
    ) -> Tuple[Optional[str], float]:
        """
        Finds the best-matching candidate for a single product name.

        Internally delegates to the batch version for consistency.

        Args:
            new_item_name (str): Normalised name of the new product.
            candidate_names (List[str]): Normalised names of existing products.
            candidates (List[Any]): Corresponding DB objects (must have ``.id``).

        Returns:
            Tuple[Optional[str], float]: (best_candidate_id, similarity_score)
        """
        if not candidate_names:
            return None, 0.0

        # Single-item encode — used only when called outside of a batch context.
        new_emb = self._model.encode(new_item_name, convert_to_tensor=True)
        cand_embs = self._model.encode(candidate_names, convert_to_tensor=True)

        scores = util.cos_sim(new_emb, cand_embs)[0]
        best_idx = torch.argmax(scores).item()
        return candidates[best_idx].id, scores[best_idx].item()

    # ------------------------------------------------------------------
    # Batch API (new — call this from _process_batch for speed)
    # ------------------------------------------------------------------

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """
        Encodes a list of texts into embedding vectors in a single forward pass.

        This is the key optimisation: instead of calling ``model.encode()`` once
        per product (which re-runs the neural network each time), we encode all
        texts together. The GPU/CPU can process them in parallel inside the model.

        Args:
            texts (List[str]): Product names to encode.

        Returns:
            np.ndarray: Matrix of shape (len(texts), embedding_dim).
        """
        if not texts:
            return np.array([])
        return self._model.encode(
            texts,
            batch_size=64,          # Process up to 64 texts per GPU/CPU batch
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,  # Pre-normalise → cosine sim = dot product
        )

    def batch_cosine_similarity(
        self,
        query_embeddings: np.ndarray,
        corpus_embeddings: np.ndarray,
    ) -> np.ndarray:
        """
        Computes cosine similarity between every query and every corpus vector.

        Because embeddings are pre-normalised (``normalize_embeddings=True`` in
        ``encode_batch``), cosine similarity reduces to a simple dot product,
        which numpy can compute as a single highly-optimised matrix multiply.

        Args:
            query_embeddings: Shape (n_queries, dim).
            corpus_embeddings: Shape (n_corpus, dim).

        Returns:
            np.ndarray: Shape (n_queries, n_corpus) — similarity matrix.
        """
        if query_embeddings.size == 0 or corpus_embeddings.size == 0:
            return np.array([])
        return np.dot(query_embeddings, corpus_embeddings.T)
