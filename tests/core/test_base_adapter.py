import pytest
from core.base_adapter import BaseAdapter

class TestBaseAdapter:

    @pytest.mark.parametrize("input_str, expected", [
        # 1. Грами (кирилиця і латиниця, з пробілами і без)
        ("150г", {"value": 150.0, "unit": "g"}),
        ("150 г", {"value": 150.0, "unit": "g"}),
        ("150g", {"value": 150.0, "unit": "g"}),

        # 2. Кілограми
        ("1.5кг", {"value": 1.5, "unit": "kg"}),
        ("1,5 кг", {"value": 1.5, "unit": "kg"}),  # Кома має стати крапкою
        ("2kg", {"value": 2.0, "unit": "kg"}),

        # 3. Рідини (мілілітри та літри)
        ("500 мл", {"value": 500.0, "unit": "ml"}),
        ("500ml", {"value": 500.0, "unit": "ml"}),
        ("1.5 л", {"value": 1.5, "unit": "l"}),
        ("2l", {"value": 2.0, "unit": "l"}),

        # 4. Штуки
        ("10 шт", {"value": 10.0, "unit": "pcs"}),
        ("1шт", {"value": 1.0, "unit": "pcs"}),
        ("5 pcs", {"value": 5.0, "unit": "pcs"}),

        # 5. Невідомі одиниці виміру (якщо регулярка зловить цифру і букви, яких немає в словнику)
        ("100 унцій", {"value": 100.0, "unit": "унцій"}),
    ])
    def test_parse_measurements_valid_inputs(self, input_str, expected):
        """Перевіряє коректний парсинг різних одиниць виміру та чисел"""
        assert BaseAdapter.parse_measurements(input_str) == expected

    @pytest.mark.parametrize("invalid_input", [
        "",
        None,
        "   ",
        "просто текст",   # Немає цифр взагалі
        "100",            # Немає букв (одиниць виміру)
        "кг 1.5",         # Неправильний порядок
    ])
    def test_parse_measurements_invalid_and_fallback(self, invalid_input):
        """Якщо формат неправильний або порожній, має повертатися дефолтне значення (1 шт)"""
        assert BaseAdapter.parse_measurements(invalid_input) == {"value": 1.0, "unit": "pcs"}

    def test_normalize_raises_not_implemented_error(self):
        """Перевіряє, що базовий метод normalize захищений і вимагає реалізації в дочірніх класах"""
        adapter = BaseAdapter()

        # Перевіряємо, чи дійсно викидається помилка NotImplementedError
        with pytest.raises(NotImplementedError) as exc_info:
            adapter.normalize(raw_data={}, media_proxy=None)

        # Перевіряємо, чи правильний текст помилки
        assert "Цей метод мають реалізувати дочірні класи" in str(exc_info.value)