import requests
from config import SILPO_HEADERS


class SilpoApiClient:

    @staticmethod
    def fetch_all_slugs(branch_id="1edee42f-ece6-6e12-8d91-d3a7e392bfd1", max_pages=2):
        """
        Збирає slug-и товарів через правильні GET-запити.
        """
        url = f'https://sf-ecom-api.silpo.ua/v1/uk/branches/{branch_id}/products'
        headers = SILPO_HEADERS.copy()

        all_slugs = []
        limit = 50

        print("🔍 [СІЛЬПО] Починаємо збір загального списку товарів (Discovery Phase)...")

        for page in range(1, max_pages + 1):
            # 🔥 Точна копія параметрів з вашого перехопленого запиту
            params = {
                "limit": limit,
                "offset": (page - 1) * limit,
                "deliveryType": "DeliveryHome",
                "category": "frukty-ovochi-4788",
                "includeChildCategories": "true",
                "inStock": "true"
            }

            try:
                response = requests.get(url, headers=headers, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                items = data.get('items', [])
                if not items:
                    print(f"   ℹ️ Товари закінчилися на сторінці {page}.")
                    break

                for item in items:
                    if 'slug' in item:
                        all_slugs.append(item['slug'])

                print(f"   📥 Зібрано {len(all_slugs)} товарів (Сторінка {page})...")

            except requests.exceptions.RequestException as e:
                print(f"⚠️ Помилка при зборі списку (сторінка {page}): {e}")
                break

        return list(set(all_slugs))

    @staticmethod
    def fetch_detailed_product(slug, branch_id="1edee42f-ece6-6e12-8d91-d3a7e392bfd1"):
        # Тут ми теж використаємо реальний branch_id, щоб не було конфліктів
        url = f'https://sf-ecom-api.silpo.ua/v1/uk/branches/{branch_id}/products/{slug}'
        headers = SILPO_HEADERS.copy()
        headers['referer'] = f'https://silpo.ua/product/{slug}'

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Відмова API Сільпо: {e}")