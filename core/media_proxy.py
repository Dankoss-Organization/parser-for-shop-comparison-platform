import os
import requests
import cloudinary
import cloudinary.uploader
import cloudinary.api
from cloudinary.exceptions import NotFound
from typing import Optional, Dict, Tuple, Any

from config import STORAGE_DIR, CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET


class CloudinaryImageProxy:
    """
    A proxy service for managing, downloading, and hosting product images.

    This class acts as an intermediary between the raw image URLs provided by
    the supermarket APIs and the platform's cloud storage (Cloudinary). It prevents
    image hotlinking, ensures high availability, and handles missing or broken URLs.

    **Design Pattern:** It implements a lazy Singleton-like initialization for the Cloudinary configuration.
    The API keys are configured only once upon the first instantiation of this class.
    """

    _initialized: bool = False

    def __init__(self) -> None:
        """
        Initializes the CloudinaryImageProxy.

        On the first call, it safely configures the global `cloudinary` library
        using credentials loaded from the environment parameters. Subsequent
        initializations bypass the configuration step.
        """
        if not CloudinaryImageProxy._initialized:
            cloudinary.config(
                cloud_name=CLOUDINARY_CLOUD_NAME,
                api_key=CLOUDINARY_API_KEY,
                api_secret=CLOUDINARY_API_SECRET,
                secure=True,
                max_connections = 16
            )
            CloudinaryImageProxy._initialized = True

        os.makedirs(STORAGE_DIR, exist_ok=True)

    def process_image(
            self,
            raw_url: str,
            product_sku: str,
            suffix: str,
            headers: Dict[str, str],
            folder_name: str = "products",
            fallback_replace: Optional[Tuple[str, str]] = None
    ) -> Optional[str]:
        """
        Processes a raw image URL through a three-step caching and upload pipeline.

        Logic Flow:
        1. **Cloud Check:** Queries Cloudinary to see if the image already exists
           under the expected public ID. If it does, returns the existing secure URL.
        2. **Local Download:** If missing, streams the image from the `raw_url`
           and saves it to the local `STORAGE_DIR`.
           *Fallback Logic:* If the initial request yields a 404 error and a
           `fallback_replace` rule is provided, it modifies the URL and retries
           (specifically useful for Silpo's changing image resolutions).
        3. **Cloud Upload:** Pushes the locally saved file to Cloudinary and
           returns the permanent, secure hosting URL.

        Args:
            raw_url (str): The original image URL scraped from the store.
            product_sku (str): The unique identifier of the product (e.g., "silpo_123").
            suffix (str): A string appended to the filename to distinguish between
                main images and gallery images (e.g., "main", "gallery_1").
            headers (Dict[str, str]): HTTP headers required to successfully download
                the image from the target store (bypassing basic bot protection).
            folder_name (str, optional): The target directory inside Cloudinary.
                Defaults to "products".
            fallback_replace (Optional[Tuple[str, str]], optional): A tuple containing
                `("old_string", "new_string")` to fix broken URLs dynamically on a 404.
                Defaults to None.

        Returns:
            Optional[str]: The secure Cloudinary URL (`https://res.cloudinary.com/...`)
            of the processed image, or `None` if `raw_url` is empty.

        Raises:
            Exception: If the image fails to download or upload after all attempts.
        """
        if not raw_url:
            return None

        try:
            cloud_file_name = f"{folder_name}/{product_sku}_{suffix}"

            # 1. CLOUDINARY CHECK
            try:
                existing_file = cloudinary.api.resource(cloud_file_name)
                print(f"    ✅ [СХОВИЩЕ] Фото {cloud_file_name} вже існує.")
                return existing_file.get("secure_url")
            except NotFound:
                pass

            # 2. DOWNLOAD
            ext = raw_url.split('.')[-1]
            if len(ext) > 4 or '?' in ext:
                ext = "jpg" if "silpo" in folder_name else "png"

            new_filename = f"{product_sku}_{suffix}.{ext}"
            local_filepath = os.path.join(STORAGE_DIR, new_filename)

            print(f"    ⬇️ [ЗАВАНТАЖЕННЯ] Качаємо: {new_filename}...")

            if not os.path.exists(local_filepath):
                response = requests.get(raw_url, headers=headers, stream=True, timeout=10)

                # Fallback logic (specifically for Silpo 404 errors)
                if response.status_code == 404 and fallback_replace:
                    old_str, new_str = fallback_replace
                    if old_str in raw_url:
                        fallback_url = raw_url.replace(old_str, new_str)
                        response = requests.get(fallback_url, headers=headers, stream=True, timeout=10)

                response.raise_for_status()

                with open(local_filepath, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)

            # 3. UPLOAD
            print(f"    ☁️ [ХМАРА] Відправляю {new_filename}...")
            upload_result = cloudinary.uploader.upload(local_filepath, public_id=cloud_file_name, overwrite=True)
            return upload_result.get("secure_url")

        except Exception as e:
            print(f"    ⚠️ [УВАГА] Збій при завантаженні фото ({raw_url}): {e}")
            return raw_url