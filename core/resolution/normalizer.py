"""
Text normalization utilities for the product resolution pipeline.

This module provides functions to clean and standardize product names before
they are fed into the Machine Learning matcher. Proper normalization is crucial
to prevent false negatives caused by promotional noise, varying punctuation,
or inconsistent spacing in product titles.
"""

import re

# Слова-сміття, які заважають порівнювати товари
STOP_WORDS = {
    "акція", "знижка", "суперціна", "новинка", "упаковка",
    "грн", "шт", "г", "кг", "мл", "л", "за", "на", "з", "та", "і"
}
"""
set[str]: A collection of Ukrainian "noise" words that disrupt semantic matching.
It includes promotional terms (e.g., "акція", "суперціна"), units of measurement 
(e.g., "кг", "шт"), and common prepositions/conjunctions. A `set` is used here 
to ensure O(1) time complexity during word filtering.
"""


def clean_text(text: str) -> str:
    """
    Cleans and normalizes a product name for the ML-based resolution process.

    This function strips away irrelevant information that does not contribute to
    the actual semantic identity of the product, ensuring that the NLP model
    compares the core product names rather than promotional variations.

    Logic Flow:
    1. **Null Check:** Returns an empty string if the input is None or empty.
    2. **Case Normalization:** Converts the entire string to lowercase.
    3. **Punctuation Removal:** Uses the regex `[^\\w\\s]` to replace all special
       characters and punctuation marks with spaces.
    4. **Tokenization & Filtering:** Splits the text into individual words and
       removes any word present in the `STOP_WORDS` set.
    5. **Reconstruction:** Joins the surviving words with a single space to
       ensure consistent spacing.

    Args:
        text (str): The raw product name string (e.g., "Акція! Сир 'Голландський' 200г").

    Returns:
        str: The normalized product name containing only meaningful semantic keywords.

    Examples:
        >>> clean_text("Акція! Шоколад Milka з горіхами 100 г суперціна")
        'шоколад milka горіхами 100'
        >>> clean_text("Молоко, Яготинське 2.5%")
        'молоко яготинське 2 5'
        >>> clean_text(None)
        ''
    """
    if not text:
        return ""

    # Переводимо в нижній регістр
    text = text.lower()

    # Видаляємо всі спецсимволи та пунктуацію
    text = re.sub(r'[^\w\s]', ' ', text)

    # Розбиваємо на слова і фільтруємо стоп-слова
    words = text.split()
    filtered_words = [w for w in words if w not in STOP_WORDS]

    # Залишаємо лише одинарні пробіли
    return " ".join(filtered_words)