"""Чистые расчёты профессии: функция(data: dict) -> dict. Decimal (prec=128 уже включён), без сети и файлов."""
from decimal import Decimal


def input_units(function_id, data):
    """Какие поля — числа и в каких единицах: {'путь/к/полю': 'единица'}; биндинг сверит их с цитатами."""
    return {'amount': 'RUB'}


def example_calc(data):
    amount = Decimal(str(data['amount']))
    return {'amount': str(amount), 'doubled': str(amount * 2)}
