"""
VarusApiClient — HTTP client for the Varus product catalog API.

The Varus website is powered by Vue Storefront with an Elasticsearch backend
exposed at /api/catalog/.../product_v2/_search. Products are organised into a
category tree; the most efficient discovery strategy is to query each category
separately and paginate with from/size offsets.

Previous approach (ID-pagination over the whole catalogue) had two problems:
1. It fetched every product regardless of category relevance.
2. It relied on a local file cache that went stale silently.

Current approach:
1. Iterate over CATEGORY_IDS (curated list of food/grocery categories).
2. For each category, paginate until the page is empty.
3. Collect product IDs and return them as the slug list.
"""

import json
import logging
import requests
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class VarusApiClient:
    """
    Stateless HTTP client for the Varus catalog search API.

    All methods are static — the class acts as a namespace for related
    functions rather than holding per-instance state.

    Attributes:
        SHOP_ID (str): Varus region/shop identifier used in every request.
            Confirmed from browser network traffic: shop_id=57.
        BASE_URL (str): Elasticsearch search proxy endpoint.
        PAGE_SIZE (int): Products per page. 40 matches the browser's default;
            can be raised to 100 without triggering rate limits.
        CATEGORY_IDS (List[int]): Curated list of grocery category IDs.
            Add or remove IDs here to control which sections are scraped.
            To find new category IDs: open Varus in DevTools → Network →
            filter by "_search" → look at the category_ids filter in the request.
    """

    SHOP_ID = "57"
    BASE_URL = "https://varus.ua/api/catalog/vue_storefront_catalog_2/product_v2/_search"
    PAGE_SIZE = 100  # Safe upper limit; Elasticsearch default max is 10 000

    # ------------------------------------------------------------------ #
    #  CATEGORY IDS                                                        #
    #  Grouped by section for readability. Add new IDs as needed.         #
    # ------------------------------------------------------------------ #
    CATEGORY_IDS: List[int] = [
        # Фрукти, овочі, горіхи
        53253,
        # М'ясо та напівфабрикати
        53028,
        # Риба та морепродукти
        53051,
        # Алкоголь
        53297,
        # Ковбаси, сосиски, делікатеси
        53029,
        # Сири
        53048,
        # Молочні продукти та яйця
        53036,
        # Бакалія
        52876,
        # Хлібобулочні вироби
        53273,
        # Кондитерські вироби та солодощі
        52971,
        #Чай, кава, гарячі напої
        52905,
        #Вода, соки, напої
        52956,
        #Снеки
        52922,
        #Заморожені продукти
        52962,
        #Консервація та соління
        58295,
        #Тютюнові вироби
        53249
    ]

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:151.0) "
            "Gecko/20100101 Firefox/151.0"
        ),
        "Accept": "application/json",
        "Accept-Language": "uk-UA,uk;q=0.9",
        "Referer": "https://varus.ua/",
        "Content-Type": "application/json",
    }

    # Fields we need for discovery (minimal set → faster response)
    _DISCOVERY_FIELDS = "id,sku"

    # Fields we need for full product detail
    _DETAIL_FIELDS = (
        "sku,id,name,sqpp_data_region_default,weight,volume,"
        "is_18_plus,is_tobacco,brand_data,description,"
        "category,countrymanufacturerforsite,image"
    )

    # ------------------------------------------------------------------ #
    #  Discovery                                                           #
    # ------------------------------------------------------------------ #

    @classmethod
    def fetch_all_slugs(cls) -> List[str]:
        """
        Collects product IDs from all configured categories.

        For each category in ``CATEGORY_IDS``, paginates through products
        in batches of ``PAGE_SIZE`` until an empty page is returned.

        Returns:
            List[str]: Deduplicated product IDs ready to be passed to
                ``fetch_detailed_product``.

        Note:
            Uses a set internally to deduplicate products that appear in
            multiple categories (e.g. a product in both "Молоко" and
            "Молочні продукти").
        """
        all_ids: set[str] = set()

        for category_id in cls.CATEGORY_IDS:
            logger.info("[Varus] Збираємо категорію %d...", category_id)
            ids_in_category = cls._fetch_category_slugs(category_id)
            new = len(ids_in_category - all_ids)
            all_ids.update(ids_in_category)
            logger.info(
                "[Varus] Категорія %d: %d товарів (%d нових). Всього: %d",
                category_id, len(ids_in_category), new, len(all_ids),
            )

        return list(all_ids)

    @classmethod
    def _fetch_category_slugs(cls, category_id: int) -> set:
        """
        Paginates through a single category and returns all product IDs.

        Uses ``from`` + ``size`` offset pagination. Stops when the returned
        page is shorter than ``PAGE_SIZE`` (last page reached).

        Args:
            category_id (int): Elasticsearch category identifier.

        Returns:
            set[str]: Product IDs found in this category.
        """
        ids: set[str] = set()
        offset = 0

        while True:
            payload = cls._build_category_payload(category_id)
            params = {
                "_source_include": cls._DISCOVERY_FIELDS,
                "from": offset,
                "size": cls.PAGE_SIZE,
                "shop_id": cls.SHOP_ID,
                "request": json.dumps(payload),
                "request_format": "search-query",
                "response_format": "compact",
                "sort": "",
            }

            try:
                items = cls._get_items(params)
            except Exception as exc:
                logger.warning(
                    "[Varus] Помилка для категорії %d (offset=%d): %s",
                    category_id, offset, exc,
                )
                break

            if not items:
                break  # Empty page → we've exhausted this category

            for item in items:
                source = item.get("_source", item) if isinstance(item, dict) else {}
                pid = source.get("id") or source.get("sku")
                if pid:
                    ids.add(str(pid))

            print(
                f"   [Varus] Категорія {category_id} | "
                f"offset={offset} | сторінка={len(items)} | всього в категорії={len(ids)}"
            )

            if len(items) < cls.PAGE_SIZE:
                break  # Last (partial) page

            offset += cls.PAGE_SIZE

        return ids

    @staticmethod
    def _build_category_payload(category_id: int) -> dict:
        """
        Builds the Elasticsearch query payload for a single category.

        Filters:
        - ``visibility`` in [2, 4] (catalog + catalog+search)
        - ``status`` in [0, 1] (enabled products)
        - ``category_ids`` in [category_id]
        - ``sqpp_data_region_default.in_stock`` = true (in-stock only)

        Args:
            category_id (int): Category to filter by.

        Returns:
            dict: JSON-serialisable payload for the ``request`` query parameter.
        """
        return {
            "_availableFilters": [],
            "_appliedFilters": [
                {"attribute": "visibility", "value": {"in": [2, 4]}, "scope": "default"},
                {"attribute": "status", "value": {"in": [0, 1]}, "scope": "default"},
                {"attribute": "category_ids", "value": {"in": [category_id]}, "scope": "default"},
                {"attribute": "sqpp_data_region_default.in_stock", "value": {"or": True}, "scope": "default"},
            ],
            "_appliedSort": [{"field": "id", "options": {"order": "asc"}}],
            "_searchText": "",
        }

    # ------------------------------------------------------------------ #
    #  Detail fetch                                                        #
    # ------------------------------------------------------------------ #

    @classmethod
    def fetch_detailed_product(cls, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches full product data for a single product ID.

        Args:
            product_id (str): Numeric product ID as a string (from ``fetch_all_slugs``).

        Returns:
            dict | None: Product source dict, or None if not found / request failed.
        """
        payload = {
            "_availableFilters": [],
            "_appliedFilters": [
                {"attribute": "id", "value": {"in": [product_id]}, "scope": "default"}
            ],
            "_searchText": "",
        }
        params = {
            "_source_include": cls._DETAIL_FIELDS,
            "from": 0,
            "size": 1,
            "shop_id": cls.SHOP_ID,
            "request": json.dumps(payload),
            "request_format": "search-query",
            "response_format": "compact",
        }

        try:
            items = cls._get_items(params)
            if items and isinstance(items[0], dict):
                return items[0].get("_source", items[0])
        except Exception as exc:
            logger.warning("[Varus] Помилка деталей для %s: %s", product_id, exc)

        return None

    # ------------------------------------------------------------------ #
    #  Shared HTTP helper                                                  #
    # ------------------------------------------------------------------ #

    @classmethod
    def _get_items(cls, params: dict) -> list:
        """
        Executes a GET request and extracts the hits array from the response.

        Handles both list responses (compact mode) and nested
        ``{"hits": {"hits": [...]}}`` Elasticsearch responses.

        Args:
            params (dict): Query parameters for the search endpoint.

        Returns:
            list: Raw item list (may be empty).

        Raises:
            requests.HTTPError: If the server returns a non-2xx status.
            ValueError: If the response body cannot be parsed as JSON.
        """
        resp = requests.get(
            cls.BASE_URL,
            params=params,
            headers=cls.HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            hits_outer = data.get("hits", [])
            if isinstance(hits_outer, list):
                return hits_outer
            if isinstance(hits_outer, dict):
                return hits_outer.get("hits", [])

        return []