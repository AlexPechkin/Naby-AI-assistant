"""Оценка недвижимости РФ: проверки задания, источников и расчёты подходов."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

D = Decimal
ZERO = D("0")
FUNCTIONS = ("assignment", "object_docs", "market_analysis", "sales_comparison", "income_approach", "cost_approach", "valuation_report", "cadastral_dispute", "mortgage_pledge", "report_review", "appraiser_status")


def fail(code): raise ValueError(code)
def text(v, n, size=10000, empty=False):
    if type(v) is not str or len(v) > size or (not empty and not v.strip()): fail(n + "_invalid")
    return v.strip()
def num(v, n, low=ZERO, high=D("1e20")):
    if type(v) is bool: fail(n + "_type")
    try: r = D(str(v))
    except (InvalidOperation, ValueError): fail(n + "_not_number")
    if not r.is_finite() or r < low or r > high: fail(n + "_range")
    return r
def money(v): return str(v.quantize(D("0.01"), rounding=ROUND_HALF_UP))
def boolean(v, n):
    if type(v) is not bool: fail(n + "_invalid")
    return v
def mapping(v, n):
    if type(v) is not dict: fail(n + "_invalid")
    return v
def rows(v, n, maximum=200):
    if type(v) is not list or not v or len(v) > maximum: fail(n + "_invalid")
    return v
def dated(v, n):
    text(v, n, 10)
    try: return date.fromisoformat(v)
    except ValueError: fail(n + "_date")

