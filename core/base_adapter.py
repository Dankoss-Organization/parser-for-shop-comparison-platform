import re

class BaseAdapter:
    @staticmethod
    def parse_measurements(ratio_str):
        # Загальна логіка розбору ваги, яка була однаковою у двох файлах
        if not ratio_str:
            return {"value": 1.0, "unit": "pcs"}

        match = re.match(r"([\d\.,]+)\s*([а-яa-zA-Z]+)", str(ratio_str).lower().strip().replace(',', '.'))
        if match:
            val = float(match.group(1))
            unit = match.group(2)
            unit_map = {"г": "g", "g": "g", "кг": "kg", "kg": "kg", "л": "l", "l": "l", "мл": "ml", "ml": "ml", "шт": "pcs", "pcs": "pcs"}
            return {"value": val, "unit": unit_map.get(unit, unit)}

        return {"value": 1.0, "unit": "pcs"}

    def normalize(self, raw_data, media_proxy):
        raise NotImplementedError("Цей метод мають реалізувати дочірні класи")