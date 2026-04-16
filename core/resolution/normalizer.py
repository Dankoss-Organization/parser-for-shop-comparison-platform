import re

# Слова-сміття, які заважають порівнювати товари
STOP_WORDS = {"акція", "знижка", "суперціна", "новинка", "упаковка", "грн", "шт", "г", "кг", "мл", "л"}


def clean_text(text: str) -> str:
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