import os
from dotenv import load_dotenv

# Змушуємо Python прочитати файл .env і завантажити змінні в пам'ять
load_dotenv()

# --- CLOUDINARY НАЛАШТУВАННЯ ---
# Тепер ми не пишемо ключі руками, а дістаємо їх із середовища
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# Налаштування директорій
STORAGE_DIR = "storage/images"
os.makedirs(STORAGE_DIR, exist_ok=True)

# Базові URL
SILPO_BASE_IMG_URL = "https://images.silpo.ua/v2/products/1000x1000/webp/"

# Заголовки для парсингу
HEADERS = {
    'accept': 'application/json',
    'origin': 'https://silpo.ua',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
}