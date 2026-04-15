import os
import requests
import cloudinary
import cloudinary.uploader
import cloudinary.api
from cloudinary.exceptions import NotFound
from config import (
    STORAGE_DIR, FORA_HEADERS,
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
)

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

def download_and_save_image(raw_url, product_sku, suffix):
    if not raw_url:
        return None

    try:
        # Змінили папку на fora_products
        cloud_file_name = f"fora_products/{product_sku}_{suffix}"

        # 1. ПЕРЕВІРКА В CLOUDINARY
        try:
            existing_file = cloudinary.api.resource(cloud_file_name)
            print(f"    ✅ [СХОВИЩЕ] Фото {cloud_file_name} вже існує. Пропускаємо.")
            return existing_file.get("secure_url")
        except NotFound:
            pass

        # 2. ЯКЩО ФАЙЛУ НЕМАЄ, СКАЧУЄМО ЛОКАЛЬНО
        ext = raw_url.split('.')[-1]
        if len(ext) > 4 or '?' in ext:
            ext = "png" # Фора часто використовує png

        new_filename = f"{product_sku}_{suffix}.{ext}"
        local_filepath = os.path.join(STORAGE_DIR, new_filename)

        print(f"    ⬇️ [ЗАВАНТАЖЕННЯ] Качаємо нове фото: {new_filename}...")

        if not os.path.exists(local_filepath):
            response = requests.get(raw_url, headers=FORA_HEADERS, stream=True, timeout=10)
            response.raise_for_status()

            with open(local_filepath, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)

        # 3. ВІДПРАВЛЯЄМО В ХМАРУ
        print(f"    ☁️ [ХМАРА] Відправляю {new_filename} у Cloudinary...")
        upload_result = cloudinary.uploader.upload(
            local_filepath,
            public_id=cloud_file_name,
            overwrite=True
        )

        return upload_result.get("secure_url")

    except Exception as e:
        print(f"⚠️ Помилка обробки фото {raw_url}: {e}")
        return None