import os
from dotenv import load_dotenv

load_dotenv()

# --- CLOUDINARY НАЛАШТУВАННЯ ---
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# Налаштування директорій
STORAGE_DIR = "storage/images"
os.makedirs(STORAGE_DIR, exist_ok=True)

# Базові константи
SILPO_BASE_IMG_URL = "https://images.silpo.ua/v2/products/1000x1000/webp/"

# Заголовки для парсингу
SILPO_HEADERS = {
    'accept': 'application/json',
    'origin': 'https://silpo.ua',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145.0.0.0 Safari/537.36',
}

FORA_HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json',
    'origin': 'https://fora.ua',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145.0.0.0 Safari/537.36',
}