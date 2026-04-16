from sentence_transformers import SentenceTransformer, util
import torch


class MLMatcher:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MLMatcher, cls).__new__(cls)
            print("🧠 Завантаження NLP-моделі (це відбудеться лише один раз)...")
            # Мультимовна модель, яка чудово розуміє українську семантику
            cls._model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        return cls._instance

    def get_best_match(self, new_item_name: str, candidate_names: list, candidates: list):
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