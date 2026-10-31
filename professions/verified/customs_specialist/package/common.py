"""Таможенные сценарии РФ/ЕАЭС: чистые проверки и расчёты Decimal.
Внешних вызовов, файлов и неизменяемых ставок нет. Нормы передаются входами.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

D = Decimal
ZERO = D("0")
FUNCTIONS = ("tnved_classification", "customs_value", "customs_payments", "declaration", "non_tariff", "origin", "trade_contract", "post_clearance")


def fail(code):
    raise ValueError(code)


def number(value, name, minimum=ZERO, maximum=D("1e18")):
    if type(value) is bool:
        fail(name + "_type")
    try:
        result = D(str(value))
    except (InvalidOperation, ValueError):
        fail(name + "_not_number")
    if not result.is_finite() or result < minimum or result > maximum:
        fail(name + "_range")
    return result


def text(value, name, size=10000, empty=False):
    if type(value) is not str or len(value) > size or (not empty and not value.strip()):
        fail(name + "_invalid")
    return value.strip()


def rows(value, name, maximum=100):
    if type(value) is not list or not value or len(value) > maximum:
        fail(name + "_invalid")
    return value


def mapping(value, name):
    if type(value) is not dict:
        fail(name + "_invalid")
    return value


def boolean(value, name):
    if type(value) is not bool:
        fail(name + "_invalid")
    return value


def money(value):
    return str(value.quantize(D("0.01"), rounding=ROUND_HALF_UP))


def dated(value, name):
    text(value, name, 10)
    try:
        return date.fromisoformat(value)
    except ValueError:
        fail(name + "_invalid_date")


def rate_line(label, amount, currency="RUB", source=""):
    return [label, money(amount), currency, source]


def convert(amount, fx):
    return amount * fx


