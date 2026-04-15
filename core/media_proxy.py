import os
import requests
import cloudinary
import cloudinary.uploader
import cloudinary.api
from cloudinary.exceptions import NotFound
from config import STORAGE_DIR, CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET


class CloudinaryImageProxy:
    _initialized = False

    def __init__(self):
        # Патерн Singleton для підключення
        if not CloudinaryImageProxy._initialized:
            cloudinary.config(
                cloud_name=CLOUDINARY_CLOUD_NAME,
                api_key=CLOUDINARY_API_KEY,
                api_secret=CLOUDINARY_API_SECRET,
                secure=True
            )
            CloudinaryImageProxy._initialized = True

    def process_image(self, raw_url, product_sku, suffix, headers, folder_name="products", fallback_replace=None):
        if not raw_url:
            return None

        try:
            cloud_file_name = f"{folder_name}/{product_sku}_{suffix}"

            # 1. ПЕРЕВІРКА В CLOUDINARY
            try:
                existing_file = cloudinary.api.resource(cloud_file_name)
                print(f"    ✅ [СХОВИЩЕ] Фото {cloud_file_name} вже існує.")
                return existing_file.get("secure_url")
            except NotFound:
                pass

            # 2. ЗАВАНТАЖЕННЯ
            ext = raw_url.split('.')[-1]
            if len(ext) > 4 or '?' in ext:
                ext = "jpg" if "silpo" in folder_name else "png"

            new_filename = f"{product_sku}_{suffix}.{ext}"
            local_filepath = os.path.join(STORAGE_DIR, new_filename)

            print(f"    ⬇️ [ЗАВАНТАЖЕННЯ] Качаємо: {new_filename}...")

            if not os.path.exists(local_filepath):
                response = requests.get(raw_url, headers=headers, stream=True, timeout=10)

                # Логіка Fallback для Сільпо (перенесена без змін)
                if response.status_code == 404 and fallback_replace:
                    old_str, new_str = fallback_replace
                    if old_str in raw_url:
                        fallback_url = raw_url.replace(old_str, new_str)
                        response = requests.get(fallback_url, headers=headers, stream=True, timeout=10)

                response.raise_for_status()

                with open(local_filepath, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)

            # 3. ВІДПРАВКА
            print(f"    ☁️ [ХМАРА] Відправляю {new_filename}...")
            upload_result = cloudinary.uploader.upload(local_filepath, public_id=cloud_file_name, overwrite=True)
            return upload_result.get("secure_url")

        except Exception as e:
            raise Exception(f"Збій при завантаженні фото ({raw_url}): {e}")