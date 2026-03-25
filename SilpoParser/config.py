import os

# --- CLOUDINARY НАЛАШТУВАННЯ ---
CLOUDINARY_CLOUD_NAME = "dujpbhvfx"
CLOUDINARY_API_KEY = "927126933888236"
CLOUDINARY_API_SECRET = "nnnwchU9c238Cw1NEm2N9LVg_wY"
# Налаштування директорій
STORAGE_DIR = "storage/images"
os.makedirs(STORAGE_DIR, exist_ok=True)

# Базові URL
OUR_BASE_IMAGE_URL = "https://your-promo-app.com/media/"
SILPO_BASE_IMG_URL = "https://images.silpo.ua/v2/products/1000x1000/webp/"

# Заголовки для парсингу
HEADERS = {
    'accept': 'application/json',
    'origin': 'https://silpo.ua',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
}